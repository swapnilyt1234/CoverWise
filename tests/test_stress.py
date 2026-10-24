import asyncio
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from uagents import Model
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
)
from uagents_core.types import DeliveryStatus

from coverwise import agents, policies
from coverwise.agents import Coordinator, install_investigator
from coverwise.generate_policies import generate
from coverwise.money import display_money, inr
from coverwise.stress import (
    Comparison,
    assess,
    compare,
    interpret,
    parse_input,
    present_comparison,
)
from coverwise.transport import StressTestRequest, StressTestResult


@pytest.fixture
def pdfs(tmp_path, monkeypatch):
    monkeypatch.setattr(policies, "PDF_DIR", tmp_path)
    sources = {}
    for policy_id, spec in policies.REGISTRY.items():
        source = json.loads(
            (policies.ROOT / "fixtures" / "policies" / f"{policy_id}.json").read_text(
                encoding="utf-8"
            )
        )
        sources[policy_id] = source
        generate(source, tmp_path / spec.filename)
    return tmp_path, sources


def reports():
    return [policies.load_policy(p) for p in policies.REGISTRY]


def scenario(
    event="2027-01-15", final="2026-12-31", new="2027-02-01", member="member-01"
):
    return parse_input(f"{member} {final} {new} {event} illness_hospitalization")


def change(pdfs, policy, name, value):
    root, sources = pdfs
    clauses = [c for p in sources[policy]["pages"] for c in p["clauses"]]
    next(c for c in clauses if c["term"] == name)["value"] = value
    generate(sources[policy], root / policies.REGISTRY[policy].filename)


def finding(assessment, name):
    return next(f for f in assessment.findings if f.check == name)


@pytest.mark.parametrize(
    "event,outcome", [("2026-12-31", "pass"), ("2027-01-01", "excluded")]
)
def test_employer_last_and_first_day(pdfs, event, outcome):
    report = reports()[0]
    result = assess(report, scenario(event), interpret(report))
    assert finding(result, "termination").outcome == outcome
    assert finding(result, "period").outcome == outcome


def test_expiry_independent_of_termination(pdfs):
    change(
        pdfs,
        "existing-employer",
        "Policy dates",
        "2026-01-01 through 2026-12-15 inclusive; subject to employment termination.",
    )
    result = compare(scenario("2026-12-16"), reports())
    employer = result.assessments[0]
    assert finding(employer, "period").outcome == "excluded"
    assert finding(employer, "termination").outcome == "pass"
    assert result.employer_last_day == date(2026, 12, 15)
    assert result.gap.start == date(2026, 12, 16)


@pytest.mark.parametrize(
    "event,outcome", [("2026-12-15", "pass"), ("2026-12-16", "excluded")]
)
def test_termination_independent_of_expiry(pdfs, event, outcome):
    change(
        pdfs,
        "existing-employer",
        "Employment termination",
        "Coverage for both members ends on Demo A's final employment date, "
        "2026-12-15 inclusive, or policy expiry if earlier. "
        "No conversion or continuity benefit.",
    )
    result = compare(scenario(event, final="2026-12-15"), reports())
    employer = result.assessments[0]
    assert finding(employer, "termination").outcome == outcome
    assert finding(employer, "period").outcome == "pass"
    assert result.employer_last_day == date(2026, 12, 15)


@pytest.mark.parametrize(
    "event,outcome", [("2027-06-30", "pass"), ("2027-07-01", "excluded")]
)
def test_personal_expiry_endpoints(pdfs, event, outcome):
    result = compare(scenario(event), reports())
    assert finding(result.assessments[1], "period").outcome == outcome


@pytest.mark.parametrize(
    "name", ["Employment termination", "Policy dates", "Covered members", "Exclusions"]
)
def test_relevant_unknown_wording(pdfs, name):
    change(pdfs, "existing-employer", name, "See missing schedule.")
    result = compare(scenario("2026-12-31"), reports())
    assert result.assessments[0].status == "insufficient_information"
    assert any("unrecognized" in m for m in result.assessments[0].missing_information)


def test_assessment_rejects_foreign_evidence(pdfs):
    result = compare(scenario(), reports()).model_dump()
    result["assessments"][0]["findings"][0]["evidence_ids"] = ["foreign"]
    with pytest.raises(ValueError, match="foreign evidence"):
        Comparison.model_validate(result)


@pytest.mark.parametrize(
    "event,outcome",
    [
        ("2026-06-30", "pass"),
        ("2026-07-01", "excluded"),
        ("2026-07-31", "excluded"),
        ("2026-08-01", "pass"),
    ],
)
def test_waiting_boundaries(pdfs, event, outcome):
    report = reports()[1]
    result = assess(report, scenario(event), interpret(report))
    assert finding(result, "waiting").outcome == outcome
    if event == "2026-08-01":
        assert "elapsed" in finding(result, "waiting").detail
        assert result.temporal == "passes"
        assert result.status == "insufficient_information"
    if event == "2026-06-30":
        assert result.status == "excluded"  # Before policy inception.


def test_member_not_listed(pdfs):
    result = compare(scenario(member="member-99"), reports())
    assert all(a.status == "excluded" for a in result.assessments)
    assert all(finding(a, "member").evidence_ids for a in result.assessments)


@pytest.mark.parametrize(
    "kind", ["missing", "conflict", "unrecognized", "ambiguous", "invalid_date"]
)
def test_unknown_terms_are_not_rules(pdfs, kind):
    root, sources = pdfs
    source = sources["existing-personal"]
    clauses = source["pages"][2]["clauses"]
    clause = next(c for c in clauses if c["term"] == "Waiting period")
    if kind == "missing":
        clauses.remove(clause)
    elif kind == "conflict":
        clauses.append({**clause, "value": "Illness wait waived."})
    else:
        clause["value"] = {
            "unrecognized": "Illness wait waived.",
            "ambiguous": "UNCONFIRMED: illness wait.",
            "invalid_date": "Initial illness waiting interval is 2026-07-31 "
            "through 2026-07-01 inclusive. No continuity credit or waiver is granted.",
        }[kind]
    generate(source, root / "existing-personal.pdf")
    report = reports()[1]
    rules = interpret(report)
    assert rules.waiting.value is None
    result = assess(report, scenario(), rules)
    assert result.status == "insufficient_information"
    assert result.temporal == "unknown"
    assert any("Waiting period" in m for m in result.missing_information)


def test_mismatch_requests_correction(pdfs):
    report = compare(scenario(final="2026-12-30"), reports())
    assert report.assessments[0].temporal == "correction_required"
    assert report.assessments[0].status == "insufficient_information"
    assert "Correct" in report.assessments[0].next_action
    assert not report.gap_known and report.gap is None
    assert "PDF not overridden" in present_comparison(report)


def test_no_gap_contiguous_and_same_scenario(pdfs):
    s = scenario(new="2027-01-01")
    assert s.profile_id is None
    result = compare(s, reports())
    assert result.gap_known and result.gap is None
    assert result.scenario == s
    assert all(a.scenario_id == s.scenario_id for a in result.assessments)
    assert "Same member and dates" in present_comparison(result)


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "member-01 2026-12-31 2026-12-31 2027-01-15 illness_hospitalization",
        "member-01 2026-12-31 2026-12-30 2027-01-15 illness_hospitalization",
        "member-01 2026-12-31 2027-02-01 2027-02-30 illness_hospitalization",
        "member-01 20261231 2027-02-01 2027-01-15 illness_hospitalization",
        "member-01 2026-12-31 2027-02-01 2027-01-15 accident",
        "x" * 513,
    ],
)
def test_invalid_inputs_actionable(payload):
    with pytest.raises(ValueError, match="/stress-test"):
        parse_input(payload)


def test_actual_pdf_change_changes_decision_hash_and_evidence(pdfs):
    before = compare(scenario(), reports())
    change(
        pdfs,
        "existing-personal",
        "Waiting period",
        "Initial illness waiting interval is 2026-07-01 through 2027-01-31 "
        "inclusive. No continuity credit or waiver is granted.",
    )
    after = compare(scenario(), reports())
    assert before.assessments[1].status == "insufficient_information"
    assert after.assessments[1].status == "excluded"
    assert before.inspections[1].document.sha256 != after.inspections[1].document.sha256
    assert (
        finding(before.assessments[1], "waiting").evidence_ids
        != finding(after.assessments[1], "waiting").evidence_ids
    )


def test_explicit_illness_exclusion(pdfs):
    change(
        pdfs, "existing-personal", "Exclusions", "Illness hospitalization is excluded."
    )
    result = compare(scenario(), reports())
    assert result.assessments[1].status == "excluded"
    assert finding(result.assessments[1], "exclusions").outcome == "excluded"


@pytest.mark.parametrize(
    "paise,expected",
    [
        (100000000, "₹10,00,000"),
        (20000000, "₹2,00,000"),
        (300000, "₹3,000"),
        (600000, "₹6,000"),
        (101, "₹1.01"),
        (1, "₹0.01"),
        (0, "₹0"),
        (123456789, "₹12,34,567.89"),
    ],
)
def test_inr(paise, expected):
    assert inr(paise) == expected
    assert display_money(f"{paise} INR paise/day") == expected + "/day"
    assert display_money(f"{paise} INR paise/year") == expected + "/year"


def test_presentation_keeps_evidence_and_material_limits(pdfs):
    result = compare(parse_input("preset"), reports())
    original = result.model_dump_json()
    text = present_comparison(result)
    assert "₹2,00,000" in text and "shared family" in text
    assert "₹3,000/day maximum room reimbursement" in text
    assert "other events are not specified" in text
    assert "2027-01-01 through 2027-01-31" in text
    assert len(text) <= policies.MAX_REPLY
    assert result.model_dump_json() == original
    inspection = policies.present(result.inspections[1])
    assert "₹6,000/year, total annual premium for both members" in inspection
    assert "600000 INR paise" in original
    assert "not guaranteed coverage" in text
    assert "automatically stacked" in text


def context():
    return SimpleNamespace(
        agent=SimpleNamespace(address="test-coordinator"),
        session=uuid4(),
        send=AsyncMock(return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)),
    )


def test_sdk_delegation_correlation_and_scenario_binding(pdfs):
    async def exercise():
        ctx = context()
        service = Coordinator("investigator")
        s = parse_input("preset")
        task = asyncio.create_task(service.delegate(ctx, "", scenario=s))
        await asyncio.sleep(0)
        request = ctx.send.call_args.args[1]
        assert isinstance(request, StressTestRequest)
        assert json.loads(request.scenario_json) == s.model_dump(mode="json")
        report = compare(s, reports())
        result = StressTestResult(
            request_id=request.request_id,
            status="success",
            report_json=report.model_dump_json(),
        )
        assert not await service.accept_result(ctx, "intruder", result)
        assert not await service.accept_result(context(), "investigator", result)
        changed = compare(scenario("2026-12-31"), reports())
        wrong = StressTestResult(
            request_id=request.request_id,
            status="success",
            report_json=changed.model_dump_json(),
        )
        assert not await service.accept_result(ctx, "investigator", wrong)
        assert await service.accept_result(ctx, "investigator", result)
        assert await task == result
        assert not await service.accept_result(ctx, "investigator", result)
        assert not service.pending

    asyncio.run(exercise())


@pytest.mark.parametrize("mention", [False, True])
def test_stress_command_ack_and_delegation(pdfs, mention):
    async def exercise():
        ctx = context()
        service = Coordinator(
            "investigator", explainer=SimpleNamespace(explain=AsyncMock())
        )
        s = parse_input("preset")
        report = compare(s, reports())
        service.delegate = AsyncMock(
            return_value=StressTestResult(
                request_id=uuid4(),
                status="success",
                report_json=report.model_dump_json(),
            )
        )
        prefix = "@test-coordinator " if mention else ""
        await service.chat(
            ctx,
            "client",
            ChatMessage(content=[TextContent(text=prefix + "/stress-test preset")]),
        )
        assert isinstance(ctx.send.call_args_list[0].args[1], ChatAcknowledgement)
        service.delegate.assert_awaited_once_with(ctx, "", scenario=s)
        assert "Employer protection last day" in ctx.send.call_args.args[1].text()
        service.explainer.explain.assert_not_called()

    asyncio.run(exercise())


def test_investigator_owns_engine_and_rejects_invalid_requests(pdfs, monkeypatch):
    async def exercise():
        protocols = []
        install_investigator(SimpleNamespace(include=protocols.append), "coordinator")
        handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(StressTestRequest)
        ]
        ctx = context()
        s = parse_input("preset")
        engine = Mock(return_value=compare(s, reports()))
        monkeypatch.setattr(agents, "run_stress", engine)
        request = StressTestRequest(
            request_id=uuid4(), scenario_json=s.model_dump_json()
        )
        await handler(ctx, "intruder", request)
        engine.assert_not_called()
        await handler(ctx, "coordinator", request)
        engine.assert_called_once_with(s)
        assert (
            Comparison.model_validate_json(
                ctx.send.call_args.args[1].report_json
            ).scenario
            == s
        )
        await handler(
            ctx,
            "coordinator",
            StressTestRequest(request_id=uuid4(), scenario_json="{}"),
        )
        assert ctx.send.call_args.args[1].error == "invalid_scenario"

    asyncio.run(exercise())
