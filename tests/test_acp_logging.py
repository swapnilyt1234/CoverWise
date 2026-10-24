import asyncio
import hashlib
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from uagents.utils import set_global_log_level
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    Resource,
    ResourceContent,
    TextContent,
)
from uagents_core.types import DeliveryStatus

from coverwise.agents import LOGGER, Coordinator
from coverwise.live import configure_logging
from coverwise.transport import MAX_TEXT, DiagnosticRequest, diagnose

PRIVATE = "private-body-MUST-NOT-APPEAR"


def context():
    return SimpleNamespace(
        agent=SimpleNamespace(address="fixture-coordinator-address"),
        session=uuid4(),
        send=AsyncMock(return_value=SimpleNamespace(status=DeliveryStatus.DELIVERED)),
    )


@pytest.mark.parametrize(
    ("blocks", "reason", "prefix"),
    [
        ([TextContent(text="/diagnose CoverWise connectivity")], "accepted", True),
        (
            [TextContent(text="/diagnose   " + PRIVATE + " \n")],
            "accepted",
            True,
        ),
        ([TextContent(text=" /diagnose " + PRIVATE)], "missing_exact_prefix", False),
        ([], "no_text", False),
        ([TextContent(text="/diagnose \t\n")], "empty_payload", True),
        (
            [TextContent(text="/diagnose " + "x" * (MAX_TEXT + 1))],
            "oversized_text",
            True,
        ),
        ([TextContent(text=PRIVATE)] * 9, "too_many_blocks", None),
        (
            [
                ResourceContent(
                    resource_id=uuid4(),
                    resource=Resource(
                        uri="https://private.invalid/path?token=" + PRIVATE,
                        metadata={"token": PRIVATE},
                    ),
                )
            ],
            "unsupported_block",
            None,
        ),
        ([MetadataContent(metadata={"token": PRIVATE})], "no_text", False),
    ],
)
def test_parser_logging_and_privacy_preserve_behavior(caplog, blocks, reason, prefix):
    async def exercise():
        service = Coordinator("investigator")

        async def result(ctx, text):
            # Ack is sent before the parser delegates; payload is never normalized.
            assert isinstance(ctx.send.call_args_list[0].args[1], ChatAcknowledgement)
            return diagnose(DiagnosticRequest(request_id=uuid4(), text=text))

        service.delegate = AsyncMock(side_effect=result)
        ctx = context()
        message = ChatMessage(content=blocks)
        with caplog.at_level(logging.INFO, logger="coverwise"):
            await service.chat(ctx, "client", message)
        records = [r.getMessage() for r in caplog.records if r.name == "coverwise"]
        output = "\n".join(records)
        assert (
            f"event=parser message_id={message.msg_id} session={ctx.session}" in output
        )
        assert (
            f"exact_prefix={prefix} accepted={reason == 'accepted'} reason={reason}"
            in output
        )
        assert "event=acp_received" in output and "block_types=" in output
        lengths = [
            len(b.text) if isinstance(b, TextContent) else None for b in blocks[:8]
        ]
        assert f"block_count={len(blocks)}" in output
        assert f"text_lengths={lengths}" in output
        assert "event=ack_send" in output and "outcome=delivered" in output
        assert "event=reply_send" in output
        assert PRIVATE not in output and "private.invalid" not in output
        if reason == "accepted":
            text = "".join(b.text for b in blocks if isinstance(b, TextContent))
            service.delegate.assert_awaited_once_with(ctx, text[len("/diagnose ") :])
            payload = json.loads(ctx.send.call_args.args[1].text())
            assert payload["result"]["status"] == "success"
            assert "event=diagnostic_result" in output
        else:
            service.delegate.assert_not_called()
            if reason in ("no_text", "missing_exact_prefix", "empty_payload"):
                assert ctx.send.call_args.args[1].text() == (
                    "Use /diagnose <nonempty text>, /policies, "
                    "/inspect <policy-id>, or /stress-test (help)."
                )

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("wrapper", "payload", "reason"),
    [
        ("direct", "CoverWise connectivity", "accepted"),
        ("self", "CoverWise connectivity", "accepted"),
        ("wrong", PRIVATE, "missing_exact_prefix"),
        ("prose", PRIVATE, "missing_exact_prefix"),
        ("repeated", PRIVATE, "missing_exact_prefix"),
        ("double_separator", PRIVATE, "missing_exact_prefix"),
        ("tab_separator", PRIVATE, "missing_exact_prefix"),
        ("no_separator", PRIVATE, "missing_exact_prefix"),
        ("address_suffix", PRIVATE, "missing_exact_prefix"),
        ("direct", " \tनमस्ते 🌱 " + PRIVATE + " \n", "accepted"),
        ("self", " \tनमस्ते 🌱 " + PRIVATE + " \n", "accepted"),
        ("direct", "", "empty_payload"),
        ("self", " \t\n", "empty_payload"),
        ("direct", "x" * MAX_TEXT, "accepted"),
        ("self", "x" * MAX_TEXT, "accepted"),
        ("direct", "x" * (MAX_TEXT + 1), "oversized_text"),
        ("self", "x" * (MAX_TEXT + 1), "oversized_text"),
        ("wrong", "x" * MAX_TEXT, "oversized_text"),
    ],
)
def test_exact_self_mention_parsing_limits_and_private_logs(
    caplog, wrapper, payload, reason
):
    async def exercise():
        ctx = context()
        # Different context address every time; no SDK identities or agents created.
        ctx.agent.address = "unit-coordinator-" + uuid4().hex
        mention = f"@{ctx.agent.address} "
        wrappers = {
            "direct": "",
            "self": mention,
            "wrong": "@other-private-address ",
            "prose": "private-prose-before-command ",
            "repeated": mention + mention,
            "double_separator": mention + " ",
            "tab_separator": f"@{ctx.agent.address}\t",
            "no_separator": f"@{ctx.agent.address}",
            "address_suffix": f"@{ctx.agent.address}-other ",
        }
        text = wrappers[wrapper] + "/diagnose " + payload
        service = Coordinator("investigator")

        async def result(ctx, text):
            return diagnose(DiagnosticRequest(request_id=uuid4(), text=text))

        service.delegate = AsyncMock(side_effect=result)
        with caplog.at_level(logging.INFO, logger="coverwise"):
            await service.chat(
                ctx, "client", ChatMessage(content=[TextContent(text=text)])
            )
        output = caplog.text
        matched = wrapper in ("self", "repeated", "double_separator")
        removed = len(mention) if matched else 0
        assert f"self_mention_match={matched}" in output
        assert f"mention_prefix_length={len(mention)}" in output
        assert f"removed_prefix_length={removed}" in output
        assert f"normalized_command_length={len(text) - removed}" in output
        normalized_match = wrapper in ("direct", "self")
        assert f"normalized_exact_prefix={normalized_match}" in output
        assert f"accepted={reason == 'accepted'} reason={reason}" in output
        assert ctx.agent.address not in output
        assert PRIVATE not in output
        assert "other-private-address" not in output
        assert "private-prose-before-command" not in output
        assert text not in output
        if reason == "accepted":
            service.delegate.assert_awaited_once_with(ctx, payload)
            response = json.loads(ctx.send.call_args.args[1].text())
            assert response["result"]["character_count"] == len(payload)
            assert (
                response["result"]["sha256"]
                == hashlib.sha256(payload.encode("utf-8")).hexdigest()
            )
        else:
            service.delegate.assert_not_called()

    asyncio.run(exercise())


def test_delegation_logs_start_result_timeout_and_correlation(caplog):
    async def exercise():
        service = Coordinator("investigator", timeout=0.05)
        ctx = context()
        with caplog.at_level(logging.INFO, logger="coverwise"):
            task = asyncio.create_task(service.delegate(ctx, PRIVATE))
            await asyncio.sleep(0)
            request = ctx.send.call_args.args[1]
            await service.accept_result(ctx, "investigator", diagnose(request))
            assert (await task).status == "success"
            assert (await service.delegate(ctx, PRIVATE)).error == "timeout"
        output = "\n".join(r.getMessage() for r in caplog.records)
        assert f"event=delegation_start request_id={request.request_id}" in output
        assert f"event=delegation_result request_id={request.request_id}" in output
        assert "event=delegation_send" in output
        assert "event=delegation_end" in output and "outcome=timeout" in output
        assert f"session={ctx.session}" in output
        assert PRIVATE not in output
        assert not service.pending

    asyncio.run(exercise())


@pytest.mark.parametrize("event", ["ack_send", "reply_send"])
@pytest.mark.parametrize("raises", [False, True])
def test_send_outcome_logs_do_not_dump_delivery_details(caplog, event, raises):
    async def exercise():
        service = Coordinator("investigator")
        ctx = context()
        ctx.send.return_value = SimpleNamespace(
            status=DeliveryStatus.FAILED,
            detail=PRIVATE,
            endpoint="https://private.invalid/" + PRIVATE,
        )
        message = ChatAcknowledgement(uuid4())
        if event == "reply_send":
            message = ChatMessage(content=[TextContent(text=PRIVATE)])
        with caplog.at_level(logging.INFO, logger="coverwise"):
            if raises:
                ctx.send.side_effect = OSError(PRIVATE)
                with pytest.raises(OSError):
                    await service.send_logged(ctx, "client", message, event)
            else:
                delivery = await service.send_logged(ctx, "client", message, event)
                assert delivery.status == DeliveryStatus.FAILED
        assert f"event={event}" in caplog.text
        assert f"outcome={'exception' if raises else 'failed'}" in caplog.text
        assert PRIVATE not in caplog.text and "private.invalid" not in caplog.text

    asyncio.run(exercise())


def test_live_info_logging_restored_after_sdk_warning_configuration(capsys):
    loggers = [logging.getLogger()] + [
        logger
        for logger in logging.Logger.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    levels = {logger: logger.level for logger in loggers}
    try:
        # This is the real SDK helper called by investigator construction, no Agent.
        with patch.object(LOGGER, "handlers", []), patch.object(LOGGER, "propagate"):
            set_global_log_level(logging.WARNING)
            assert LOGGER.level == logging.WARNING
            configure_logging()
            configure_logging()
            assert len(LOGGER.handlers) == 1
            LOGGER.info("event=visibility_probe")
            output = capsys.readouterr().err
            assert output.count("event=visibility_probe") == 1
            assert "event=logging_ready level=INFO" in output
            for handler in LOGGER.handlers:
                handler.close()
    finally:
        for logger, level in levels.items():
            logger.setLevel(level)


def test_effective_timeout_is_logged_without_configuration_secrets(capsys):
    previous_level = LOGGER.level
    try:
        with (
            patch.object(LOGGER, "handlers", []),
            patch.object(LOGGER, "propagate", False),
        ):
            configure_logging(0.23)
            output = capsys.readouterr().err
            assert "event=configuration request_timeout_seconds=0.230" in output
            assert "dotenv_override=False" in output
            assert "SEED" not in output and "API_KEY" not in output
            for handler in LOGGER.handlers:
                handler.close()
    finally:
        LOGGER.setLevel(previous_level)
