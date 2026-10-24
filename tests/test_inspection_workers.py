"""Card confirmation through real coordinator/Investigator handlers and PDF children."""

import asyncio
import hashlib
import logging
from time import monotonic

import pytest
from pypdf import PdfReader
from test_cards import click, harness, open_form, payload
from test_sandbox import insurer as insurer

from coverwise import agents, policies
from coverwise.transport import PolicyInspectionRequest, PolicyInspectionResult


def inspection_workers(monkeypatch, *, startup_delay=0, extraction_delay=0):
    # Harness normally substitutes load_policy; restore the production parent.
    monkeypatch.setattr(agents, "inspect_policy", policies.inspect_policy)
    popen = policies.subprocess.Popen
    children = []
    delays = dict(startup=startup_delay, extraction=extraction_delay)

    def launch(command, **kwargs):
        script = (
            "import sys,time; from pathlib import Path; "
            "from coverwise import policies; "
            "policies.PDF_DIR=Path(sys.argv.pop(1)); "
            f"time.sleep({delays['startup']}); "
            "original=policies.load_policy; "
            "policies.load_policy=lambda p: "
            "((policies.PDF_DIR/'extracting').touch(), "
            f"time.sleep({delays['extraction']}), original(p))[2]; "
            "raise SystemExit(policies.main())"
        )
        child = popen(
            [command[0], "-c", script, str(policies.PDF_DIR), *command[3:]],
            **kwargs,
        )
        children.append(child)
        return child

    monkeypatch.setattr(policies.subprocess, "Popen", launch)
    return children, delays


async def job_review(h):
    form = await open_form(h, "job")
    await click(
        h,
        form["submit_cta"],
        dict(
            final_employment="2026-12-31",
            new_cover_known="known",
            new_start="2027-02-01",
            current_cover="unsure",
            policy="existing-employer",
        ),
    )
    kind, review = payload(h)
    assert kind == "review" and not h.requests
    return review


def assert_reaped(children):
    assert children
    assert all(p.poll() is not None and p.stdout.closed for p in children)
    assert all(p.stdin is None or p.stdin.closed for p in children)


@pytest.mark.parametrize("startup_delay", [0, 2.1])
def test_job_confirmation_uses_real_isolated_evidence(
    insurer, monkeypatch, caplog, startup_delay
):
    caplog.set_level(logging.INFO, logger="coverwise")

    async def run():
        h = harness(insurer, monkeypatch)
        children, _ = inspection_workers(monkeypatch, startup_delay=startup_delay)
        try:
            review = await job_review(h)
            started = monotonic()
            await click(h, review["approve_cta"])
            print(f"job_confirm_ms={(monotonic() - started) * 1000:.3f}")
            result = h.results[-1]
            assert isinstance(h.requests[-1], PolicyInspectionRequest)
            assert isinstance(result, PolicyInspectionResult)
            assert result.status == "success", result.error
            report = policies.PolicyInspection.model_validate_json(result.report_json)
            path = policies.PDF_DIR / policies.REGISTRY["existing-employer"].filename
            assert (
                report.document.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
            )
            pages = [p.extract_text() for p in PdfReader(path).pages]
            policies.verify_evidence(report, pages)
            assert any(
                e.clause_id == "EMP-02" for t in report.terms for e in t.evidence
            )
            kind, card = payload(h)
            assert kind == "detail" and "EMP-02" in str(card)
            assert "31 days" in str(card)
            assert not h.service.pending and not h.model_calls
            assert insurer.store.counts()["quotes"] == 0
            assert insurer.store.counts()["payments"] == 0
            assert_reaped(children)
        finally:
            await h.close()

    asyncio.run(run())
    timings = [
        r.getMessage() for r in caplog.records if "pdf_worker_timing" in r.message
    ]
    assert any(
        "stage=pdf_worker_startup" in m and "outcome=ready" in m for m in timings
    )
    assert any("stage=pdf_extraction" in m and "deadline_s=2.000" in m for m in timings)
    if startup_delay:
        startup = next(m for m in timings if "stage=pdf_worker_startup" in m)
        assert 2000 < float(startup.split("elapsed_ms=")[1].split()[0]) < 5000
    print("\n".join(timings))


@pytest.mark.parametrize("failure", ["startup", "extraction", "malformed"])
def test_failed_job_preserves_draft_and_issues_working_retry(
    insurer, monkeypatch, caplog, failure
):
    caplog.set_level(logging.INFO, logger="coverwise")

    async def run():
        h = harness(insurer, monkeypatch)
        children, delays = inspection_workers(
            monkeypatch,
            startup_delay=5.1 if failure == "startup" else 0,
            extraction_delay=2.1 if failure == "extraction" else 0,
        )
        path = policies.PDF_DIR / "existing-employer.pdf"
        original = path.read_bytes()
        if failure == "malformed":
            path.write_bytes(b"%PDF-1.7\nbroken")
        try:
            review = await job_review(h)
            old_token = review["approve_cta"]["selection"]["card_token"]
            draft = h.service.cards.actions[old_token].data
            await click(h, review["approve_cta"])
            error = h.results[-1]
            assert error.status == "error" and error.report_json is None
            assert error.error == (
                "malformed_pdf" if failure == "malformed" else "extraction_timeout"
            )
            kind, retry = payload(h)
            assert (
                kind == "review" and "Your details are saved" in h.messages[-1].text()
            )
            assert retry["summary_rows"] == review["summary_rows"]
            token = retry["approve_cta"]["selection"]["card_token"]
            action = h.service.cards.actions[token]
            assert token != old_token and not action.used
            assert action.kind == "job_confirm" and action.data == draft
            assert action.scope == ("client", insurer.session)
            session = h.service.cards.sessions[action.scope]
            assert session.stage == action.source_stage == "job_review"
            assert action.epoch == session.epoch
            assert action.expires > h.service.cards.timer()
            assert not h.service.pending
            assert_reaped(children)
            assert (policies.PDF_DIR / "extracting").exists() == (failure != "startup")
            assert "fallback_reason=inspection_unavailable" in caplog.text

            # The failed one-shot action stays consumed; only the new token retries.
            await click(h, review["approve_cta"])
            assert len(h.requests) == 1 and len(children) == 1
            delays.update(startup=0, extraction=0)
            path.write_bytes(original)
            await click(h, retry["approve_cta"])
            assert h.results[-1].status == "success"
            assert len(h.requests) == len(children) == 2
            assert payload(h)[0] == "detail" and "EMP-02" in str(payload(h)[1])
            assert insurer.store.counts()["quotes"] == 0
            assert insurer.store.counts()["payments"] == 0
            assert_reaped(children)
        finally:
            await h.close()

    asyncio.run(run())
    timings = [
        r.getMessage() for r in caplog.records if "pdf_worker_timing" in r.message
    ]
    if failure != "malformed":
        stage = "pdf_worker_startup" if failure == "startup" else "pdf_extraction"
        assert any(
            f"stage={stage}" in m and "outcome=extraction_timeout" in m for m in timings
        )
    print(f"failure={failure}\n" + "\n".join(timings))


def test_cancelled_job_handler_still_reaps_bounded_pdf_child(
    insurer, monkeypatch, caplog
):
    caplog.set_level(logging.INFO, logger="coverwise")

    async def run():
        h = harness(insurer, monkeypatch)
        children, _ = inspection_workers(monkeypatch, extraction_delay=2.1)
        review = await job_review(h)
        confirmation = asyncio.create_task(click(h, review["approve_cta"]))
        try:
            async with asyncio.timeout(6):
                while not (policies.PDF_DIR / "extracting").exists():
                    await asyncio.sleep(0.01)
            h.tasks[-1].cancel()
            with pytest.raises(asyncio.CancelledError):
                await h.tasks[-1]
            confirmation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await confirmation
            assert not h.service.pending and not h.results
            # Cancelling to_thread does not stop its thread; its deadline still reaps.
            async with asyncio.timeout(4):
                while children[0].poll() is None or not children[0].stdout.closed:
                    await asyncio.sleep(0.01)
            assert_reaped(children)
            assert insurer.store.counts()["payments"] == 0
        finally:
            confirmation.cancel()
            await asyncio.gather(confirmation, *h.tasks, return_exceptions=True)
            await h.http.aclose()

    asyncio.run(run())
    assert "stage=pdf_extraction" in caplog.text
    assert "outcome=extraction_timeout" in caplog.text


@pytest.mark.parametrize("policy_id", ["existing-personal", "candidate-horizon"])
def test_inspect_command_uses_same_isolated_worker(insurer, monkeypatch, policy_id):
    async def run():
        h = harness(insurer, monkeypatch)
        children, _ = inspection_workers(monkeypatch)
        try:
            reply = await h.ask("/inspect " + policy_id)
            assert h.requests[-1].policy_id == policy_id
            result = h.results[-1]
            assert result.status == "success", result.error
            report = policies.PolicyInspection.model_validate_json(result.report_json)
            assert report == policies.load_policy(policy_id)
            assert report.document.sha256 in reply
            assert not h.service.pending and not h.model_calls
            assert_reaped(children)
        finally:
            await h.close()

    asyncio.run(run())
