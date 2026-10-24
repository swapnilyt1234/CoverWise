import asyncio
import logging
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
from coverwise.contracts import PolicyDocument
from coverwise.policies import (
    PolicyError,
    load_policy,
    parse_pages,
    present,
    verify_evidence,
)
from coverwise.transport import (
    DiagnosticRequest,
    PolicyInspectionRequest,
    PolicyInspectionResult,
    diagnose,
)


def sample_report(pages=None):
    pages = pages or ["EMP-01 | Deductible: None. [END EMP-01]"]
    document = PolicyDocument(
        document_id="existing-employer",
        document_version="1",
        sha256="a" * 64,
        source_type="pdf",
        title="Fictional unit-test report, not extracted PDF evidence",
    )
    return parse_pages(document, pages)


def context():
    return SimpleNamespace(
        agent=SimpleNamespace(address="unit-coordinator"),
        session=uuid4(),
        send=AsyncMock(return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)),
    )


def test_rule_statuses_and_verified_evidence():
    pages = [
        "EMP-01 | Deductible: None. [END EMP-01]\n"
        "EMP-02 | Room rent: UNCONFIRMED: schedule absent. [END EMP-02]",
        "EMP-03 | Deductible: 100 INR paise. [END EMP-03]",
    ]
    report = sample_report(pages)
    terms = {term.name: term for term in report.terms}
    assert terms["Deductible"].status == "conflict"
    assert len(terms["Deductible"].evidence) == 2
    assert {e.locator.page for e in terms["Deductible"].evidence} == {1, 2}
    assert terms["Room rent"].status == "ambiguous"
    assert terms["Renewal date"].status == "not_stated"
    assert terms["Renewal date"].value is None
    assert terms["Renewal date"].evidence == []
    verify_evidence(report, pages)
    terms["Deductible"].evidence[0].excerpt = "Invented text"
    with pytest.raises(PolicyError, match="evidence_mismatch"):
        verify_evidence(report, pages)


def test_explicit_none_and_normalization_are_distinct_from_missing():
    report = sample_report(["EMP-01 | Deductible:\n  None.\t[END EMP-01]"])
    terms = {term.name: term for term in report.terms}
    assert terms["Deductible"].value == "None."
    assert terms["Deductible"].status == "stated"
    assert terms["Co-payment"].value is None
    assert terms["Co-payment"].status == "not_stated"
    assert report == sample_report(["EMP-01 | Deductible: None. [END EMP-01]"])
    assert len(present(report)) <= policies.MAX_REPLY


@pytest.mark.parametrize(
    "policy_id",
    ["../existing-employer", "C:/policy.pdf", "https://example.test/a", "unknown", ""],
)
def test_registry_rejects_ids_before_opening_files(policy_id, monkeypatch):
    monkeypatch.setattr(
        policies.Path, "open", Mock(side_effect=AssertionError("no reads"))
    )
    with pytest.raises(PolicyError, match="unknown_policy_id"):
        load_policy(policy_id)


@pytest.mark.parametrize(
    "data, code",
    [
        (b"not a PDF", "malformed_pdf"),
        (b"%PDF-" + b"x" * policies.MAX_BYTES, "oversized_file"),
    ],
    ids=["malformed-header", "oversized"],
)
def test_bounded_file_rejection_without_pdf_dependency(
    tmp_path, monkeypatch, data, code
):
    monkeypatch.setattr(policies, "PDF_DIR", tmp_path)
    (tmp_path / "existing-employer.pdf").write_bytes(data)
    with pytest.raises(PolicyError, match=code):
        load_policy("existing-employer")


@pytest.mark.parametrize(
    "failure", [PolicyError("malformed_pdf"), RuntimeError("private document data")]
)
def test_investigator_failures_are_errors_without_findings(
    monkeypatch, caplog, failure
):
    async def exercise():
        protocols = []
        install_investigator(SimpleNamespace(include=protocols.append), "coordinator")
        callback = protocols[0].signed_message_handlers[
            Model.build_schema_digest(PolicyInspectionRequest)
        ]
        inspect = Mock(side_effect=failure)
        monkeypatch.setattr(agents, "inspect_policy", inspect)
        ctx = context()
        request = PolicyInspectionRequest(
            request_id=uuid4(), policy_id="existing-employer"
        )
        with caplog.at_level(logging.INFO, logger="coverwise"):
            await callback(ctx, "intruder", request)
            inspect.assert_not_called()
            await callback(ctx, "coordinator", request)
        result = ctx.send.call_args.args[1]
        assert result.status == "error" and result.report_json is None
        assert result.error in ("malformed_pdf", "extraction_failed")
        assert "private document data" not in caplog.text

    asyncio.run(exercise())


def test_policy_correlation_and_type_do_not_accept_diagnostic_or_wrong_policy():
    async def exercise():
        service = Coordinator("investigator")
        ctx = context()
        task = asyncio.create_task(
            service.delegate(ctx, "", policy_id="existing-employer")
        )
        await asyncio.sleep(0)
        request = ctx.send.call_args.args[1]
        diagnostic = diagnose(
            DiagnosticRequest(request_id=request.request_id, text="x")
        )
        assert not await service.accept_result(ctx, "investigator", diagnostic)
        fields = dict(
            request_id=request.request_id,
            status="success",
            report_json=sample_report().model_dump_json(),
        )
        wrong = PolicyInspectionResult(policy_id="existing-personal", **fields)
        assert not await service.accept_result(ctx, "investigator", wrong)
        correct = PolicyInspectionResult(policy_id="existing-employer", **fields)
        assert not await service.accept_result(ctx, "intruder", correct)
        assert await service.accept_result(ctx, "investigator", correct)
        assert await task == correct
        assert not await service.accept_result(ctx, "investigator", correct)
        assert not service.pending

    asyncio.run(exercise())


def test_policy_timeout_returns_no_findings_and_cleans_pending():
    async def exercise():
        service = Coordinator("investigator", timeout=0.05)
        result = await service.delegate(context(), "", policy_id="existing-employer")
        assert isinstance(result, PolicyInspectionResult)
        assert result.status == "error" and result.error == "timeout"
        assert result.report_json is None
        assert not service.pending

    asyncio.run(exercise())


@pytest.mark.parametrize("mention", [False, True])
def test_policy_commands_use_delegation_and_readable_presentation(mention):
    async def exercise():
        service = Coordinator(
            "investigator", explainer=SimpleNamespace(explain=AsyncMock())
        )
        ctx = context()
        prefix = "@unit-coordinator " if mention else ""
        service.delegate = AsyncMock(
            return_value=PolicyInspectionResult(
                request_id=uuid4(),
                policy_id="existing-employer",
                status="success",
                report_json=sample_report().model_dump_json(),
            )
        )
        await service.chat(
            ctx, "client", ChatMessage(content=[TextContent(text=prefix + "/policies")])
        )
        service.delegate.assert_not_called()
        assert "existing-employer" in ctx.send.call_args.args[1].text()
        await service.chat(
            ctx,
            "client",
            ChatMessage(
                content=[TextContent(text=prefix + "/inspect existing-employer")]
            ),
        )
        service.delegate.assert_awaited_once_with(
            ctx, "", policy_id="existing-employer"
        )
        reply = ctx.send.call_args.args[1].text()
        assert "Deductible: stated" in reply and "p1, EMP-01" in reply
        assert "Renewal date: not_stated" in reply
        assert not reply.startswith("{")
        assert isinstance(ctx.send.call_args_list[0].args[1], ChatAcknowledgement)
        service.explainer.explain.assert_not_called()

    asyncio.run(exercise())
