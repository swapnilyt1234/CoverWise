"""Distinct Provider SDK protocol, authoritative synthetic catalogue tool."""

import asyncio
import logging
from threading import Lock
from time import monotonic

from uagents import Protocol

from coverwise.catalogue import load_catalogue
from coverwise.policies import PolicyError
from coverwise.sandbox import SandboxError, SandboxProvider
from coverwise.sandbox_contracts import SandboxCommand
from coverwise.transport import (
    CatalogueRequest,
    CatalogueResult,
    SandboxRequest,
    SandboxResult,
)

LOGGER = logging.getLogger("coverwise")


def install_provider(agent, coordinator: str, *, sandbox=None):
    protocol = Protocol(name="CoverWiseProviderCatalogue", version="1.0.0")
    initialize = Lock()

    @protocol.on_message(CatalogueRequest, replies=CatalogueResult)
    async def catalogue(ctx, sender: str, request: CatalogueRequest):
        if sender != coordinator:
            return
        received = monotonic()
        session = ctx.session
        LOGGER.info(
            "role=provider event=handler_received stage=provider_catalogue "
            "request_id=%s session=%s received_monotonic=%.6f injection=%s",
            request.request_id,
            session,
            received,
            request.test_timeout,
        )
        if request.test_timeout:
            LOGGER.info(
                "role=provider request_id=%s outcome=test_silence "
                "session=%s stage=provider_catalogue injection=True",
                request.request_id,
                session,
            )
            return

        def work():
            started = monotonic()
            LOGGER.info(
                "role=provider event=catalogue_started stage=provider_catalogue "
                "request_id=%s session=%s queue_scope=executor queue_wait_ms=%.3f "
                "injection=False",
                request.request_id,
                session,
                (started - received) * 1000,
            )
            try:
                return load_catalogue()
            finally:
                LOGGER.info(
                    "role=provider event=catalogue_finished stage=provider_catalogue "
                    "request_id=%s session=%s assessment_duration_ms=%.3f "
                    "injection=False",
                    request.request_id,
                    session,
                    (monotonic() - started) * 1000,
                )

        try:
            snapshot = await asyncio.to_thread(work)
            payload = snapshot.model_dump_json()
            if len(payload.encode("utf-8")) > 32768:
                raise PolicyError("result_too_large")
            result = CatalogueResult(
                request_id=request.request_id, status="success", payload_json=payload
            )
        except Exception as exc:
            code = (
                "result_too_large"
                if isinstance(exc, PolicyError) and str(exc) == "result_too_large"
                else "catalogue_unavailable"
            )
            result = CatalogueResult(
                request_id=request.request_id, status="error", error=code
            )
        sending = monotonic()
        try:
            await ctx.send(sender, result)
        finally:
            LOGGER.info(
                "role=provider event=response_send stage=provider_catalogue "
                "request_id=%s session=%s response_send_ms=%.3f injection=%s",
                request.request_id,
                session,
                (monotonic() - sending) * 1000,
                request.test_timeout,
            )
        LOGGER.info(
            "role=provider request_id=%s outcome=%s", request.request_id, result.status
        )

    @protocol.on_message(SandboxRequest, replies=SandboxResult)
    async def workflow(ctx, sender: str, request: SandboxRequest):
        nonlocal sandbox
        if sender != coordinator:
            return
        if request.observed_session != ctx.session:
            await ctx.send(
                sender,
                SandboxResult(
                    request_id=request.request_id,
                    status="error",
                    error="scope_mismatch",
                ),
            )
            return
        try:
            command = SandboxCommand.model_validate_json(request.command_json)
        except ValueError:
            await ctx.send(
                sender,
                SandboxResult(
                    request_id=request.request_id,
                    status="error",
                    error="invalid_workflow_request",
                ),
            )
            return
        started = monotonic()

        def work():
            nonlocal sandbox
            with initialize:
                if sandbox is None:
                    sandbox = SandboxProvider()
            return sandbox.execute(
                request.observed_sender,
                request.observed_session,
                request.request_id,
                command,
            )

        try:
            reply = await asyncio.to_thread(work)
            payload = reply.model_dump_json()
            if len(payload.encode("utf-8")) > 131072:
                raise PolicyError("result_too_large")
            result = SandboxResult(
                request_id=request.request_id, status="success", payload_json=payload
            )
        except SandboxError:
            result = SandboxResult(
                request_id=request.request_id, status="error", error="workflow_rejected"
            )
        except Exception:
            result = SandboxResult(
                request_id=request.request_id,
                status="error",
                error="workflow_unavailable",
            )
        LOGGER.info(
            "role=provider event=sandbox_result stage=provider_sandbox "
            "request_id=%s session=%s elapsed_ms=%.3f outcome=%s",
            request.request_id,
            ctx.session,
            (monotonic() - started) * 1000,
            result.status,
        )
        await ctx.send(sender, result)

    agent.include(protocol)
