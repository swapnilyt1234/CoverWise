"""Provider SDK handlers with actual isolated PDF workers and temporary SQLite."""

import asyncio
import hashlib
import logging
from time import monotonic

import pytest
from test_sandbox import insurer as insurer
from test_sandbox import sandbox_router

from coverwise import policies, recommend
from coverwise.sandbox_contracts import SandboxReply
from coverwise.sandbox_ui import parse_command


def real_workers(insurer, monkeypatch, *, startup_delay=0, extraction_delay=0):
    popen = policies.subprocess.Popen
    launches = []

    def launch(command, **kwargs):
        # Redirect only the test child to temporary generated PDFs.
        script = (
            "import sys,time; from pathlib import Path; "
            "from coverwise import policies; "
            "policies.PDF_DIR=Path(sys.argv.pop(1)); "
            f"time.sleep({startup_delay if not launches else 0}); "
        )
        if extraction_delay:
            script += (
                "original=policies.load_policy; "
                "policies.load_policy=lambda p: "
                f"(time.sleep({extraction_delay}), original(p))[1]; "
            )
        script += "raise SystemExit(policies.main())"
        launches.append(command)
        return popen(
            [command[0], "-c", script, str(policies.PDF_DIR), *command[3:]], **kwargs
        )

    monkeypatch.setattr(policies.subprocess, "Popen", launch)
    monkeypatch.setattr(insurer.store, "assessor", recommend.run)
    return launches


@pytest.mark.parametrize("startup_delay", [0, 2.1])
def test_repeated_quotes_use_real_batch_workers(
    insurer, monkeypatch, caplog, startup_delay
):
    launches = real_workers(insurer, monkeypatch, startup_delay=startup_delay)
    caplog.set_level(logging.INFO, logger="coverwise")

    async def run():
        service, ctx, tasks = sandbox_router(
            insurer.store, session=insurer.session, timeout=15
        )
        references, durations = [], []
        for _ in range(3):
            started = monotonic()
            result = await service.sandbox_operation(
                ctx, insurer.sender, parse_command("/quote preset")
            )
            durations.append(round((monotonic() - started) * 1000, 3))
            assert result.status == "success"
            reply = SandboxReply.model_validate_json(result.payload_json)
            assert reply.state == "quote_active", reply.error_code
            assert reply.quote.premium_paise == 2200000
            document = reply.quote.evidence.document
            assert (
                document.sha256
                == hashlib.sha256(
                    (
                        policies.PDF_DIR
                        / policies.CANDIDATES[document.document_id].filename
                    ).read_bytes()
                ).hexdigest()
            )
            references.append(reply.reference)
        await asyncio.gather(*tasks)
        assert len(set(references)) == len(launches) == 3
        assert all("--batch-worker" in command for command in launches)
        assert insurer.store.counts()["quotes"] == 3
        assert insurer.store.counts()["payments"] == 0
        print(f"quote_ms={durations} startup_delay={startup_delay}")

    asyncio.run(run())
    messages = [
        r.getMessage() for r in caplog.records if "event=pdf_worker_timing" in r.message
    ]
    startups = [m for m in messages if "stage=pdf_worker_startup" in m]
    extractions = [m for m in messages if "stage=pdf_extraction" in m]
    assert len(startups) == 3 and len(extractions) == 12
    assert all("deadline_s=2.000" in m for m in extractions)
    print("\n".join(messages))


@pytest.mark.parametrize("failure", ["malformed_pdf", "extraction_timeout"])
def test_quote_extraction_failure_is_persisted_without_a_quote(
    insurer, monkeypatch, failure
):
    launches = real_workers(
        insurer,
        monkeypatch,
        extraction_delay=0.2 if failure == "extraction_timeout" else 0,
    )
    if failure == "malformed_pdf":
        (policies.PDF_DIR / "candidate-horizon.pdf").write_bytes(b"%PDF-1.7\nbroken")
    else:
        monkeypatch.setattr(policies, "WORKER_SECONDS", 0.05)

    async def run():
        service, ctx, tasks = sandbox_router(
            insurer.store, session=insurer.session, timeout=15
        )
        result = await service.sandbox_operation(
            ctx, insurer.sender, parse_command("/quote preset")
        )
        reply = SandboxReply.model_validate_json(result.payload_json)
        assert reply.state == "rejected" and reply.error_code == failure
        recovered = await service.sandbox_operation(
            ctx, insurer.sender, parse_command("/sandbox-status " + reply.operation_id)
        )
        status = SandboxReply.model_validate_json(recovered.payload_json)
        assert status.state == "rejected" and status.error_code == failure
        await asyncio.gather(*tasks)
        assert len(launches) == 1
        assert insurer.store.counts()["quotes"] == 0
        assert insurer.store.counts()["payments"] == 0
        assert not service.pending

    asyncio.run(run())
