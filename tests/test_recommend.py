import asyncio
import hashlib
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from uagents import Model
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
)
from uagents_core.types import DeliveryStatus

from coverwise import agents, catalogue, policies, provider
from coverwise.agents import Coordinator, offline_recommend
from coverwise.catalogue import Catalogue, CatalogueSnapshot, load_catalogue
from coverwise.generate_policies import generate
from coverwise.live import LiveSettings
from coverwise.live import main as live_main
from coverwise.recommend import (
    Recommendation,
    RecommendationInput,
    evaluate,
    parse_input,
    present,
    present_evidence,
    scenario,
)
from coverwise.transport import (
    CandidateAssessmentRequest,
    CandidateAssessmentResult,
    CatalogueRequest,
    CatalogueResult,
)


@pytest.fixture
def fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(policies, "PDF_DIR", tmp_path)
    sources = {}
    for identifier, spec in (policies.REGISTRY | policies.CANDIDATES).items():
        source = json.loads(
            (policies.ROOT / "fixtures" / "policies" / f"{identifier}.json").read_text(
                encoding="utf-8"
            )
        )
        sources[identifier] = source
        generate(source, tmp_path / spec.filename)
    snapshot = load_catalogue()
    return tmp_path, sources, snapshot


def assess(fixtures, inputs=None):
    _, _, snapshot = fixtures
    inputs = inputs or parse_input("preset")
    ids = ["existing-employer"]
    if inputs.path == "existing-personal":
        ids.append("existing-personal")
    ids.extend(p.document.document_id for p in snapshot.catalogue.products)
    return evaluate(inputs, snapshot, [policies.load_policy(p) for p in ids])


def altered(inputs, **changes):
    return RecommendationInput.model_validate(inputs.model_dump() | changes)


def candidate(result, identifier="candidate-horizon"):
    return next(c for c in result.candidates if c.product_id == identifier)


def rewrite(fixtures, identifier, name, value, *, update_hash=False, **product_changes):
    root, sources, snapshot = fixtures
    source = sources[identifier]
    next(c for p in source["pages"] for c in p["clauses"] if c["term"] == name)[
        "value"
    ] = value
    path = root / policies.CANDIDATES[identifier].filename
    generate(source, path)
    if update_hash:
        payload = snapshot.model_dump(mode="json")
        product = next(
            p for p in payload["catalogue"]["products"] if p["product_id"] == identifier
        )
        product["document"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        product.update(product_changes)
        snapshot = CatalogueSnapshot.model_validate(payload)
    return root, sources, snapshot


def test_actual_preset_evidence_and_three_distinctions(fixtures):
    result = assess(fixtures)
    assert result.outcome == "shortlist"
    assert result.shortlist == ["candidate-horizon"]
    assert candidate(result, "candidate-economy").requirements.status == "fail"
    query = candidate(result, "candidate-query")
    assert query.requirements.status == "unknown" and query.disposition == "clarify"
    assert "room schedule" in " ".join(query.material_unknowns)
    horizon = candidate(result)
    assert (
        horizon.eligibility.status
        == horizon.budget.status
        == horizon.requirements.status
        == "pass"
    )
    assert horizon.immediate.status == "excluded"
    assert horizon.later.status == "conditional"
    assert horizon.first_eligible_day == date(2027, 1, 31)
    assert "2027-01-01 through 2027-01-31" in result.employer_gap
    for c in result.candidates:
        assert c.eligibility.evidence_ids and c.requirements.evidence_ids
        assert (
            c.immediate.scenario_id
            == scenario(result.inputs, result.inputs.immediate_event).scenario_id
        )
        assert c.later.scenario_id == result.baseline[0].later.scenario_id


@pytest.mark.parametrize(
    "budget,expected", [(2199999, "fail"), (2200000, "pass"), (2200001, "pass")]
)
def test_budget_boundaries(fixtures, budget, expected):
    result = assess(
        fixtures, altered(parse_input("preset"), annual_budget_paise=budget)
    )
    assert candidate(result).budget.status == expected


@pytest.mark.parametrize(
    "dob,status",
    [
        ("2009-01-01", "pass"),
        ("2009-01-02", "fail"),
        ("1967-01-01", "pass"),
        ("1966-01-01", "fail"),
    ],
)
def test_age_boundaries_at_start(fixtures, dob, status):
    inputs = parse_input("preset")
    members = [m.model_dump() for m in inputs.members]
    members[0]["date_of_birth"] = dob
    result = assess(fixtures, altered(inputs, members=members))
    assert candidate(result).eligibility.status == status
    if status == "fail":
        assert (
            candidate(result).immediate.status
            == candidate(result).later.status
            == "excluded"
        )


@pytest.mark.parametrize(
    "disclosure,expected",
    [("absent", "pass"), ("present", "fail"), ("unknown", "unknown")],
)
def test_disclosures(fixtures, disclosure, expected):
    inputs = parse_input("preset")
    members = [m.model_dump() for m in inputs.members]
    members[0]["preexisting"] = disclosure
    result = assess(fixtures, altered(inputs, members=members))
    assert candidate(result).eligibility.status == expected
    if expected == "unknown":
        assert candidate(result).disposition == "clarify" and not result.shortlist
        assert candidate(result).later.status == "insufficient_information"


def test_dependant_and_member_count_fail(fixtures):
    inputs = parse_input("preset")
    members = [m.model_dump() for m in inputs.members] + [
        dict(
            member_id="child-01",
            date_of_birth="2015-01-01",
            relationship="child",
            preexisting="absent",
        )
    ]
    result = assess(fixtures, altered(inputs, members=members))
    assert all(c.eligibility.status == "fail" for c in result.candidates)
    assert result.outcome == "no_suitable_option"
    assert "unsupported" in " ".join(candidate(result).eligibility.reasons)


@pytest.mark.parametrize(
    "event,expected",
    [
        ("2027-01-01", "excluded"),
        ("2027-01-30", "excluded"),
        ("2027-01-31", "conditional"),
    ],
)
def test_new_wait_boundaries(fixtures, event, expected):
    result = assess(fixtures, altered(parse_input("preset"), immediate_event=event))
    assert candidate(result).immediate.status == expected


def test_proposed_start_changes_wait_and_period(fixtures):
    result = assess(
        fixtures, altered(parse_input("preset"), proposed_start="2026-12-01")
    )
    assert candidate(result).first_eligible_day == date(2026, 12, 31)
    assert candidate(result).immediate.status == "conditional"
    assert result.inputs.immediate_event == date(2027, 1, 15)


@pytest.mark.parametrize(
    "preset,outcome",
    [
        ("preset-low", "no_suitable_option"),
        ("preset-clarify", "provider_clarification_required"),
        ("preset-existing", "keep_existing_obtain_terms"),
    ],
)
def test_no_option_clarification_existing(fixtures, preset, outcome):
    result = assess(fixtures, parse_input(preset))
    assert result.outcome == outcome and not result.shortlist
    if preset == "preset-existing":
        assert len(result.baseline) == 2
        assert result.baseline[1].immediate.status == "insufficient_information"
        assert candidate(result).budget.status == "pass"
        assert "₹28,000" in candidate(result).budget.reasons[0]
        assert "Keep existing personal cover" in present(result)


def test_catalogue_pdf_hash_and_term_disagreement(fixtures):
    changed = rewrite(
        fixtures,
        "candidate-horizon",
        "Sum insured",
        "50000000 INR paise per policy year, shared family hospitalization limit.",
    )
    with pytest.raises(policies.PolicyError, match="catalogue_pdf_disagreement"):
        assess(changed)
    changed = rewrite(
        fixtures,
        "candidate-horizon",
        "Sum insured",
        "50000000 INR paise per policy year, shared family hospitalization limit.",
        update_hash=True,
    )
    with pytest.raises(policies.PolicyError, match="catalogue_pdf_disagreement"):
        assess(changed)


def test_changed_matched_pdf_terms_change_facts_hash_and_result(fixtures):
    before = assess(fixtures)
    changed = rewrite(
        fixtures,
        "candidate-horizon",
        "Sum insured",
        "50000000 INR paise per policy year, shared family hospitalization limit.",
        update_hash=True,
        family_limit_paise=50000000,
    )
    after = assess(changed)
    assert candidate(before).disposition == "qualifies"
    assert candidate(after).disposition == "rejected"
    assert (
        candidate(before).immediate.document.sha256
        != candidate(after).immediate.document.sha256
    )
    assert (
        candidate(before).requirements.evidence_ids
        != candidate(after).requirements.evidence_ids
    )


def test_changed_wait_duration_is_not_copied_from_existing(fixtures):
    changed = rewrite(
        fixtures,
        "candidate-horizon",
        "Waiting period",
        "Initial illness wait is 60 days from proposed start, inclusive. "
        "No continuity credit or waiver is granted.",
        update_hash=True,
        initial_wait_days=60,
    )
    result = assess(changed)
    assert candidate(result).later.status == "excluded"
    assert candidate(result).first_eligible_day == date(2027, 3, 2)
    assert candidate(result).disposition == "rejected"


def test_requirement_change_can_make_cheaper_option_qualify(fixtures):
    result = assess(
        fixtures,
        altered(
            parse_input("preset"),
            minimum_family_limit_paise=50000000,
            room_requirement="any-room",
        ),
    )
    assert result.shortlist == ["candidate-economy", "candidate-horizon"]
    assert candidate(result, "candidate-query").disposition == "clarify"


def test_report_binding_and_roundtrip(fixtures):
    result = assess(fixtures)
    assert Recommendation.model_validate_json(result.model_dump_json()) == result
    payload = result.model_dump()
    payload["candidates"][0]["later"]["scenario_id"] = "wrong"
    with pytest.raises(ValueError, match="scenario mismatch"):
        Recommendation.model_validate(payload)


def test_reply_bounds_word_target_and_complete_evidence(fixtures):
    result = assess(fixtures)
    text = present(result)
    assert 300 <= len(text.split()) <= 500
    assert len(text) <= policies.MAX_REPLY
    for inspection in result.inspections:
        for page in range(1, inspection.document.page_count + 1):
            detail = present_evidence(result, inspection.document.document_id, page)
            assert len(detail) <= policies.MAX_REPLY
            for term in inspection.terms:
                for evidence in term.evidence:
                    if evidence.locator.page == page:
                        assert evidence.excerpt in detail
                        assert evidence.evidence_id in detail
    assert "/recommend-evidence" in text


@pytest.mark.parametrize("payload", ["", "employer-only 3000000", "x" * 1501])
def test_missing_inputs_request_clarification(payload):
    with pytest.raises(ValueError, match="recommend"):
        parse_input(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("annual_budget_paise", 1.2),
        ("minimum_family_limit_paise", 0),
        ("later_event", "2027-01-01"),
        ("assumed_new_employer_start", "2026-12-30"),
    ],
)
def test_invalid_input_not_accepted(field, value):
    with pytest.raises(ValueError):
        altered(parse_input("preset"), **{field: value})


def ctx():
    return SimpleNamespace(
        agent=SimpleNamespace(address="coordinator"),
        session=uuid4(),
        send=AsyncMock(return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)),
    )


def test_real_sdk_protocol_harness_calls_provider_then_investigator(
    fixtures, monkeypatch
):
    inputs = parse_input("preset")
    report = assess(fixtures, inputs)
    order = []

    def catalogue_tool():
        order.append("provider")
        return fixtures[2]

    def investigator_tool(actual_inputs, snapshot):
        order.append("investigator")
        assert actual_inputs == inputs and snapshot == fixtures[2]
        return report

    monkeypatch.setattr(provider, "load_catalogue", catalogue_tool)
    monkeypatch.setattr(agents, "assess_candidates", investigator_tool)
    result = asyncio.run(offline_recommend(inputs))
    assert result.status == "success" and order == ["provider", "investigator"]


def test_provider_timeout_is_honest_and_does_not_call_tools(monkeypatch):
    tool = Mock(side_effect=AssertionError("must not load a fabricated fallback"))
    monkeypatch.setattr(provider, "load_catalogue", tool)
    monkeypatch.setattr(agents, "assess_candidates", tool)
    result = asyncio.run(offline_recommend(parse_input("preset"), True))
    assert result.status == "error" and result.error == "timeout"
    assert result.payload_json is None
    tool.assert_not_called()


def test_catalogue_correlation_and_cleanup(fixtures):
    async def exercise():
        context = ctx()
        service = Coordinator("investigator", provider="provider")
        request = CatalogueRequest(request_id=uuid4())
        task = asyncio.create_task(
            service.request_tool(context, "provider", request, CatalogueResult)
        )
        await asyncio.sleep(0)
        good = CatalogueResult(
            request_id=request.request_id,
            status="success",
            payload_json=fixtures[2].model_dump_json(),
        )
        assert not await service.accept_result(context, "investigator", good)
        assert not await service.accept_result(ctx(), "provider", good)
        wrong = CatalogueResult(
            request_id=uuid4(), status="success", payload_json=good.payload_json
        )
        assert not await service.accept_result(context, "provider", wrong)
        wrong_type = CandidateAssessmentResult(
            request_id=request.request_id, status="error", error="timeout"
        )
        assert not await service.accept_result(context, "provider", wrong_type)
        assert await service.accept_result(context, "provider", good)
        assert await task == good
        assert not await service.accept_result(context, "provider", good)
        assert not service.pending

    asyncio.run(exercise())


def test_investigator_result_binds_inputs_and_catalogue(fixtures):
    async def exercise():
        context = ctx()
        service = Coordinator("investigator", provider="provider")
        inputs = parse_input("preset")
        report = assess(fixtures, inputs)
        request = CandidateAssessmentRequest(
            request_id=uuid4(),
            input_json=inputs.model_dump_json(),
            catalogue_json=fixtures[2].model_dump_json(),
        )
        task = asyncio.create_task(
            service.request_tool(
                context,
                "investigator",
                request,
                CandidateAssessmentResult,
                inputs=inputs,
                catalogue=fixtures[2],
            )
        )
        await asyncio.sleep(0)
        payload = report.model_dump()
        payload["catalogue"]["source_sha256"] = "a" * 64
        wrong = CandidateAssessmentResult(
            request_id=request.request_id,
            status="success",
            payload_json=Recommendation.model_validate(payload).model_dump_json(),
        )
        assert not await service.accept_result(context, "investigator", wrong)
        good = CandidateAssessmentResult(
            request_id=request.request_id,
            status="success",
            payload_json=report.model_dump_json(),
        )
        assert await service.accept_result(context, "investigator", good)
        assert await task == good

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "command",
    [
        "/recommend preset",
        "/recommend-evidence candidate-horizon 3 preset",
        "@coordinator /recommend preset",
    ],
)
def test_acp_ack_delegation_and_detail_access(fixtures, command):
    async def exercise():
        report = assess(fixtures)
        service = Coordinator("investigator", provider="provider")
        service.recommend = AsyncMock(
            return_value=CandidateAssessmentResult(
                request_id=uuid4(),
                status="success",
                payload_json=report.model_dump_json(),
            )
        )
        context = ctx()
        await service.chat(
            context, "client", ChatMessage(content=[TextContent(text=command)])
        )
        assert isinstance(context.send.call_args_list[0].args[1], ChatAcknowledgement)
        service.recommend.assert_awaited_once()
        reply = context.send.call_args.args[1].text()
        assert "HOR-03" in reply
        assert len(reply) <= policies.MAX_REPLY
        if command.startswith("/recommend-evidence "):
            with patch(
                "coverwise.agents.present_evidence",
                side_effect=policies.PolicyError("result_too_large"),
            ):
                await service.chat(
                    context, "client", ChatMessage(content=[TextContent(text=command)])
                )
            assert (
                "display unavailable: result_too_large"
                in context.send.call_args.args[1].text()
            )

    asyncio.run(exercise())


def test_provider_rejects_wrong_sender_and_invalid_catalogue(monkeypatch):
    async def exercise():
        protocols = []
        provider.install_provider(
            SimpleNamespace(include=protocols.append), "coordinator"
        )
        handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(CatalogueRequest)
        ]
        tool = Mock(side_effect=ValueError("private internals"))
        monkeypatch.setattr(provider, "load_catalogue", tool)
        context = ctx()
        request = CatalogueRequest(request_id=uuid4())
        await handler(context, "intruder", request)
        tool.assert_not_called()
        await handler(context, "coordinator", request)
        result = context.send.call_args.args[1]
        assert result.error == "catalogue_unavailable" and result.payload_json is None

    asyncio.run(exercise())


def test_versioned_catalogue_validation(fixtures, tmp_path, monkeypatch):
    data = fixtures[2].catalogue.model_dump(mode="json")
    data["products"].append(data["products"][0])
    with pytest.raises(ValueError):
        Catalogue.model_validate(data)
    path = tmp_path / "bad.json"
    path.write_text("{}")
    monkeypatch.setattr(catalogue, "CATALOGUE_PATH", path)
    with pytest.raises(policies.PolicyError, match="catalogue_unavailable"):
        load_catalogue()


@pytest.mark.parametrize("provider_seed", [None, "personal", "investigator"])
def test_provider_missing_or_duplicate_refuses_before_construction(
    provider_seed, capsys
):
    env = dict(
        ASI1_API_KEY="test",
        COVERWISE_PERSONAL_AGENT_SEED="personal",
        COVERWISE_INVESTIGATOR_AGENT_SEED="investigator",
    )
    if provider_seed is not None:
        env["COVERWISE_PROVIDER_AGENT_SEED"] = provider_seed
    with (
        patch.dict("os.environ", env, clear=True),
        patch("coverwise.live.load_dotenv"),
        patch("coverwise.live.Agent") as agent,
        patch("coverwise.live.internal_agent") as internal,
    ):
        assert live_main() == 1
        agent.assert_not_called()
        internal.assert_not_called()
    assert "refused" in capsys.readouterr().out


def test_three_seed_settings_valid():
    with patch.dict(
        "os.environ",
        dict(
            ASI1_API_KEY="test",
            COVERWISE_PERSONAL_AGENT_SEED="personal",
            COVERWISE_INVESTIGATOR_AGENT_SEED="investigator",
            COVERWISE_PROVIDER_AGENT_SEED="provider",
        ),
        clear=True,
    ):
        settings = LiveSettings.from_environment()
    assert settings.provider_seed == "provider" and settings.request_timeout == 15


@pytest.mark.parametrize(
    "field,value", [("name", "Changed Plan"), ("insurer", "Fictional Other Insurer")]
)
def test_identity_disagreement_is_not_silent(fixtures, field, value):
    root, sources, snapshot = fixtures
    payload = snapshot.model_dump(mode="json")
    payload["catalogue"]["products"][2][field] = value
    changed = (root, sources, CatalogueSnapshot.model_validate(payload))
    with pytest.raises(policies.PolicyError, match="catalogue_pdf_disagreement"):
        assess(changed)


def test_existing_wait_remains_date_dependent(fixtures):
    inputs = altered(parse_input("preset-existing"), immediate_event="2026-07-31")
    result = assess(fixtures, inputs)
    assert result.baseline[1].immediate.status == "excluded"
    assert "event inside wait" in present(result)
    assert "has an elapsed wait" not in present(result)


@pytest.mark.parametrize(
    "event,expected", [("2028-03-01", "excluded"), ("2028-03-02", "conditional")]
)
def test_new_wait_handles_leap_day(fixtures, event, expected):
    result = assess(
        fixtures,
        altered(
            parse_input("preset"),
            proposed_start="2028-02-01",
            immediate_event=event,
            later_event="2028-04-01",
        ),
    )
    assert candidate(result).first_eligible_day == date(2028, 3, 2)
    assert candidate(result).immediate.status == expected


@pytest.mark.parametrize("role", ["provider", "investigator"])
def test_tool_failure_never_fabricates_recommendation(fixtures, monkeypatch, role):
    monkeypatch.setattr(provider, "load_catalogue", Mock(return_value=fixtures[2]))
    monkeypatch.setattr(
        agents, "assess_candidates", Mock(return_value=assess(fixtures))
    )
    target = provider if role == "provider" else agents
    attribute = "load_catalogue" if role == "provider" else "assess_candidates"
    monkeypatch.setattr(
        target,
        attribute,
        Mock(
            side_effect=policies.PolicyError(
                "catalogue_unavailable"
                if role == "provider"
                else "document_unavailable"
            )
        ),
    )
    result = asyncio.run(offline_recommend(parse_input("preset")))
    assert result.status == "error" and result.payload_json is None
    if role == "provider":
        agents.assess_candidates.assert_not_called()


def test_cancellation_and_timeout_remove_pending():
    async def exercise():
        service = Coordinator("investigator", provider="provider", timeout=0.05)
        context = ctx()
        request = CatalogueRequest(request_id=uuid4())
        result = await service.request_tool(
            context, "provider", request, CatalogueResult
        )
        assert result.error == "timeout" and not service.pending
        task = asyncio.create_task(
            service.request_tool(
                context,
                "provider",
                CatalogueRequest(request_id=uuid4()),
                CatalogueResult,
            )
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not service.pending

    asyncio.run(exercise())


def timing_router(service):
    """Queued SDK-handler harness, never SDK Agent construction or transport."""
    protocols = []
    agents.install_investigator(
        SimpleNamespace(include=protocols.append), "coordinator"
    )
    provider.install_provider(SimpleNamespace(include=protocols.append), "coordinator")
    tasks, requests = [], []

    def context_for_session():
        context = ctx()

        async def send(destination, message):
            requests.append((context.session, destination, message))
            protocol = protocols[1 if destination == "provider" else 0]

            async def response(_destination, result):
                await service.accept_result(context, destination, result)

            tool_context = SimpleNamespace(session=context.session, send=response)
            handler = protocol.signed_message_handlers[
                Model.build_schema_digest(type(message))
            ]
            tasks.append(
                asyncio.create_task(handler(tool_context, "coordinator", message))
            )
            return SimpleNamespace(status=DeliveryStatus.DELIVERED)

        context.send = send
        return context

    return context_for_session, requests, tasks


def test_effective_timeout_reaches_both_stages(fixtures, monkeypatch, caplog):
    import logging

    report = assess(fixtures)
    monkeypatch.setattr(provider, "load_catalogue", lambda: fixtures[2])
    monkeypatch.setattr(agents, "assess_candidates", lambda *_: report)

    async def exercise():
        env = dict(
            ASI1_API_KEY="PRIVATE-KEY",
            COVERWISE_PERSONAL_AGENT_SEED="PRIVATE-1",
            COVERWISE_INVESTIGATOR_AGENT_SEED="PRIVATE-2",
            COVERWISE_PROVIDER_AGENT_SEED="PRIVATE-3",
            COVERWISE_REQUEST_TIMEOUT_SECONDS="0.23",
        )
        with patch.dict("os.environ", env, clear=True):
            settings = LiveSettings.from_environment()
        service = Coordinator(
            "investigator", provider="provider", timeout=settings.request_timeout
        )
        context_for, requests, tasks = timing_router(service)
        actual_timeout = asyncio.timeout
        deadlines = []

        def observed_timeout(delay):
            deadlines.append(delay)
            return actual_timeout(delay)

        with (
            caplog.at_level(logging.INFO, logger="coverwise"),
            patch("coverwise.agents.asyncio.timeout", side_effect=observed_timeout),
        ):
            result = await service.recommend(context_for(), report.inputs)
        await asyncio.gather(*tasks)
        assert result.status == "success"
        assert deadlines == [settings.request_timeout, settings.request_timeout]
        assert [r[1] for r in requests] == ["provider", "investigator"]
        assert not service.pending
        assert "stage=provider_catalogue deadline_s=0.230" in caplog.text
        assert "stage=investigator_assessment deadline_s=0.230" in caplog.text
        assert "PRIVATE" not in caplog.text and "1992-04-10" not in caplog.text

    asyncio.run(exercise())


def test_timeout_late_response_reason_and_recovery(fixtures, monkeypatch, caplog):
    import logging
    import time

    report = assess(fixtures)
    slow = [True]
    monkeypatch.setattr(provider, "load_catalogue", lambda: fixtures[2])

    def work(*_):
        if slow[0]:
            time.sleep(0.12)
        return report

    monkeypatch.setattr(agents, "assess_candidates", work)

    async def exercise():
        service = Coordinator("investigator", provider="provider", timeout=0.05)
        context_for, requests, tasks = timing_router(service)
        context = context_for()
        with caplog.at_level(logging.INFO, logger="coverwise"):
            result = await service.recommend(context, report.inputs)
            assert result.error == "timeout" and not service.pending
            expired = requests[-1][2].request_id
            assert service.closed[expired] == ("expired", "investigator_assessment")
            await asyncio.gather(*tasks)
            assert f"request_id={expired} outcome=ignored_response" in caplog.text
            assert "reason=expired" in caplog.text
            assert "stage=investigator_assessment deadline_s=0.050" in caplog.text
            assert "event=pending_cleanup" in caplog.text
            assert "outcome=test_silence" not in caplog.text
            slow[0] = False
            assert (await service.recommend(context, report.inputs)).status == "success"
            await asyncio.gather(*tasks)
        assert not service.pending

    asyncio.run(exercise())


def test_normal_recovery_after_intentional_provider_timeout(
    fixtures, monkeypatch, caplog
):
    import logging

    report = assess(fixtures)
    monkeypatch.setattr(provider, "load_catalogue", lambda: fixtures[2])
    monkeypatch.setattr(agents, "assess_candidates", lambda *_: report)

    async def exercise():
        service = Coordinator("investigator", provider="provider", timeout=0.05)
        context_for, requests, tasks = timing_router(service)
        context = context_for()
        with caplog.at_level(logging.INFO, logger="coverwise"):
            assert (
                await service.recommend(context, report.inputs, test_timeout=True)
            ).error == "timeout"
            assert len(requests) == 1 and not service.pending
            assert (await service.recommend(context, report.inputs)).status == "success"
            await asyncio.gather(*tasks)
        assert "outcome=test_silence" in caplog.text and "injection=True" in caplog.text
        assert not service.pending

    asyncio.run(exercise())


def test_repeated_concurrent_requests_keep_inputs_and_sessions(fixtures, monkeypatch):
    monkeypatch.setattr(provider, "load_catalogue", lambda: fixtures[2])
    monkeypatch.setattr(
        agents, "assess_candidates", lambda inputs, _: assess(fixtures, inputs)
    )

    async def exercise():
        service = Coordinator("investigator", provider="provider", timeout=3)
        context_for, requests, tasks = timing_router(service)
        inputs = [parse_input(p) for p in ("preset", "preset-low", "preset-existing")]
        results = await asyncio.gather(
            *(service.recommend(context_for(), i) for i in inputs)
        )
        await asyncio.gather(*tasks)
        reports = [Recommendation.model_validate_json(r.payload_json) for r in results]
        assert [r.inputs for r in reports] == inputs
        assert [r.outcome for r in reports] == [
            "shortlist",
            "no_suitable_option",
            "keep_existing_obtain_terms",
        ]
        assert len({r[0] for r in requests}) == 3
        assert len({r[2].request_id for r in requests}) == 6
        assert not service.pending

    asyncio.run(exercise())


def test_slow_packaging_does_not_block_async_work(fixtures, monkeypatch):
    import threading
    import time

    report = assess(fixtures)
    monkeypatch.setattr(agents, "assess_candidates", lambda *_: report)
    packaging_started, packaging_finished = threading.Event(), threading.Event()
    original = agents.present_recommendation

    def packaging(value):
        packaging_started.set()
        time.sleep(0.1)
        packaging_finished.set()
        return original(value)

    monkeypatch.setattr(agents, "present_recommendation", packaging)

    async def exercise():
        protocols = []
        agents.install_investigator(
            SimpleNamespace(include=protocols.append), "coordinator"
        )
        handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(CandidateAssessmentRequest)
        ]
        request = CandidateAssessmentRequest(
            request_id=uuid4(),
            input_json=report.inputs.model_dump_json(),
            catalogue_json=fixtures[2].model_dump_json(),
        )
        task = asyncio.create_task(handler(ctx(), "coordinator", request))
        async with asyncio.timeout(2):
            while not packaging_started.is_set():
                await asyncio.sleep(0.001)
            await asyncio.sleep(0.01)
            responsive = not packaging_finished.is_set()
            await task
        assert responsive

    asyncio.run(exercise())


def test_cancelled_handler_keeps_worker_lane_until_real_completion(
    fixtures, monkeypatch
):
    import threading

    report = assess(fixtures)
    started, release = threading.Event(), threading.Event()
    calls = []

    def work(*_):
        calls.append(1)
        if len(calls) == 1:
            started.set()
            assert release.wait(2)
        return report

    monkeypatch.setattr(agents, "assess_candidates", work)

    async def exercise():
        protocols = []
        agents.install_investigator(
            SimpleNamespace(include=protocols.append), "coordinator"
        )
        handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(CandidateAssessmentRequest)
        ]

        def request():
            return CandidateAssessmentRequest(
                request_id=uuid4(),
                input_json=report.inputs.model_dump_json(),
                catalogue_json=fixtures[2].model_dump_json(),
            )

        first_context, second_context = ctx(), ctx()
        first = asyncio.create_task(handler(first_context, "coordinator", request()))
        second = None
        try:
            async with asyncio.timeout(2):
                while not started.is_set():
                    await asyncio.sleep(0.001)
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
                second = asyncio.create_task(
                    handler(second_context, "coordinator", request())
                )
                await asyncio.sleep(0.02)
                assert len(calls) == 1
                release.set()
                await second
            first_context.send.assert_not_called()
            assert second_context.send.call_args.args[1].status == "success"
        finally:
            release.set()
            await asyncio.gather(
                first, *([second] if second else []), return_exceptions=True
            )

    asyncio.run(exercise())


def test_response_ignore_reasons_and_bounded_history(caplog):
    import logging
    from time import monotonic

    from coverwise.agents import RECENT_REQUESTS, Pending

    async def exercise():
        service = Coordinator("investigator", provider="provider")
        context = ctx()
        request_id = uuid4()
        future = asyncio.get_running_loop().create_future()
        slot = agents.Pending(
            context.session,
            future,
            CatalogueResult,
            sender="provider",
            deadline=monotonic() + 2,
        )
        service.pending[request_id] = slot
        result = CatalogueResult(
            request_id=request_id, status="error", error="catalogue_unavailable"
        )
        with caplog.at_level(logging.INFO, logger="coverwise"):
            assert not await service.accept_result(context, "intruder", result)
            assert not await service.accept_result(ctx(), "provider", result)
            slot.deadline = monotonic() - 1
            assert not await service.accept_result(context, "provider", result)
            assert not future.done()  # Expired replies cannot win a delayed timer race.
            slot.deadline = monotonic() + 2
            future.cancel()
            assert not await service.accept_result(context, "provider", result)
            service.finish(context, request_id, "cancelled")
            assert not await service.accept_result(context, "provider", result)
            unknown = CatalogueResult(
                request_id=uuid4(), status="error", error="catalogue_unavailable"
            )
            assert not await service.accept_result(context, "provider", unknown)
            for _ in range(RECENT_REQUESTS + 1):
                identifier = uuid4()
                service.pending[identifier] = Pending(
                    context.session, asyncio.get_running_loop().create_future()
                )
                service.finish(context, identifier, "cancelled")
        assert len(service.closed) == RECENT_REQUESTS
        for reason in (
            "sender_mismatch",
            "session_mismatch",
            "expired",
            "cancelled",
            "unknown_id",
        ):
            assert "reason=" + reason in caplog.text

    asyncio.run(exercise())
