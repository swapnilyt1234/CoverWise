import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from uagents import Model
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent
from uagents_core.types import DeliveryStatus

from coverwise import agents, policies, provider
from coverwise.catalogue import CatalogueSnapshot, load_catalogue
from coverwise.generate_policies import generate
from coverwise.recommend import RecommendationInput, evaluate, parse_input
from coverwise.sandbox import (
    CHALLENGE_TTL,
    QUOTE_TTL,
    SandboxError,
    SandboxProvider,
    owner_scope,
)
from coverwise.sandbox_contracts import ApplicationFields, SandboxCommand, SandboxReply
from coverwise.sandbox_ui import HELP, START, parse_command, present
from coverwise.transport import SandboxRequest, SandboxResult


class Clock:
    value = datetime(2026, 10, 24, tzinfo=timezone.utc)

    def __call__(self):
        return self.value


@pytest.fixture
def insurer(tmp_path, monkeypatch):
    pdfs = tmp_path / "pdfs"
    monkeypatch.setattr(policies, "PDF_DIR", pdfs)
    sources = {}
    for identifier, spec in (policies.REGISTRY | policies.CANDIDATES).items():
        source = json.loads(
            (policies.ROOT / "fixtures" / "policies" / f"{identifier}.json").read_text(
                encoding="utf-8"
            )
        )
        sources[identifier] = source
        generate(source, pdfs / spec.filename)
    snapshot = [load_catalogue()]
    clock = Clock()

    def assessment(inputs, catalogue):
        ids = [
            "existing-employer",
            *(["existing-personal"] if inputs.path == "existing-personal" else []),
            *(p.document.document_id for p in catalogue.catalogue.products),
        ]
        return evaluate(inputs, catalogue, [policies.load_policy(p) for p in ids])

    store = SandboxProvider(
        tmp_path / "provider.sqlite3",
        clock=clock,
        catalogue=lambda: snapshot[0],
        assessor=assessment,
    )
    return SimpleNamespace(
        store=store,
        clock=clock,
        snapshot=snapshot,
        sources=sources,
        session=uuid4(),
        sender="synthetic-acp-sender",
        assessment=assessment,
    )


def execute(env, text, *, sender=None, session=None, operation=None, store=None):
    command = parse_command(text) if isinstance(text, str) else text
    return (store or env.store).execute(
        sender or env.sender, session or env.session, operation or uuid4(), command
    )


def quote(env, inputs=None, product="candidate-horizon"):
    return execute(
        env,
        SandboxCommand(
            action="quote", product_id=product, inputs=inputs or parse_input("preset")
        ),
    )


def review(env, mode="success", inputs=None):
    q = quote(env, inputs)
    assert q.state == "quote_active"
    app = execute(env, f"/apply {q.reference} confirm-demo {mode}")
    assert app.state == "review"
    return q, app


def restart(env):
    return SandboxProvider(
        env.store.path,
        clock=env.clock,
        catalogue=lambda: env.snapshot[0],
        assessor=env.assessment,
    )


def test_computed_quote_evidence_expiry_and_calendar_dates(insurer):
    reply = quote(insurer)
    q = reply.quote
    assert q.premium_paise == 2200000 and type(q.premium_paise) is int
    assert q.created_at == insurer.clock.value
    assert q.expires_at - q.created_at == QUOTE_TTL
    assert str(q.cover_start) == "2027-01-01" and str(q.cover_end) == "2027-12-31"
    assert (
        str(q.wait_end) == "2027-01-30" and str(q.first_post_wait_day) == "2027-01-31"
    )
    assert q.evidence.document.sha256 == q.product.document.sha256
    assert q.immediate_status == "excluded" and "Computed" in q.premium_basis
    assert execute(insurer, "/sandbox-status " + q.quote_id).quote == q
    assert insurer.store.counts()["payments"] == 0


@pytest.mark.parametrize(
    "offset,expected", [(-1, "review"), (0, "rejected"), (1, "rejected")]
)
def test_quote_expiry_boundary(insurer, offset, expected):
    q = quote(insurer).quote
    insurer.clock.value = q.expires_at + timedelta(microseconds=offset)
    app = execute(insurer, f"/apply {q.quote_id} confirm-demo success")
    assert app.state == expected
    if expected == "rejected":
        assert app.error_code == "quote_expired"
        assert insurer.store.counts()["applications"] == 0


@pytest.mark.parametrize(
    "offset,expected", [(-1, "completed"), (0, "rejected"), (1, "rejected")]
)
def test_challenge_expiry_boundary(insurer, offset, expected):
    _, app = review(insurer)
    assert app.application.challenge_expires_at == insurer.clock.value + CHALLENGE_TTL
    insurer.clock.value = app.application.challenge_expires_at + timedelta(
        microseconds=offset
    )
    result = execute(insurer, app.next_commands[0])
    assert result.state == expected
    assert insurer.store.counts()["payments"] == (1 if expected == "completed" else 0)


@pytest.mark.parametrize("product", ["candidate-economy", "candidate-query"])
def test_hard_failures_and_missing_schedule_cannot_be_quoted(insurer, product):
    result = quote(insurer, product=product)
    assert result.state == "rejected"
    assert insurer.store.counts()["quotes"] == 0


def test_budget_disclosure_and_existing_cover_paths_fail_closed(insurer):
    for preset in ("preset-low", "preset-existing"):
        assert quote(insurer, parse_input(preset)).state == "rejected"
    inputs = parse_input("preset").model_dump()
    inputs["members"][0]["preexisting"] = "unknown"
    assert (
        quote(insurer, RecommendationInput.model_validate(inputs)).state == "rejected"
    )
    assert insurer.store.counts()["quotes"] == 0


@pytest.mark.parametrize(
    "fields",
    [
        dict(confirm_demo=False, payment_outcome="success"),
        dict(confirm_demo=1, payment_outcome="success"),
        dict(confirm_demo=True, payment_outcome="success", card="not-collected"),
    ],
)
def test_invalid_application_rejected_before_revision(insurer, fields):
    quote(insurer)
    with pytest.raises(ValueError):
        ApplicationFields.model_validate(fields)
    assert (
        insurer.store.counts()["applications"]
        == insurer.store.counts()["revisions"]
        == 0
    )


def test_no_payment_without_approval_and_wrong_challenge(insurer):
    _, app = review(insurer)
    with pytest.raises(SandboxError, match="approval_required"):
        insurer.store.purchase(
            owner_scope(insurer.sender, insurer.session), app.reference
        )
    wrong = parse_command(app.next_commands[0]).model_copy(
        update={"challenge": "x" * 24}
    )
    assert execute(insurer, wrong).state == "rejected"
    assert (
        insurer.store.counts()["approvals"] == insurer.store.counts()["payments"] == 0
    )


@pytest.mark.parametrize("wrong", ["sender", "session"])
def test_cross_scope_approve_status_and_challenge_rejected(insurer, wrong):
    q, app = review(insurer)
    kwargs = {wrong: "other-sender" if wrong == "sender" else uuid4()}
    for text in (
        app.next_commands[0],
        "/sandbox-status " + app.reference,
        "/sandbox-status " + q.reference,
        "/sandbox-status " + q.operation_id,
    ):
        result = execute(insurer, text, **kwargs)
        assert (
            result.state == "rejected"
            and result.error_code == "not_found_or_not_authorized"
        )
        assert result.application is result.quote is result.payment is None
    assert insurer.store.counts()["payments"] == 0


def test_duplicate_and_concurrent_approvals_have_one_actual_payment(insurer):
    _, app = review(insurer)
    command = parse_command(app.next_commands[0])
    stores = [restart(insurer) for _ in range(4)]
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = list(
            workers.map(lambda s: execute(insurer, command, store=s), stores)
        )
    assert all(r.state == "completed" for r in results)
    assert len({r.payment.confirmation for r in results}) == 1
    assert len({r.payment.transaction_reference for r in results}) == 1
    counts = insurer.store.counts()
    for table in (
        "quotes",
        "applications",
        "revisions",
        "approvals",
        "payments",
        "payment_ledger",
    ):
        assert counts[table] == 1
    insurer.clock.value += timedelta(days=1)
    assert (
        execute(insurer, command).payment.confirmation
        == results[0].payment.confirmation
    )


def test_duplicate_application_is_not_a_silent_mutation(insurer):
    q, app = review(insurer)
    again = execute(insurer, f"/apply {q.reference} confirm-demo success")
    assert again.reference == app.reference and again.challenge is None
    changed = execute(insurer, f"/apply {q.reference} confirm-demo unknown")
    assert changed.error_code == "application_exists_use_review"
    assert insurer.store.counts()["applications"] == 1


def test_revision_rotates_challenge_and_invalidates_prior_approval(insurer):
    q, app = review(insurer)
    scope = owner_scope(insurer.sender, insurer.session)
    insurer.store.authorize(scope, parse_command(app.next_commands[0]))
    changed = execute(
        insurer, f"/review {app.reference} {q.reference} confirm-demo unknown"
    )
    assert changed.application.revision == 2 and changed.challenge != app.challenge
    assert execute(insurer, app.next_commands[0]).state == "rejected"
    with insurer.store.transaction() as db:
        assert db.execute("SELECT state FROM approvals").fetchone()[0] == "invalidated"
    assert insurer.store.counts()["payments"] == 0


@pytest.mark.parametrize("change", ["plan", "members", "start"])
def test_material_replacement_quote_requires_new_approval(insurer, change):
    inputs = parse_input("preset").model_dump()
    inputs.update(minimum_family_limit_paise=50000000, room_requirement="any-room")
    _, app = review(insurer, inputs=RecommendationInput.model_validate(inputs))
    insurer.store.authorize(
        owner_scope(insurer.sender, insurer.session),
        parse_command(app.next_commands[0]),
    )
    product = "candidate-horizon"
    if change == "plan":
        product = "candidate-economy"
    elif change == "members":
        inputs["members"] = inputs["members"][:1]
        inputs["event_member_id"] = "member-01"
    else:
        inputs["proposed_start"] = "2026-12-01"
    q = quote(insurer, RecommendationInput.model_validate(inputs), product=product)
    assert q.state == "quote_active"
    newer = execute(
        insurer, f"/review {app.reference} {q.reference} confirm-demo success"
    )
    assert newer.application.revision == 2
    assert execute(insurer, app.next_commands[0]).state == "rejected"
    assert insurer.store.counts()["payments"] == 0


def test_changed_authoritative_price_invalidates_accepted_approval(insurer):
    _, app = review(insurer)
    insurer.store.authorize(
        owner_scope(insurer.sender, insurer.session),
        parse_command(app.next_commands[0]),
    )
    payload = insurer.snapshot[0].model_dump(mode="json")
    payload["catalogue"]["products"][2]["annual_premium_paise"] += 100
    insurer.snapshot[0] = CatalogueSnapshot.model_validate(payload)
    result = execute(insurer, app.next_commands[0])
    assert result.state == "rejected"
    with insurer.store.transaction() as db:
        assert (
            db.execute("SELECT state FROM applications").fetchone()[0] == "needs_review"
        )
        assert db.execute("SELECT state FROM approvals").fetchone()[0] == "invalidated"
    assert insurer.store.counts()["payments"] == 0


def test_definite_failure_never_completes_or_retries(insurer):
    _, app = review(insurer, "failure")
    failed = execute(insurer, app.next_commands[0])
    assert failed.state == "failed" and failed.payment.confirmation is None
    assert (
        execute(insurer, app.next_commands[0]).payment.payment_id
        == failed.payment.payment_id
    )
    assert execute(insurer, "/sandbox-status " + app.reference).state == "failed"
    with insurer.store.transaction() as db:
        row = db.execute("SELECT * FROM payment_ledger").fetchone()
        assert row["authoritative_state"] == "failed" and row["amount_paise"] == 0
    assert insurer.store.counts()["payments"] == 1


def test_unknown_stays_pending_until_status_reconciliation_after_restart(insurer):
    _, app = review(insurer, "unknown")
    unknown = execute(insurer, app.next_commands[0])
    assert unknown.state == "payment_pending" and unknown.payment.state == "unknown"
    assert unknown.payment.confirmation is None
    assert execute(insurer, app.next_commands[0]).state == "payment_pending"
    assert execute(insurer, "/cancel " + app.reference).state == "rejected"
    insurer.clock.value += timedelta(days=1)
    fresh = restart(insurer)
    reconciled = execute(insurer, "/sandbox-status " + app.reference, store=fresh)
    assert reconciled.state == "completed"
    assert reconciled.payment.payment_id == unknown.payment.payment_id
    assert (
        execute(
            insurer, "/sandbox-status " + app.reference, store=fresh
        ).payment.confirmation
        == reconciled.payment.confirmation
    )
    assert fresh.counts()["payments"] == fresh.counts()["payment_ledger"] == 1


def test_restart_preserves_review_challenge_and_completion(insurer):
    _, app = review(insurer)
    fresh = restart(insurer)
    completed = execute(insurer, app.next_commands[0], store=fresh)
    assert completed.state == "completed"
    another = restart(insurer)
    assert (
        execute(insurer, "/sandbox-status " + app.reference, store=another).payment
        == completed.payment
    )


def test_crash_after_durable_approval_recovers_without_new_payment(
    insurer, monkeypatch
):
    _, app = review(insurer)
    original = insurer.store.purchase
    monkeypatch.setattr(
        insurer.store,
        "purchase",
        lambda *_: (_ for _ in ()).throw(RuntimeError("simulated crash")),
    )
    op = uuid4()
    with pytest.raises(RuntimeError):
        execute(insurer, app.next_commands[0], operation=op)
    assert insurer.store.counts()["approvals"] == 1
    assert insurer.store.counts()["payments"] == 0
    monkeypatch.setattr(insurer.store, "purchase", original)
    recovered = execute(insurer, "/sandbox-status op-" + op.hex, store=restart(insurer))
    assert recovered.state == "completed"
    assert insurer.store.counts()["payments"] == 1


@pytest.mark.parametrize("approved", [False, True])
def test_cancel_before_execution_invalidates_approval(insurer, approved):
    _, app = review(insurer)
    if approved:
        insurer.store.authorize(
            owner_scope(insurer.sender, insurer.session),
            parse_command(app.next_commands[0]),
        )
    cancelled = execute(insurer, "/cancel " + app.reference)
    assert cancelled.state == "cancelled"
    assert execute(insurer, app.next_commands[0]).state == "rejected"
    assert execute(insurer, "/review " + app.reference).state == "rejected"
    assert insurer.store.counts()["payments"] == 0


def test_completed_transaction_cannot_be_cancelled_or_mutated(insurer):
    _, app = review(insurer)
    completed = execute(insurer, app.next_commands[0])
    for command in ("/cancel " + app.reference, "/review " + app.reference):
        assert execute(insurer, command).state == "rejected"
    assert (
        execute(insurer, "/sandbox-status " + app.reference).payment
        == completed.payment
    )


def test_operation_idempotency_and_scope(insurer):
    op = uuid4()
    first = execute(insurer, "/quote preset", operation=op)
    again = execute(insurer, "/quote preset", operation=op)
    assert first.quote == again.quote
    assert insurer.store.counts()["quotes"] == 1
    with pytest.raises(SandboxError, match="operation_conflict"):
        execute(insurer, "/quote preset", operation=op, session=uuid4())


def test_unknown_schema_is_rejected_without_destroying_records(insurer):
    quote(insurer)
    with sqlite3.connect(insurer.store.path) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(SandboxError, match="unsupported_schema"):
        restart(insurer)
    with sqlite3.connect(insurer.store.path) as db:
        assert db.execute("SELECT count(*) FROM quotes").fetchone()[0] == 1


def sandbox_router(store, *, session=None, timeout=3):
    service = agents.Coordinator("investigator", provider="provider", timeout=timeout)
    protocols = []
    provider.install_provider(
        SimpleNamespace(include=protocols.append), "coordinator", sandbox=store
    )
    context = SimpleNamespace(
        agent=SimpleNamespace(address="coordinator"), session=session or uuid4()
    )
    tasks = []

    async def send(destination, message):
        assert destination == "provider"

        async def result(_destination, reply):
            await service.accept_result(context, "provider", reply)

        tool_context = SimpleNamespace(session=context.session, send=result)
        handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(SandboxRequest)
        ]
        tasks.append(asyncio.create_task(handler(tool_context, "coordinator", message)))
        return SimpleNamespace(status=DeliveryStatus.DELIVERED)

    context.send = send
    return service, context, tasks


@pytest.mark.parametrize("stage", ["quote", "approval"])
def test_typed_sdk_flow_and_timeout_status_recovery(
    insurer, monkeypatch, stage, caplog
):
    import logging
    import time

    caplog.set_level(logging.INFO, logger="coverwise")
    command = (
        "/quote preset" if stage == "quote" else review(insurer)[1].next_commands[0]
    )
    original = insurer.store.execute
    first = [True]

    def delayed(*args):
        result = original(*args)
        if first[0]:
            first[0] = False
            time.sleep(0.12)
        return result

    monkeypatch.setattr(insurer.store, "execute", delayed)

    async def exercise():
        service, context, tasks = sandbox_router(
            insurer.store, session=insurer.session, timeout=0.05
        )
        result = await service.sandbox_operation(
            context, insurer.sender, parse_command(command)
        )
        assert result.status == "error" and result.error == "timeout"
        assert not service.pending
        await asyncio.gather(*tasks)
        assert "reason=expired" in caplog.text
        # The 50ms budget injects failure; recovery uses the normal harness budget.
        service.timeout = 3
        status = parse_command("/sandbox-status op-" + result.request_id.hex)
        recovered = await service.sandbox_operation(context, insurer.sender, status)
        assert recovered.status == "success"
        reply = SandboxReply.model_validate_json(recovered.payload_json)
        assert reply.state == ("quote_active" if stage == "quote" else "completed")
        assert insurer.store.counts()["quotes"] == 1
        assert insurer.store.counts()["payments"] == (stage == "approval")
        assert not service.pending

    asyncio.run(exercise())


def test_acp_self_mention_review_and_no_challenge_in_logs(insurer, caplog):
    import logging

    q = quote(insurer)

    async def exercise():
        service = agents.Coordinator("investigator", provider="provider")
        context = SimpleNamespace(
            agent=SimpleNamespace(address="coordinator"),
            session=insurer.session,
            send=AsyncMock(
                return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)
            ),
        )
        result = execute(insurer, f"/apply {q.reference} confirm-demo success")

        async def operation(_ctx, sender, command):
            assert sender == insurer.sender
            return SandboxResult(
                request_id=uuid4(),
                status="success",
                payload_json=result.model_dump_json(),
            )

        service.sandbox_operation = operation
        with caplog.at_level(logging.INFO, logger="coverwise"):
            await service.chat(
                context,
                insurer.sender,
                ChatMessage(
                    content=[
                        TextContent(
                            text="@coordinator /apply "
                            + q.reference
                            + " confirm-demo success"
                        )
                    ]
                ),
            )
        text = context.send.call_args.args[1].text()
        assert result.next_commands[0] in text
        assert "review revision 1" in text and "no real policy issued" in text
        assert result.challenge not in caplog.text
        assert "1992-04-10" not in caplog.text
        assert len(text) <= policies.MAX_REPLY

    asyncio.run(exercise())


def test_wrong_sdk_sender_or_session_cannot_touch_database(insurer):
    async def exercise():
        protocols = []
        provider.install_provider(
            SimpleNamespace(include=protocols.append),
            "coordinator",
            sandbox=insurer.store,
        )
        handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(SandboxRequest)
        ]
        context = SimpleNamespace(session=uuid4(), send=AsyncMock())
        request = SandboxRequest(
            request_id=uuid4(),
            observed_sender=insurer.sender,
            observed_session=insurer.session,
            command_json=parse_command("/quote preset").model_dump_json(),
        )
        await handler(context, "intruder", request)
        context.send.assert_not_called()
        await handler(context, "coordinator", request)
        assert context.send.call_args.args[1].error == "scope_mismatch"
        assert insurer.store.counts()["operations"] == 0

    asyncio.run(exercise())


def test_missing_authoritative_effect_keeps_unknown_pending_without_retry(insurer):
    _, app = review(insurer, "unknown")
    pending = execute(insurer, app.next_commands[0])
    with insurer.store.transaction() as db:
        db.execute("DELETE FROM payment_ledger")
    status = execute(
        insurer, "/sandbox-status " + app.reference, store=restart(insurer)
    )
    assert status.state == "payment_pending" and status.payment == pending.payment
    assert execute(insurer, app.next_commands[0]).state == "payment_pending"
    assert insurer.store.counts()["payments"] == 1
    assert insurer.store.counts()["payment_ledger"] == 0


def test_durable_approval_cannot_start_payment_after_review_expiry(insurer):
    _, app = review(insurer)
    insurer.store.authorize(
        owner_scope(insurer.sender, insurer.session),
        parse_command(app.next_commands[0]),
    )
    insurer.clock.value = app.application.challenge_expires_at
    result = execute(
        insurer, "/sandbox-status " + app.reference, store=restart(insurer)
    )
    assert result.state == "rejected" and result.error_code == "approval_expired"
    assert insurer.store.counts()["payments"] == 0
    refreshed = execute(insurer, "/review " + app.reference)
    assert refreshed.state == "review" and refreshed.application.revision == 2
    assert execute(insurer, app.next_commands[0]).state == "rejected"


def test_expired_quote_requires_new_quote_and_review(insurer):
    _, app = review(insurer)
    insurer.clock.value = app.application.quote.expires_at
    assert execute(insurer, app.next_commands[0]).state == "rejected"
    status = execute(insurer, "/sandbox-status " + app.reference)
    assert status.state == "needs_review"
    fresh = execute(insurer, status.next_commands[1])
    newer = execute(
        insurer, f"/review {app.reference} {fresh.reference} confirm-demo success"
    )
    assert newer.application.revision == 2
    assert execute(insurer, newer.next_commands[0]).state == "completed"


@pytest.mark.parametrize("change", ["premium_paise", "currency"])
def test_tampered_material_quote_cannot_execute_payment(insurer, change):
    q, app = review(insurer)
    insurer.store.authorize(
        owner_scope(insurer.sender, insurer.session),
        parse_command(app.next_commands[0]),
    )
    with insurer.store.transaction() as db:
        raw = json.loads(
            db.execute("SELECT body FROM quotes WHERE id=?", (q.reference,)).fetchone()[
                0
            ]
        )
        raw[change] = raw[change] + 1 if change == "premium_paise" else "USD"
        db.execute(
            "UPDATE quotes SET body=? WHERE id=?", (json.dumps(raw), q.reference)
        )
    result = execute(insurer, app.next_commands[0])
    assert result.state == "rejected" and result.error_code == "quote_integrity_failure"
    assert insurer.store.counts()["payments"] == 0


def test_historic_quote_cannot_create_second_application(insurer):
    q, app = review(insurer)
    fresh = quote(insurer)
    assert (
        execute(
            insurer, f"/review {app.reference} {fresh.reference} confirm-demo success"
        ).state
        == "review"
    )
    assert (
        execute(insurer, f"/apply {q.reference} confirm-demo success").state
        == "rejected"
    )
    assert insurer.store.counts()["applications"] == 1


@pytest.mark.parametrize("action", ["quote", "apply"])
def test_resource_and_operation_reference_survive_lost_reply(
    insurer, monkeypatch, action
):
    command = "/quote preset"
    if action == "apply":
        command = f"/apply {quote(insurer).reference} confirm-demo success"
    monkeypatch.setattr(
        insurer.store,
        "view",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("lost reply")),
    )
    op = uuid4()
    with pytest.raises(RuntimeError, match="lost reply"):
        execute(insurer, command, operation=op)
    recovered = execute(insurer, "/sandbox-status op-" + op.hex, store=restart(insurer))
    assert recovered.state == ("quote_active" if action == "quote" else "review")
    assert insurer.store.counts()["quotes"] == 1
    assert insurer.store.counts()["payments"] == 0


def test_quote_budget_exact_boundary(insurer):
    inputs = parse_input("preset").model_dump()
    inputs["annual_budget_paise"] = 2200000
    assert (
        quote(insurer, RecommendationInput.model_validate(inputs)).state
        == "quote_active"
    )
    inputs["annual_budget_paise"] -= 1
    assert (
        quote(insurer, RecommendationInput.model_validate(inputs)).state == "rejected"
    )


@pytest.mark.parametrize(
    "change", ["scope", "action", "operation", "inputs", "product"]
)
def test_coordinator_rejects_wrong_workflow_binding(insurer, change):
    op = uuid4()
    result = execute(insurer, "/quote preset", operation=op)
    raw = result.model_dump(mode="json")
    if change == "scope":
        raw["scope"] = "0" * 64
    elif change == "action":
        raw["action"] = "status"
    elif change == "operation":
        raw["operation_id"] = "op-" + uuid4().hex
    elif change == "inputs":
        raw["quote"]["inputs"]["annual_budget_paise"] += 1
    else:
        raw["quote"]["product"]["product_id"] = "candidate-query"

    async def exercise():
        coordinator = agents.Coordinator("investigator", provider="provider")
        future = asyncio.get_running_loop().create_future()
        coordinator.pending[op] = agents.Pending(
            insurer.session,
            future,
            result_type=SandboxResult,
            sender="provider",
            sandbox=parse_command("/quote preset"),
            scope=result.scope,
        )
        accepted = await coordinator.accept_result(
            SimpleNamespace(session=insurer.session),
            "provider",
            SandboxResult(
                request_id=op, status="success", payload_json=json.dumps(raw)
            ),
        )
        assert not accepted and not future.done()

    asyncio.run(exercise())


def commands(text):
    return [block.split("\n```", 1)[0] for block in text.split("```text\n")[1:]]


@pytest.mark.parametrize(
    "text,reason",
    [
        (
            "/apply q-" + "a" * 32 + " confirm-demo private-profile",
            "success, failure or unknown",
        ),
        (
            "/apply private-profile confirm-demo success",
            "complete quote/application reference",
        ),
    ],
)
def test_sandbox_validation_error_is_actionable_without_echoing_fields(text, reason):
    with pytest.raises(ValueError) as error:
        parse_command(text)
    assert reason in str(error.value)
    assert "private-profile" not in str(error.value)
    assert "/sandbox" in str(error.value)


def test_quote_and_review_present_actual_commands_and_material_limits(insurer):
    q, app = review(insurer)
    for reply, ceiling in ((q, 220), (app, 330)):
        original = reply.model_dump_json()
        text = present(reply)
        assert len(text.split()) <= ceiling
        assert "2027-01-15: excluded" in text
        assert "2027-01-01 to 2027-01-30" in text
        assert "2027-01-31" in text and "UTC" in text
        assert "SHA-256" not in text
        assert ("born" in text) == (reply.state == "review")
        assert q.quote.product.document.sha256 not in text
        assert (
            "no real policy issued" in text.lower()
            and "no real money moved" in text.lower()
        )
        assert reply.next_commands[0] in commands(text)
        assert "/sandbox-details " + reply.reference in commands(text)
        for command in commands(text):
            assert "..." not in command and "…" not in command and "<" not in command
            parse_command(command)
        assert reply.model_dump_json() == original
    review_text = present(app)
    for restriction in app.application.quote.restrictions:
        from coverwise.money import display_money

        assert display_money(restriction) in review_text
    for disclosure in app.application.quote.required_disclosures:
        assert disclosure in review_text
    assert app.next_commands[0] in commands(review_text)
    assert "/cancel " + app.reference in commands(review_text)


@pytest.mark.parametrize(
    "mode,state",
    [("success", "completed"), ("failure", "failed"), ("unknown", "payment_pending")],
)
def test_payment_presenter_actions_match_authoritative_state(insurer, mode, state):
    _, app = review(insurer, mode)
    result = execute(insurer, app.next_commands[0])
    text = present(result)
    assert result.state == state
    assert len(text.split()) <= 140
    assert result.payment.payment_id in text
    assert result.payment.transaction_reference in text
    assert "Challenge expires" not in text and "approval expiry" not in text
    assert "Required:" not in text and "Synthetic disclosures:" not in text
    assert (
        "confirm-demo" not in text and "/approve " not in text and "/apply " not in text
    )
    assert "Quote:" not in text and "born" not in text
    assert commands(text) == [
        "/sandbox-status " + app.reference,
        "/sandbox-details " + app.reference,
    ]
    if mode == "unknown":
        assert "Reconciliation is required" in text and "Do not pay again" in text
        assert result.payment.confirmation is None and "Confirmation:" not in text
    elif mode == "success":
        assert (
            result.payment.confirmation in text
            and "Future claims are not guaranteed" in text
        )
    else:
        assert "definitely failed" in text and "No purchase completed" in text


def details_payload(text):
    return json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])


def restore_details(records):
    """Consume the displayed record format as a client, checking string coverage."""
    root, segments = None, {}

    def assign(path, value):
        nonlocal root
        if not path:
            root = value
        else:
            parent = root
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = value

    for record in records:
        kind, path = record["kind"], record["path"]
        if kind == "string_segment":
            segments.setdefault(tuple(path), []).append(record)
        else:
            assert kind in ("object", "array", "value")
            value = (
                {}
                if kind == "object"
                else [None] * record["length"]
                if kind == "array"
                else record["value"]
            )
            assign(path, value)
    for path, parts in segments.items():
        offset, strings = 0, []
        for part in sorted(parts, key=lambda p: p["offset"]):
            assert part["offset"] == offset
            offset += len(part["value"])
            strings.append(part["value"])
        assert offset == parts[0]["total_characters"]
        assign(path, "".join(strings))
    return root


def test_details_are_complete_read_only_and_do_not_disclose_challenge(insurer):
    _, app = review(insurer, "unknown")
    pending = execute(insurer, app.next_commands[0])
    records = []
    page = 1
    while True:
        details = execute(insurer, f"/sandbox-details {app.reference} {page}")
        assert details.state == "payment_pending" and details.payment == pending.payment
        text = present(details, page=page)
        assert len(text) <= policies.MAX_REPLY
        assert app.challenge not in text and "/approve " not in text
        payload = details_payload(text)
        assert payload["reference"] == app.reference and payload["page"] == page
        assert 1 <= page <= payload["total"] <= 64
        assert len(text.encode("utf-8")) <= policies.MAX_REPLY
        records.extend(payload["records"])
        if page > 1:
            assert f"/sandbox-details {app.reference} {page - 1}" in commands(text)
        next_command = f"/sandbox-details {app.reference} {page + 1}"
        assert (next_command in commands(text)) == (page < payload["total"])
        if page == payload["total"]:
            break
        page += 1
    data = restore_details(records)
    assert data["application"] == pending.application.model_dump(mode="json")
    assert data["payment"] == pending.payment.model_dump(mode="json")
    assert (
        insurer.store.counts()["payments"]
        == insurer.store.counts()["payment_ledger"]
        == 1
    )
    # Status remains the existing explicit reconciliation operation.
    assert execute(insurer, "/sandbox-status " + app.reference).state == "completed"


def test_details_large_escaped_unicode_excerpt_is_segmented_without_loss(insurer):
    q = quote(insurer)
    raw = q.model_dump(mode="json")
    # Valid source text can be much larger than a page and include Markdown fences.
    excerpt = 'Line "quoted" \\ path\n₹😀 ```json\n```\t' * 700 + "END"
    raw["quote"]["evidence"]["terms"][0]["evidence"][0]["excerpt"] = excerpt
    reply = SandboxReply.model_validate(raw)
    before = reply.model_dump_json()
    records, totals = [], []
    page = 1
    while True:
        text = present(reply.model_copy(update={"action": "details"}), page=page)
        payload = details_payload(text)
        assert text.count("```json\n") == 1
        assert len(text.encode("utf-8")) <= policies.MAX_REPLY
        assert payload["reference"] == q.reference and payload["page"] == page
        assert all("path" in r and "kind" in r for r in payload["records"])
        records.extend(payload["records"])
        totals.append(payload["total"])
        assert (f"/sandbox-details {q.reference} {page + 1}" in commands(text)) == (
            page < payload["total"]
        )
        if page == payload["total"]:
            break
        page += 1
    assert len(set(totals)) == 1
    assert any(
        r["kind"] == "string_segment" and r["path"][-1] == "excerpt" for r in records
    )
    restored = restore_details(records)
    assert restored["quote"] == reply.quote.model_dump(mode="json")
    assert (
        restored["quote"]["evidence"]["terms"][0]["evidence"][0]["excerpt"] == excerpt
    )
    assert reply.model_dump_json() == before


def test_details_single_page_and_out_of_range_are_valid_json(insurer):
    # An unknown operation has a small, read-only snapshot and needs one page.
    reply = execute(insurer, "/sandbox-details op-" + uuid4().hex)
    text = present(reply)
    payload = details_payload(text)
    assert payload["page"] == payload["total"] == 1
    assert commands(text) == ["/sandbox-status " + reply.reference]
    assert restore_details(payload["records"])["state"] == "operation_pending"
    invalid = present(reply, page=64)
    error = details_payload(invalid)
    assert error["reference"] == reply.reference
    assert error["error"] == "page_out_of_range" and error["records"] == []
    assert f"/sandbox-details {reply.reference} 1" in commands(invalid)
    assert len(invalid.encode("utf-8")) <= policies.MAX_REPLY


@pytest.mark.parametrize("kind", ["quote", "application", "operation"])
@pytest.mark.parametrize("wrong", ["sender", "session"])
def test_details_reuse_sender_and_session_isolation(insurer, kind, wrong):
    q, app = review(insurer)
    ref = {
        "quote": q.reference,
        "application": app.reference,
        "operation": app.operation_id,
    }[kind]
    kwargs = {wrong: "other-sender" if wrong == "sender" else uuid4()}
    result = execute(insurer, "/sandbox-details " + ref, **kwargs)
    assert result.state == "rejected" and result.application is result.quote is None
    assert result.error_code == "not_found_or_not_authorized"


def test_details_of_approved_application_do_not_start_payment(insurer):
    _, app = review(insurer)
    insurer.store.authorize(
        owner_scope(insurer.sender, insurer.session),
        parse_command(app.next_commands[0]),
    )
    details = execute(insurer, "/sandbox-details " + app.reference)
    assert details.state == "approved" and details.payment is None
    assert insurer.store.counts()["payments"] == 0


def test_details_use_typed_sdk_delegation_and_preserve_old_command_serialization(
    insurer,
):
    q = quote(insurer)
    # Existing operation digests must not gain default fields after this UI change.
    assert set(parse_command("/quote preset").model_dump()) == {
        "action",
        "product_id",
        "inputs",
        "reference",
        "application",
        "replacement_quote",
        "revision",
        "challenge",
    }

    async def exercise():
        service, ctx, tasks = sandbox_router(insurer.store, session=insurer.session)
        result = await service.sandbox_operation(
            ctx, insurer.sender, parse_command("/sandbox-details " + q.reference)
        )
        await asyncio.gather(*tasks)
        assert result.status == "success" and not service.pending
        reply = SandboxReply.model_validate_json(result.payload_json)
        assert reply.action == "details" and reply.quote == q.quote
        assert "/sandbox-details " + q.reference + " 2" in present(reply)
        assert insurer.store.counts()["payments"] == 0

    asyncio.run(exercise())


@pytest.mark.parametrize("bad", ["0", "65", "-1", "no", "1 2"])
def test_details_page_validation(bad):
    with pytest.raises(ValueError):
        parse_command("/sandbox-details a-" + "a" * 32 + " " + bad)


def test_help_copyable_blocks_have_no_placeholders_and_start_is_read_only(insurer):
    for text in (HELP, START):
        for command in commands(text):
            assert "..." not in command and "…" not in command and "<" not in command
            assert command.startswith(("/quote ", "/recommend ", "/stress-test "))
    explicit = commands(HELP)[1]
    assert parse_command(explicit) == parse_command("/quote preset")

    async def exercise():
        service = agents.Coordinator("investigator", provider="provider")
        service.sandbox_operation = AsyncMock(
            side_effect=AssertionError("start is help only")
        )
        ctx = SimpleNamespace(
            agent=SimpleNamespace(address="coordinator"),
            session=insurer.session,
            send=AsyncMock(
                return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)
            ),
        )
        await service.chat(
            ctx,
            insurer.sender,
            ChatMessage(content=[TextContent(text="@coordinator /start")]),
        )
        response = ctx.send.call_args.args[1]
        assert "sample policies" in response.text().lower()
        assert response.content[1].metadata["card_kind"] == "carousel"
        assert response.content[1].metadata["requires_card_interaction"] == "true"
        assert insurer.store.counts()["quotes"] == 0

    asyncio.run(exercise())
