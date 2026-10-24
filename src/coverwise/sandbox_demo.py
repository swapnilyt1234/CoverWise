"""Offline SDK-handler demonstration against actual SQLite and PDF-backed tools."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

from uagents import Model
from uagents_core.types import DeliveryStatus

from coverwise.agents import Coordinator
from coverwise.provider import install_provider
from coverwise.sandbox import LABEL, SandboxProvider
from coverwise.sandbox_contracts import SandboxReply
from coverwise.sandbox_ui import parse_command
from coverwise.transport import SandboxRequest


class OfflineWorkflow:
    """Real protocol callbacks with local contexts, not live-agent transport."""

    def __init__(self, store, *, sender="synthetic-demo-sender", session=None):
        self.sender = sender
        self.service = Coordinator(
            "unused-investigator", provider="offline-provider", timeout=15
        )
        protocols = []
        install_provider(
            SimpleNamespace(include=protocols.append),
            "offline-coordinator",
            sandbox=store,
        )
        self.handler = protocols[0].signed_message_handlers[
            Model.build_schema_digest(SandboxRequest)
        ]
        self.context = SimpleNamespace(session=session or uuid4(), send=self.send)
        self.tasks = []

    async def send(self, destination, request):
        if destination != "offline-provider" or not isinstance(request, SandboxRequest):
            raise ValueError("offline workflow accepts Provider requests only")

        async def response(_destination, result):
            await self.service.accept_result(self.context, "offline-provider", result)

        context = SimpleNamespace(session=self.context.session, send=response)
        self.tasks.append(
            asyncio.create_task(self.handler(context, "offline-coordinator", request))
        )
        return SimpleNamespace(status=DeliveryStatus.DELIVERED)

    async def command(self, text):
        result = await self.service.sandbox_operation(
            self.context, self.sender, parse_command(text)
        )
        await asyncio.gather(*self.tasks)
        if result.status != "success":
            raise RuntimeError("offline Provider operation failed: " + result.error)
        assert not self.service.pending
        return SandboxReply.model_validate_json(result.payload_json)


async def demonstrate(path):
    store = SandboxProvider(path)
    harness = OfflineWorkflow(store)
    results = []
    for mode in ("success", "failure", "unknown"):
        q = await harness.command("/quote preset")
        app = await harness.command(f"/apply {q.reference} confirm-demo {mode}")
        approval_command = app.next_commands[0]
        result = await harness.command(approval_command)
        repeated = await harness.command(approval_command)
        assert result.payment == repeated.payment
        before_restart = result.state
        # New Provider instance/connections; only the observed demo scope is retained.
        store = SandboxProvider(path)
        harness = OfflineWorkflow(
            store, sender=harness.sender, session=harness.context.session
        )
        recovered = await harness.command("/sandbox-status " + app.reference)
        expected = "failed" if mode == "failure" else "completed"
        assert recovered.state == expected
        repeated_status = await harness.command("/sandbox-status " + app.reference)
        assert repeated_status.payment == recovered.payment
        results.append(
            dict(
                mode=mode,
                quote_id=q.reference,
                application_id=app.reference,
                revision=app.application.revision,
                initial_state=before_restart,
                restart_status=recovered.state,
                payment_id=recovered.payment.payment_id,
                confirmation=recovered.payment.confirmation,
                status_command="/sandbox-status " + app.reference,
            )
        )
    counts = store.counts()
    assert all(
        counts[k] == 3
        for k in (
            "quotes",
            "applications",
            "revisions",
            "approvals",
            "payments",
            "payment_ledger",
        )
    )
    return dict(
        label=LABEL,
        harness="offline SDK handlers; no live agents or transport",
        flows=results,
        database_counts=counts,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        help="new ignored SQLite path; default is a temporary database",
    )
    args = parser.parse_args()
    if args.database:
        if args.database.exists():
            parser.error(
                "choose a new database; this demo never deletes existing records"
            )
        result = asyncio.run(demonstrate(args.database))
    else:
        with TemporaryDirectory(prefix="coverwise-sandbox-") as root:
            result = asyncio.run(demonstrate(Path(root) / "provider.sqlite3"))
    sys.stdout.buffer.write((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
