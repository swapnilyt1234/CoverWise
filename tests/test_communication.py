import asyncio
import hashlib
import json
import os
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import httpx
import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as DomainValidationError
from pydantic.v1 import ValidationError
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    MetadataContent,
    Resource,
    ResourceContent,
    TextContent,
)
from uagents_core.registration import RegistrationRequest
from uagents_core.types import DeliveryStatus

from coverwise.agents import MAX_PENDING, Coordinator, Pending
from coverwise.asi import ASI_BASE_URL, ASI_MODEL, ASIExplainer
from coverwise.live import COORDINATOR_NAME, LiveSettings, main
from coverwise.smoke import main as smoke_main
from coverwise.transport import (
    MAX_TEXT,
    DiagnosticRequest,
    DiagnosticResult,
    diagnose,
)


def context():
    return SimpleNamespace(
        agent=SimpleNamespace(address="fixture-coordinator-address"),
        session=uuid4(),
        send=AsyncMock(return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)),
    )


def test_coordinator_name_satisfies_installed_registration_constraint():
    adapter = TypeAdapter(Annotated[str, RegistrationRequest.model_fields["name"]])
    assert adapter.validate_python(COORDINATOR_NAME) == "CoverWise Diagnostic"
    with pytest.raises(DomainValidationError):
        adapter.validate_python("CoverWise Connectivity Diagnostic")


def test_missing_live_configuration_refuses_before_construction(capsys):
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("coverwise.live.load_dotenv"),
        patch("coverwise.live.Agent") as agent,
        patch("coverwise.live.internal_agent") as investigator,
    ):
        assert main() == 1
        agent.assert_not_called()
        investigator.assert_not_called()
    assert "ASI1_API_KEY" in capsys.readouterr().out


def test_process_environment_wins_and_timeout_is_forwarded_without_reading_dotenv():
    env = {
        "ASI1_API_KEY": "test-only",
        "COVERWISE_PERSONAL_AGENT_SEED": "test-personal",
        "COVERWISE_INVESTIGATOR_AGENT_SEED": "test-investigator",
        "COVERWISE_PROVIDER_AGENT_SEED": "test-provider",
        "COVERWISE_REQUEST_TIMEOUT_SECONDS": "0.23",
    }

    def dotenv_without_file_access(_path, *, override):
        assert override is False
        os.environ.setdefault("COVERWISE_REQUEST_TIMEOUT_SECONDS", "30")

    with (
        patch.dict(os.environ, env, clear=True),
        patch("coverwise.live.load_dotenv", side_effect=dotenv_without_file_access),
        patch(
            "coverwise.live.run",
            new=Mock(return_value="not a real coroutine"),
        ) as run,
        patch("coverwise.live.asyncio.run") as execute,
        patch("coverwise.live.Agent") as construct,
    ):
        assert main() == 0
        assert run.call_args.args[0].request_timeout == 0.23
        execute.assert_called_once_with("not a real coroutine")
        construct.assert_not_called()


def test_local_smoke_refuses_sdk_constructor_side_effect(capsys):
    with patch("coverwise.runtime.internal_agent") as construct:
        assert smoke_main() == 2
        construct.assert_not_called()
    assert "get_almanac_contract" in capsys.readouterr().out


@pytest.mark.parametrize("timeout", ["NaN", "0", "31", "not-a-number"])
def test_invalid_live_timeout(timeout):
    with patch.dict(
        os.environ,
        {
            "ASI1_API_KEY": "test-only",
            "COVERWISE_PERSONAL_AGENT_SEED": "test-personal",
            "COVERWISE_INVESTIGATOR_AGENT_SEED": "test-investigator",
            "COVERWISE_PROVIDER_AGENT_SEED": "test-provider",
            "COVERWISE_REQUEST_TIMEOUT_SECONDS": timeout,
        },
        clear=True,
    ):
        with pytest.raises(ValueError, match="timeout"):
            LiveSettings.from_environment()


def test_result_correlation_sender_session_and_duplicates():
    async def exercise():
        service = Coordinator("investigator")
        ctx = context()
        task = asyncio.create_task(service.delegate(ctx, "test payload"))
        await asyncio.sleep(0)
        request = ctx.send.call_args.args[1]
        result = diagnose(request)
        assert not await service.accept_result(ctx, "intruder", result)
        assert not await service.accept_result(context(), "investigator", result)
        other = diagnose(DiagnosticRequest(request_id=uuid4(), text="other"))
        assert not await service.accept_result(ctx, "investigator", other)
        assert not task.done()
        assert await service.accept_result(ctx, "investigator", result)
        assert not await service.accept_result(ctx, "investigator", result)
        assert await task == result
        assert not service.pending
        assert not await service.accept_result(ctx, "investigator", result)

    asyncio.run(exercise())


def test_timeout_cleanup_late_response_and_no_false_success():
    async def exercise():
        service = Coordinator("investigator", timeout=0.05)
        ctx = context()
        result = await service.delegate(ctx, "timeout")
        assert result.status == "error" and result.error == "timeout"
        assert result.sha256 is None and result.character_count is None
        assert not service.pending
        late = diagnose(ctx.send.call_args.args[1])
        assert not await service.accept_result(ctx, "investigator", late)

    asyncio.run(exercise())


def test_cancellation_cleans_pending():
    async def exercise():
        service = Coordinator("investigator")
        task = asyncio.create_task(service.delegate(context(), "cancel"))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not service.pending

    asyncio.run(exercise())


def test_capacity_and_failed_delivery():
    async def exercise():
        service = Coordinator("investigator")
        ctx = context()
        ctx.send.return_value.status = DeliveryStatus.FAILED
        result = await service.delegate(ctx, "test")
        assert result.error == "delivery_failed"
        assert result.status == "error" and result.sha256 is None
        assert not service.pending
        ctx.send.side_effect = OSError("fixture transport failure")
        result = await service.delegate(ctx, "test")
        assert result.status == "error" and result.error == "delivery_failed"
        assert not service.pending
        ctx.send.side_effect = None
        future = asyncio.get_running_loop().create_future()
        service.pending = {
            uuid4(): Pending(ctx.session, future) for _ in range(MAX_PENDING)
        }
        ctx.send.reset_mock()
        result = await service.delegate(ctx, "test")
        assert result.error == "busy" and result.sha256 is None
        ctx.send.assert_not_called()
        future.cancel()

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "blocks",
    [
        [],
        [TextContent(text="/diagnose ")],
        [TextContent(text="/diagnose " + "x" * (MAX_TEXT + 1))],
        [TextContent(text="insurance advice")],
        [MetadataContent(metadata={"role": "attachment"})],
        [
            ResourceContent(
                resource_id=uuid4(),
                resource=Resource(
                    uri="https://invalid.example/policy.pdf", metadata={}
                ),
            )
        ],
        [EndSessionContent()],
    ],
)
def test_acp_acknowledges_before_rejecting_input(blocks):
    async def exercise():
        service = Coordinator("investigator")
        service.delegate = AsyncMock()
        ctx = context()
        message = ChatMessage(content=blocks)
        await service.chat(ctx, "client", message)
        assert ctx.send.await_count == 2
        acknowledgement = ctx.send.call_args_list[0].args[1]
        assert acknowledgement.acknowledged_msg_id == message.msg_id
        response = ctx.send.call_args_list[1].args[1]
        assert isinstance(response, ChatMessage)
        assert "success" not in response.text()
        service.delegate.assert_not_called()
        ctx.send.reset_mock()
        await service.acknowledge(ctx, "client", ChatAcknowledgement(message.msg_id))
        ctx.send.assert_not_called()

    asyncio.run(exercise())


def test_acp_success_preserves_tool_result_and_does_not_end_session():
    async def exercise():
        service = Coordinator("investigator")
        result = diagnose(DiagnosticRequest(request_id=uuid4(), text="actual text"))
        service.delegate = AsyncMock(return_value=result)
        ctx = context()
        message = ChatMessage(content=[TextContent(text="/diagnose actual text")])
        await service.chat(ctx, "client", message)
        service.delegate.assert_awaited_once_with(ctx, "actual text")
        reply = ctx.send.call_args.args[1]
        assert not any(isinstance(block, EndSessionContent) for block in reply.content)
        payload = json.loads(reply.text())
        assert payload["result"]["sha256"] == result.sha256
        assert payload["in_reply_to"] == str(message.msg_id)
        assert "Local deterministic" in payload["explanation"]

    asyncio.run(exercise())


def test_failed_tool_skips_model():
    async def exercise():
        explainer = SimpleNamespace(explain=AsyncMock())
        service = Coordinator("investigator", explainer=explainer)
        service.delegate = AsyncMock(
            return_value=DiagnosticResult(
                request_id=uuid4(), status="error", error="timeout"
            )
        )
        ctx = context()
        await service.chat(
            ctx, "client", ChatMessage(content=[TextContent(text="/diagnose test")])
        )
        payload = json.loads(ctx.send.call_args.args[1].text())
        assert payload["result"]["status"] == "error"
        assert payload["result"]["sha256"] is None
        explainer.explain.assert_not_called()

    asyncio.run(exercise())


@pytest.mark.parametrize("failure", ["timeout", "authentication"])
def test_model_failure_with_mock_http_and_zero_retries(failure):
    async def exercise():
        calls = []

        async def respond(request):
            calls.append(request)
            assert str(request.url) == ASI_BASE_URL + "/chat/completions"
            assert json.loads(request.content)["model"] == ASI_MODEL
            if failure == "timeout":
                raise httpx.ReadTimeout("fixture timeout", request=request)
            return httpx.Response(401, json={"error": {"message": "fixture denied"}})

        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        adapter = ASIExplainer("test-only-not-a-real-key", http_client=client)
        result = diagnose(DiagnosticRequest(request_id=uuid4(), text="tool input"))
        explanation = await adapter.explain(result)
        assert "Explanation unavailable" in explanation
        assert failure in explanation
        assert len(calls) == 1
        assert result.status == "success"
        assert result.sha256 == hashlib.sha256(b"tool input").hexdigest()

    asyncio.run(exercise())


def test_transport_result_rejects_incoherent_success_and_error():
    with pytest.raises(ValidationError):
        DiagnosticResult(request_id=uuid4(), status="success")
    with pytest.raises(ValidationError):
        DiagnosticResult(
            request_id=uuid4(), status="error", error="timeout", sha256="a" * 64
        )
    request = DiagnosticRequest(request_id=uuid4(), text="\ud800")
    assert diagnose(request).error == "invalid_text"
