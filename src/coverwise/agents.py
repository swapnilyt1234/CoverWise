"""Real SDK handlers for the first, diagnostic-only communication path."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from time import monotonic
from uuid import UUID, uuid4

from uagents import Agent, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.types import DeliveryStatus

from coverwise.asi import ASIExplainer
from coverwise.cards import Cards
from coverwise.catalogue import CatalogueSnapshot
from coverwise.contracts import JobChangeScenario, PolicyInspection
from coverwise.conversation import Conversation
from coverwise.policies import (
    ERROR_CODES,
    MAX_REPLY,
    PolicyError,
    inspect_policy,
    policy_listing,
    present,
)
from coverwise.recommend import (
    HELP as RECOMMEND_HELP,
)
from coverwise.recommend import (
    Recommendation,
    RecommendationInput,
    present_evidence,
)
from coverwise.recommend import (
    parse_input as parse_recommendation,
)
from coverwise.recommend import (
    present as present_recommendation,
)
from coverwise.recommend import (
    run as assess_candidates,
)
from coverwise.sandbox import owner_scope
from coverwise.sandbox_contracts import SandboxCommand, SandboxReply
from coverwise.sandbox_ui import HELP as SANDBOX_HELP
from coverwise.sandbox_ui import PREFIXES as SANDBOX_PREFIXES
from coverwise.sandbox_ui import (
    details_page,
)
from coverwise.sandbox_ui import (
    parse_command as parse_sandbox,
)
from coverwise.sandbox_ui import (
    present as present_sandbox,
)
from coverwise.stress import (
    USAGE,
    Comparison,
    parse_input,
    present_comparison,
)
from coverwise.stress import (
    run as run_stress,
)
from coverwise.transport import (
    MAX_TEXT,
    CandidateAssessmentRequest,
    CandidateAssessmentResult,
    CatalogueRequest,
    CatalogueResult,
    DiagnosticRequest,
    DiagnosticResult,
    PolicyInspectionRequest,
    PolicyInspectionResult,
    SandboxRequest,
    SandboxResult,
    StressTestRequest,
    StressTestResult,
    diagnose,
)

LOGGER = logging.getLogger("coverwise")
COMMAND = "/diagnose "
MAX_PENDING = 16
RECENT_REQUESTS = 128


@dataclass
class Pending:
    session: UUID
    future: asyncio.Future
    result_type: type = DiagnosticResult
    policy_id: str | None = None
    scenario: JobChangeScenario | None = None
    sender: str | None = None
    inputs: RecommendationInput | None = None
    catalogue: CatalogueSnapshot | None = None
    deadline: float | None = None
    stage: str = "investigator"
    injection: bool = False
    sandbox: SandboxCommand | None = None
    scope: str | None = None


class Coordinator:
    def __init__(
        self,
        investigator: str,
        timeout: float = 3.0,
        explainer: ASIExplainer | None = None,
        provider: str | None = None,
    ):
        if not 0.05 <= timeout <= 30:
            raise ValueError("request timeout must be between 0.05 and 30 seconds")
        self.investigator = investigator
        self.timeout = timeout
        self.explainer = explainer
        self.provider = provider
        self.pending: dict[UUID, Pending] = {}
        self.closed: dict[UUID, tuple[str, str]] = {}
        self.cards = Cards(self)
        self.conversation = (
            Conversation(self, explainer)
            if callable(getattr(explainer, "parse_intent", None))
            else None
        )

    def ignored(self, ctx, request_id, reason, stage="unknown"):
        LOGGER.info(
            "role=coordinator request_id=%s outcome=ignored_response "
            "session=%s stage=%s reason=%s",
            request_id,
            ctx.session,
            stage,
            reason,
        )
        return False

    def finish(self, ctx, request_id, outcome):
        slot = self.pending.pop(request_id, None)
        if slot is None:
            return
        reason = (
            "expired"
            if outcome == "timeout"
            else "cancelled"
            if outcome == "cancelled"
            else "duplicate"
            if slot.future.done() and not slot.future.cancelled()
            else "unknown_id"
        )
        self.closed[request_id] = (reason, slot.stage)
        if len(self.closed) > RECENT_REQUESTS:
            self.closed.pop(next(iter(self.closed)))
        if not slot.future.done():
            slot.future.cancel()
        LOGGER.info(
            "role=coordinator event=pending_cleanup request_id=%s session=%s "
            "stage=%s outcome=%s pending_removed=True future_cancelled=%s "
            "injection=%s",
            request_id,
            ctx.session,
            slot.stage,
            outcome,
            slot.future.cancelled(),
            slot.injection,
        )

    async def send_logged(self, ctx: Context, destination: str, message, event: str):
        started = monotonic()
        identifier = (
            message.acknowledged_msg_id
            if isinstance(message, ChatAcknowledgement)
            else message.msg_id
            if isinstance(message, ChatMessage)
            else message.request_id
        )
        try:
            delivery = await ctx.send(destination, message)
        except Exception as exc:
            LOGGER.info(
                "role=coordinator event=%s id=%s session=%s "
                "outcome=exception error_type=%s",
                event,
                identifier,
                ctx.session,
                type(exc).__name__,
            )
            raise
        LOGGER.info(
            "role=coordinator event=%s id=%s session=%s outcome=%s "
            "send_duration_ms=%.3f",
            event,
            identifier,
            ctx.session,
            delivery.status.value,
            (monotonic() - started) * 1000,
        )
        return delivery

    async def accept_result(
        self,
        ctx: Context,
        sender: str,
        result: DiagnosticResult
        | PolicyInspectionResult
        | StressTestResult
        | CatalogueResult
        | CandidateAssessmentResult
        | SandboxResult,
    ) -> bool:
        slot = self.pending.get(result.request_id)
        if slot is None:
            reason, stage = self.closed.get(
                result.request_id, ("unknown_id", "unknown")
            )
            return self.ignored(ctx, result.request_id, reason, stage)
        reason = (
            "sender_mismatch"
            if sender != (slot.sender or self.investigator)
            else "session_mismatch"
            if slot.session != ctx.session
            else "duplicate"
            if slot.future.done() and not slot.future.cancelled()
            else "expired"
            if slot.deadline is not None and monotonic() >= slot.deadline
            else "cancelled"
            if slot.future.cancelled()
            else "result_type_mismatch"
            if not isinstance(result, slot.result_type)
            else "policy_mismatch"
            if isinstance(result, PolicyInspectionResult)
            and result.policy_id != slot.policy_id
            else None
        )
        if reason:
            return self.ignored(ctx, result.request_id, reason, slot.stage)
        if isinstance(result, SandboxResult):
            if result.status == "success":
                try:
                    if len(result.payload_json.encode("utf-8")) > 131072:
                        raise ValueError("oversize")
                    reply = SandboxReply.model_validate_json(result.payload_json)
                    if (
                        slot.sandbox is None
                        or reply.scope != slot.scope
                        or reply.action != slot.sandbox.action
                        or reply.operation_id != "op-" + result.request_id.hex
                        or (
                            reply.quote is not None
                            and slot.sandbox.action == "quote"
                            and (
                                reply.quote.inputs != slot.sandbox.inputs
                                or reply.quote.product.product_id
                                != slot.sandbox.product_id
                            )
                        )
                        or (
                            reply.application is not None
                            and slot.sandbox.action in ("review", "approve", "cancel")
                            and reply.reference != slot.sandbox.reference
                        )
                        or (
                            slot.sandbox.action in ("status", "details")
                            and not slot.sandbox.reference.startswith("op-")
                            and reply.reference != slot.sandbox.reference
                        )
                        or (
                            reply.application is not None
                            and slot.sandbox.action == "approve"
                            and reply.application.revision != slot.sandbox.revision
                        )
                        or (
                            reply.application is not None
                            and slot.sandbox.replacement_quote is not None
                            and reply.application.quote.quote_id
                            != slot.sandbox.replacement_quote
                        )
                        or (
                            reply.application is not None
                            and slot.sandbox.action == "apply"
                            and (
                                reply.application.quote.quote_id
                                != slot.sandbox.reference
                                or reply.application.fields != slot.sandbox.application
                            )
                        )
                    ):
                        return self.ignored(
                            ctx,
                            result.request_id,
                            "sandbox_binding_mismatch",
                            slot.stage,
                        )
                    present_sandbox(reply)
                except (ValueError, PolicyError):
                    return self.ignored(
                        ctx, result.request_id, "invalid_sandbox_result", slot.stage
                    )
            elif result.error not in {
                "workflow_unavailable",
                "workflow_rejected",
                "invalid_workflow_request",
                "scope_mismatch",
                "timeout",
                "delivery_failed",
                "busy",
                "provider_unavailable",
            }:
                return self.ignored(
                    ctx, result.request_id, "invalid_error_code", slot.stage
                )
        if isinstance(result, (CatalogueResult, CandidateAssessmentResult)):
            if result.status == "success":
                try:
                    if len(result.payload_json.encode("utf-8")) > 262144:
                        return self.ignored(
                            ctx, result.request_id, "oversized_result", slot.stage
                        )
                    if isinstance(result, CatalogueResult):
                        if len(result.payload_json.encode("utf-8")) > 32768:
                            return self.ignored(
                                ctx, result.request_id, "oversized_result", slot.stage
                            )
                        CatalogueSnapshot.model_validate_json(result.payload_json)
                    else:
                        report = Recommendation.model_validate_json(result.payload_json)
                        if (
                            report.inputs != slot.inputs
                            or report.catalogue != slot.catalogue
                        ):
                            return self.ignored(
                                ctx,
                                result.request_id,
                                "input_or_catalogue_mismatch",
                                slot.stage,
                            )
                        present_recommendation(report)
                except (ValueError, PolicyError):
                    return self.ignored(
                        ctx, result.request_id, "invalid_result", slot.stage
                    )
            elif result.error not in ERROR_CODES | {
                "catalogue_unavailable",
                "catalogue_pdf_disagreement",
                "invalid_input",
                "timeout",
                "delivery_failed",
                "busy",
                "provider_unavailable",
            }:
                return self.ignored(
                    ctx, result.request_id, "invalid_error_code", slot.stage
                )
        if isinstance(result, StressTestResult):
            if result.status == "success":
                try:
                    report = Comparison.model_validate_json(result.report_json)
                    if report.scenario != slot.scenario:
                        return self.ignored(
                            ctx, result.request_id, "scenario_mismatch", slot.stage
                        )
                    present_comparison(report)
                except (ValueError, PolicyError):
                    return self.ignored(
                        ctx, result.request_id, "invalid_result", slot.stage
                    )
            elif result.error not in ERROR_CODES | {
                "timeout",
                "delivery_failed",
                "busy",
                "invalid_scenario",
            }:
                return self.ignored(
                    ctx, result.request_id, "invalid_error_code", slot.stage
                )
        if isinstance(result, PolicyInspectionResult):
            if result.status == "success":
                try:
                    report = PolicyInspection.model_validate_json(result.report_json)
                    if report.document.document_id != slot.policy_id:
                        return self.ignored(
                            ctx, result.request_id, "policy_mismatch", slot.stage
                        )
                except ValueError:
                    return self.ignored(
                        ctx, result.request_id, "invalid_result", slot.stage
                    )
            elif result.error not in ERROR_CODES | {
                "timeout",
                "delivery_failed",
                "busy",
            }:
                return self.ignored(
                    ctx, result.request_id, "invalid_error_code", slot.stage
                )
        if slot.deadline is not None and monotonic() >= slot.deadline:
            return self.ignored(ctx, result.request_id, "expired", slot.stage)
        slot.future.set_result(result)
        LOGGER.info(
            "role=coordinator event=delegation_result request_id=%s session=%s "
            "outcome=%s error=%s stage=%s injection=%s",
            result.request_id,
            ctx.session,
            result.status,
            result.error,
            slot.stage,
            slot.injection,
        )
        return True

    async def delegate(
        self,
        ctx: Context,
        text: str,
        policy_id: str | None = None,
        scenario: JobChangeScenario | None = None,
    ) -> DiagnosticResult | PolicyInspectionResult | StressTestResult:
        request_id = uuid4()
        result_type = (
            StressTestResult
            if scenario is not None
            else PolicyInspectionResult
            if policy_id is not None
            else DiagnosticResult
        )
        fields = {"policy_id": policy_id} if policy_id is not None else {}

        def failure(code):
            return result_type(
                request_id=request_id, status="error", error=code, **fields
            )

        if len(self.pending) >= MAX_PENDING:
            LOGGER.info(
                "role=coordinator request_id=%s duration_ms=0 outcome=busy", request_id
            )
            return failure("busy")
        future = asyncio.get_running_loop().create_future()
        started = monotonic()
        self.pending[request_id] = Pending(
            ctx.session,
            future,
            result_type,
            policy_id,
            scenario,
            deadline=started + self.timeout,
        )
        outcome = "cancelled"
        LOGGER.info(
            "role=coordinator event=delegation_start request_id=%s session=%s "
            "text_length=%d",
            request_id,
            ctx.session,
            len(text),
        )
        try:
            async with asyncio.timeout(self.timeout):
                delivery = await self.send_logged(
                    ctx,
                    self.investigator,
                    StressTestRequest(
                        request_id=request_id, scenario_json=scenario.model_dump_json()
                    )
                    if scenario is not None
                    else PolicyInspectionRequest(
                        request_id=request_id, policy_id=policy_id
                    )
                    if policy_id is not None
                    else DiagnosticRequest(request_id=request_id, text=text),
                    "delegation_send",
                )
                if delivery.status != DeliveryStatus.DELIVERED:
                    result = failure("delivery_failed")
                else:
                    result = await future
                outcome = result.error or result.status
        except TimeoutError:
            outcome = "timeout"
            result = failure("timeout")
        except Exception:
            outcome = "delivery_failed"
            result = failure("delivery_failed")
        finally:
            self.finish(ctx, request_id, outcome)
            LOGGER.info(
                "role=coordinator event=delegation_end request_id=%s session=%s "
                "duration_ms=%.1f outcome=%s",
                request_id,
                ctx.session,
                (monotonic() - started) * 1000,
                outcome,
            )
        return result

    async def request_tool(
        self,
        ctx,
        destination,
        request,
        result_type,
        inputs=None,
        catalogue=None,
        sandbox=None,
        scope=None,
    ):
        def failure(code):
            return result_type(
                request_id=request.request_id, status="error", error=code
            )

        if destination is None:
            return failure("provider_unavailable")
        if len(self.pending) >= MAX_PENDING:
            return failure("busy")
        future = asyncio.get_running_loop().create_future()
        started = monotonic()
        timeout = self.timeout
        stage = (
            "provider_catalogue"
            if isinstance(request, CatalogueRequest)
            else "provider_sandbox"
            if isinstance(request, SandboxRequest)
            else "investigator_assessment"
        )
        injection = isinstance(request, CatalogueRequest) and request.test_timeout
        self.pending[request.request_id] = Pending(
            ctx.session,
            future,
            result_type,
            sender=destination,
            inputs=inputs,
            catalogue=catalogue,
            deadline=started + timeout,
            stage=stage,
            injection=injection,
            sandbox=sandbox,
            scope=scope,
        )
        LOGGER.info(
            "role=coordinator event=delegation_start request_id=%s session=%s "
            "stage=%s deadline_s=%.3f started_monotonic=%.6f injection=%s",
            request.request_id,
            ctx.session,
            stage,
            timeout,
            started,
            injection,
        )
        outcome = "cancelled"
        try:
            async with asyncio.timeout(timeout):
                delivered = await self.send_logged(
                    ctx, destination, request, "delegation_send"
                )
                if delivered.status != DeliveryStatus.DELIVERED:
                    outcome = "delivery_failed"
                    return failure("delivery_failed")
                result = await future
                outcome = result.error or result.status
                return result
        except TimeoutError:
            outcome = "timeout"
            LOGGER.info(
                "role=coordinator event=delegation_timeout request_id=%s session=%s "
                "stage=%s deadline_s=%.3f elapsed_ms=%.3f injection=%s",
                request.request_id,
                ctx.session,
                stage,
                timeout,
                (monotonic() - started) * 1000,
                injection,
            )
            return failure("timeout")
        except Exception:
            outcome = "delivery_failed"
            return failure("delivery_failed")
        finally:
            self.finish(ctx, request.request_id, outcome)
            LOGGER.info(
                "role=coordinator event=delegation_end request_id=%s session=%s "
                "stage=%s elapsed_ms=%.3f outcome=%s injection=%s",
                request.request_id,
                ctx.session,
                stage,
                (monotonic() - started) * 1000,
                outcome,
                injection,
            )

    async def recommend(self, ctx, inputs, *, test_timeout=False):
        catalogue_result = await self.request_tool(
            ctx,
            self.provider,
            CatalogueRequest(request_id=uuid4(), test_timeout=test_timeout),
            CatalogueResult,
        )
        if catalogue_result.status != "success":
            return CandidateAssessmentResult(
                request_id=catalogue_result.request_id,
                status="error",
                error=catalogue_result.error,
            )
        snapshot = CatalogueSnapshot.model_validate_json(catalogue_result.payload_json)
        return await self.request_tool(
            ctx,
            self.investigator,
            CandidateAssessmentRequest(
                request_id=uuid4(),
                input_json=inputs.model_dump_json(),
                catalogue_json=snapshot.model_dump_json(),
            ),
            CandidateAssessmentResult,
            inputs=inputs,
            catalogue=snapshot,
        )

    async def sandbox_operation(self, ctx, observed_sender, command):
        request = SandboxRequest(
            request_id=uuid4(),
            observed_sender=observed_sender,
            observed_session=ctx.session,
            command_json=command.model_dump_json(),
        )
        result = await self.request_tool(
            ctx,
            self.provider,
            request,
            SandboxResult,
            sandbox=command,
            scope=owner_scope(observed_sender, ctx.session),
        )
        return result

    async def chat(self, ctx: Context, sender: str, message: ChatMessage):
        started = monotonic()
        outcome = "rejected_input"
        LOGGER.info(
            "role=coordinator event=acp_received message_id=%s session=%s "
            "block_count=%d block_types=%s text_lengths=%s summary_truncated=%s",
            message.msg_id,
            ctx.session,
            len(message.content),
            [block.type for block in message.content[:8]],
            [
                len(block.text) if isinstance(block, TextContent) else None
                for block in message.content[:8]
            ],
            len(message.content) > 8,
        )
        await self.send_logged(
            ctx,
            sender,
            ChatAcknowledgement(acknowledged_msg_id=message.msg_id),
            "ack_send",
        )
        allowed = (TextContent, MetadataContent, StartSessionContent)
        prefix_match = None
        self_mention_match = None
        normalized_prefix_match = None
        mention_prefix_length = None
        removed_prefix_length = None
        normalized_command_length = None
        card_response = None
        card_source = None
        if len(message.content) > 8 or any(
            not isinstance(block, allowed) for block in message.content
        ):
            reason = (
                "too_many_blocks" if len(message.content) > 8 else "unsupported_block"
            )
            reply = (
                "Unsupported input: text only; attachments and URLs are not fetched."
            )
        else:
            text = "".join(
                block.text
                for block in message.content
                if isinstance(block, TextContent)
            )
            prefix_match = text.startswith(COMMAND)
            mention_prefix = f"@{ctx.agent.address} "
            mention_prefix_length = len(mention_prefix)
            self_mention_match = text.startswith(mention_prefix)
            removed_prefix_length = mention_prefix_length if self_mention_match else 0
            incoming_length = len(text)
            text = text[removed_prefix_length:]
            normalized_command_length = len(text)
            normalized_prefix_match = text.startswith(COMMAND)
            if incoming_length > MAX_TEXT + len(COMMAND) + removed_prefix_length:
                reason = "oversized_text"
                reply = (
                    f"Input too large: maximum {MAX_TEXT} characters after /diagnose."
                )
            elif text.strip() in ("/start", "/cards"):
                reason = "cards"
                card_source = "entry_command"
                text = text.strip()
            elif text.lstrip().startswith("{"):
                reason = "cards"
                card_source = "callback"
            elif text == "/clear-chat":
                reason = "clear_chat"
                self.cards.clear(sender, ctx.session)
                reply = (
                    self.conversation.clear(sender, ctx.session)
                    if self.conversation
                    else (
                        "Conversational draft cleared; persisted purchase"
                        " records are unchanged."
                    )
                )
            elif text == "/policies":
                reason = "policies"
            elif text == "/sandbox" or text in SANDBOX_PREFIXES:
                reason = "sandbox_help"
                reply = SANDBOX_HELP
            elif text.startswith(tuple(p + " " for p in SANDBOX_PREFIXES)):
                try:
                    sandbox_command = parse_sandbox(text)
                    sandbox_page = (
                        details_page(text) if sandbox_command.action == "details" else 1
                    )
                    reason = "sandbox"
                except ValueError as exc:
                    reason = "invalid_sandbox_input"
                    reply = str(exc)
            elif text in ("/recommend", "/recommend-timeout", "/recommend-evidence"):
                reason = "recommend_help"
                reply = RECOMMEND_HELP
            elif text.startswith(
                ("/recommend ", "/recommend-timeout ", "/recommend-evidence ")
            ):
                try:
                    command, payload = text.split(" ", 1)
                    detail = None
                    if command == "/recommend-evidence":
                        policy_id, page, payload = payload.split(" ", 2)
                        if (
                            not page.isascii()
                            or not page.isdigit()
                            or not 1 <= int(page) <= 6
                        ):
                            raise ValueError(
                                "Evidence page must be 1–6. " + RECOMMEND_HELP
                            )
                        if not 1 <= len(policy_id) <= 64:
                            raise ValueError("Document ID must be 1–64 characters.")
                        detail = (policy_id, int(page))
                    recommendation_inputs = parse_recommendation(payload)
                    reason = "recommend"
                except ValueError as exc:
                    reason = "invalid_recommendation"
                    reply = str(exc) + " Use /recommend for explicit input help."
            elif text == "/stress-test":
                reason = "stress_help"
                reply = "Synthetic preset: /stress-test preset. Explicit form: " + USAGE
            elif text.startswith("/stress-test "):
                try:
                    scenario = parse_input(text[len("/stress-test ") :])
                    reason = "stress"
                except ValueError as exc:
                    reason = "invalid_scenario"
                    reply = str(exc)
            elif text.startswith("/inspect "):
                if 1 <= len(text[len("/inspect ") :]) <= 64:
                    reason = "inspect"
                else:
                    reason = "invalid_policy_id_length"
                    reply = (
                        "Use /inspect <allowlisted-policy-id> (maximum 64 characters)."
                    )
            elif (
                self.cards.active(sender, ctx.session)
                and text
                and not text.startswith("/")
            ):
                reason = "cards"
                card_source = "prose"
            elif (
                self.conversation
                and text
                and not text.startswith(("/", "@"))
                and len(text) <= 1500
                and not re.search(r"[/`\"“”]|https?://", text)
            ):
                reason = "conversation"
            elif not normalized_prefix_match or not text[len(COMMAND) :].strip():
                reason = (
                    "no_text"
                    if not text
                    else "missing_exact_prefix"
                    if not normalized_prefix_match
                    else "empty_payload"
                )
                reply = (
                    "Use /diagnose <nonempty text>, /policies, "
                    "/inspect <policy-id>, or /stress-test (help)."
                )
            else:
                reason = "accepted"
        LOGGER.info(
            "role=coordinator event=parser message_id=%s session=%s "
            "exact_prefix=%s accepted=%s reason=%s self_mention_match=%s "
            "normalized_exact_prefix=%s mention_prefix_length=%s "
            "removed_prefix_length=%s normalized_command_length=%s",
            message.msg_id,
            ctx.session,
            prefix_match,
            reason
            in (
                "accepted",
                "policies",
                "inspect",
                "stress",
                "recommend",
                "sandbox",
                "conversation",
                "cards",
            ),
            reason,
            self_mention_match,
            normalized_prefix_match,
            mention_prefix_length,
            removed_prefix_length,
            normalized_command_length,
        )
        if reason == "cards":
            card_response = await self.cards.handle(
                ctx, sender, text, source=card_source
            )
            outcome = "card_reply"
        elif reason == "conversation":

            async def privacy_notice(notice):
                delivery = await self.send_logged(
                    ctx,
                    sender,
                    ChatMessage(content=[TextContent(text=notice)]),
                    "privacy_send",
                )
                if delivery.status != DeliveryStatus.DELIVERED:
                    raise ValueError(
                        (
                            "Privacy notice could not be delivered. Use "
                            "/start; no message was parsed."
                        )
                    )

            reply = await self.conversation.handle(ctx, sender, text, privacy_notice)
            if len(reply.encode("utf-8")) > MAX_REPLY:
                reply = (
                    "Conversation result exceeds the reply bound. Use /start "
                    "and exact evidence commands; no material limits were truncated."
                )
            outcome = "conversation_reply"
        elif reason == "sandbox":
            conversational_draft = (
                self.conversation.drafts.get((sender, ctx.session))
                if self.conversation
                else None
            )
            result = await self.sandbox_operation(ctx, sender, sandbox_command)
            outcome = result.error or result.status
            if result.status == "success":
                if self.conversation and conversational_draft:
                    self.conversation.remember(
                        sender,
                        ctx.session,
                        SandboxReply.model_validate_json(result.payload_json),
                        conversational_draft,
                    )
                reply = present_sandbox(
                    SandboxReply.model_validate_json(result.payload_json),
                    page=sandbox_page,
                )
            else:
                reply = (
                    f"Sandbox operation incomplete: {result.error}. "
                    "Do not create another purchase or repeat payment blindly. "
                    "Reconcile this operation in the same sender/session:\n```text\n"
                    "/sandbox-status op-" + result.request_id.hex + "\n```"
                )
        elif reason == "recommend":
            result = await self.recommend(
                ctx, recommendation_inputs, test_timeout=command == "/recommend-timeout"
            )
            outcome = result.error or result.status
            if result.status == "success":
                report = Recommendation.model_validate_json(result.payload_json)
                try:
                    reply = (
                        present_evidence(report, *detail)
                        if detail
                        else present_recommendation(report)
                    )
                except PolicyError as exc:
                    reply = (
                        f"Recommendation display unavailable: {exc}. "
                        "Use /inspect <document-id> or request another evidence page; "
                        "no material details silently omitted."
                    )
            else:
                reply = (
                    f"Recommendation incomplete: {result.error}. "
                    "Provider/Investigator result unavailable; "
                    "no recommendation fabricated. Retry or obtain missing source data."
                )
        elif reason == "stress":
            result = await self.delegate(ctx, "", scenario=scenario)
            outcome = result.error or result.status
            reply = (
                present_comparison(Comparison.model_validate_json(result.report_json))
                if result.status == "success"
                else f"Stress test unavailable: {result.error}. No findings returned."
            )
        elif reason == "policies":
            outcome = "listed_policies"
            reply = policy_listing()
        elif reason == "inspect":
            result = await self.delegate(ctx, "", policy_id=text[len("/inspect ") :])
            outcome = result.error or result.status
            if result.status == "success":
                reply = present(
                    PolicyInspection.model_validate_json(result.report_json)
                )
            else:
                reply = (
                    f"Policy inspection unavailable: {result.error}. "
                    "No findings returned."
                )
        elif reason == "accepted":
            result = await self.delegate(ctx, text[len(COMMAND) :])
            outcome = result.error or result.status
            LOGGER.info(
                "role=coordinator event=diagnostic_result message_id=%s "
                "request_id=%s session=%s outcome=%s error=%s",
                message.msg_id,
                result.request_id,
                ctx.session,
                result.status,
                result.error,
            )
            explanation = "Local deterministic mode; no ASI model used."
            if self.explainer is not None:
                explanation = "Live mode; explanation skipped for failed diagnostic."
                if result.status == "success":
                    explanation = await self.explainer.explain(result)
            reply = json.dumps(
                {
                    "label": "Connectivity diagnostic, not policy analysis",
                    "in_reply_to": str(message.msg_id),
                    "result": result.model_dump(),
                    "explanation": explanation,
                },
                default=str,
            )
        # Reuse the incoming Context: SDK sends carry its envelope session UUID.
        response = card_response or ChatMessage(content=[TextContent(text=reply)])
        LOGGER.info(
            "role=coordinator event=reply_ready message_id=%s reply_id=%s session=%s",
            message.msg_id,
            response.msg_id,
            ctx.session,
        )
        await self.send_logged(ctx, sender, response, "reply_send")
        LOGGER.info(
            "role=coordinator event=chat_complete message_id=%s session=%s "
            "duration_ms=%.1f outcome=%s",
            message.msg_id,
            ctx.session,
            (monotonic() - started) * 1000,
            outcome,
        )

    async def acknowledge(self, ctx: Context, sender: str, msg: ChatAcknowledgement):
        LOGGER.info(
            "role=coordinator event=acp_ack_received acknowledged_id=%s session=%s",
            msg.acknowledged_msg_id,
            ctx.session,
        )

    def install(self, agent: Agent, *, live: bool = False):
        chat = Protocol(spec=chat_protocol_spec)
        chat.on_message(ChatMessage)(self.chat)
        chat.on_message(ChatAcknowledgement)(self.acknowledge)
        agent.include(chat, publish_manifest=live)
        diagnostic = Protocol(name="CoverWiseDiagnosticResult", version="0.1.0")
        diagnostic.on_message(DiagnosticResult)(self.accept_result)
        diagnostic.on_message(PolicyInspectionResult)(self.accept_result)
        diagnostic.on_message(StressTestResult)(self.accept_result)
        diagnostic.on_message(CatalogueResult)(self.accept_result)
        diagnostic.on_message(CandidateAssessmentResult)(self.accept_result)
        diagnostic.on_message(SandboxResult)(self.accept_result)
        agent.include(diagnostic)


def install_investigator(agent: Agent, coordinator: str):
    protocol = Protocol(name="CoverWiseDiagnosticTool", version="0.1.0")
    assessment_lane = asyncio.Semaphore(1)
    active_jobs = set()
    queued = 0

    @protocol.on_message(DiagnosticRequest, replies=DiagnosticResult)
    async def investigate(ctx: Context, sender: str, request: DiagnosticRequest):
        if sender != coordinator:
            LOGGER.info(
                "role=investigator request_id=%s outcome=rejected_sender",
                request.request_id,
            )
            return
        started = monotonic()
        result = diagnose(request)
        await ctx.send(sender, result)
        LOGGER.info(
            "role=investigator request_id=%s duration_ms=%.1f outcome=%s",
            request.request_id,
            (monotonic() - started) * 1000,
            result.status,
        )

    @protocol.on_message(PolicyInspectionRequest, replies=PolicyInspectionResult)
    async def inspect(ctx: Context, sender: str, request: PolicyInspectionRequest):
        if sender != coordinator:
            LOGGER.info(
                "role=investigator request_id=%s outcome=rejected_sender",
                request.request_id,
            )
            return
        started = monotonic()
        try:
            report = await asyncio.to_thread(inspect_policy, request.policy_id)
            serialized = report.model_dump_json()
            if len(serialized.encode("utf-8")) > 65536:
                raise PolicyError("result_too_large")
            result = PolicyInspectionResult(
                request_id=request.request_id,
                policy_id=request.policy_id,
                status="success",
                report_json=serialized,
            )
        except Exception as exc:
            code = str(exc) if isinstance(exc, PolicyError) else "extraction_failed"
            result = PolicyInspectionResult(
                request_id=request.request_id,
                policy_id=request.policy_id,
                status="error",
                error=code if code in ERROR_CODES else "extraction_failed",
            )
        await ctx.send(sender, result)
        LOGGER.info(
            "role=investigator request_id=%s duration_ms=%.1f outcome=%s",
            request.request_id,
            (monotonic() - started) * 1000,
            result.status,
        )

    @protocol.on_message(StressTestRequest, replies=StressTestResult)
    async def stress_test(ctx: Context, sender: str, request: StressTestRequest):
        if sender != coordinator:
            return
        try:
            scenario = JobChangeScenario.model_validate_json(request.scenario_json)
        except ValueError:
            await ctx.send(
                sender,
                StressTestResult(
                    request_id=request.request_id,
                    status="error",
                    error="invalid_scenario",
                ),
            )
            return
        try:
            report = await asyncio.to_thread(run_stress, scenario)
            serialized = report.model_dump_json()
            present_comparison(report)
            if len(serialized.encode("utf-8")) > 131072:
                raise PolicyError("result_too_large")
            result = StressTestResult(
                request_id=request.request_id, status="success", report_json=serialized
            )
        except Exception as exc:
            code = str(exc) if isinstance(exc, PolicyError) else "extraction_failed"
            result = StressTestResult(
                request_id=request.request_id,
                status="error",
                error=code if code in ERROR_CODES else "extraction_failed",
            )
        await ctx.send(sender, result)

    @protocol.on_message(CandidateAssessmentRequest, replies=CandidateAssessmentResult)
    async def candidates(ctx, sender: str, request: CandidateAssessmentRequest):
        nonlocal queued
        if sender != coordinator:
            return
        received = monotonic()
        session = ctx.session
        LOGGER.info(
            "role=investigator event=handler_received stage=investigator_assessment "
            "request_id=%s session=%s received_monotonic=%.6f injection=False",
            request.request_id,
            session,
            received,
        )
        try:
            inputs = RecommendationInput.model_validate_json(request.input_json)
            snapshot = CatalogueSnapshot.model_validate_json(request.catalogue_json)
        except ValueError:
            await ctx.send(
                sender,
                CandidateAssessmentResult(
                    request_id=request.request_id, status="error", error="invalid_input"
                ),
            )
            return
        if queued >= MAX_PENDING:
            await ctx.send(
                sender,
                CandidateAssessmentResult(
                    request_id=request.request_id, status="error", error="busy"
                ),
            )
            return
        queued += 1
        try:
            await assessment_lane.acquire()
        finally:
            queued -= 1
        submitted = monotonic()
        LOGGER.info(
            "role=investigator event=assessment_admitted stage=investigator_assessment "
            "request_id=%s session=%s queue_scope=assessment_lane "
            "queue_wait_ms=%.3f injection=False",
            request.request_id,
            session,
            (submitted - received) * 1000,
        )

        def work():
            started = monotonic()
            LOGGER.info(
                "role=investigator event=assessment_started "
                "stage=investigator_assessment "
                "request_id=%s session=%s executor_wait_ms=%.3f injection=False",
                request.request_id,
                session,
                (started - submitted) * 1000,
            )
            try:
                report = assess_candidates(inputs, snapshot)
                payload = report.model_dump_json()
                present_recommendation(report)
                if len(payload.encode("utf-8")) > 262144:
                    raise PolicyError("result_too_large")
                return CandidateAssessmentResult(
                    request_id=request.request_id,
                    status="success",
                    payload_json=payload,
                )
            except Exception as exc:
                code = str(exc) if isinstance(exc, PolicyError) else "extraction_failed"
                allowed = ERROR_CODES | {"catalogue_pdf_disagreement"}
                return CandidateAssessmentResult(
                    request_id=request.request_id,
                    status="error",
                    error=code if code in allowed else "extraction_failed",
                )
            finally:
                LOGGER.info(
                    "role=investigator event=assessment_finished "
                    "stage=investigator_assessment request_id=%s session=%s "
                    "assessment_duration_ms=%.3f injection=False",
                    request.request_id,
                    session,
                    (monotonic() - started) * 1000,
                )

        # Cancellation of an SDK handler must not free a still-running worker's lane.
        job = asyncio.create_task(asyncio.to_thread(work))
        active_jobs.add(job)
        handler_cancelled = False

        def done(task):
            active_jobs.discard(task)
            assessment_lane.release()
            error = (
                type(task.exception()).__name__
                if not task.cancelled() and task.exception()
                else "none"
            )
            LOGGER.info(
                "role=investigator event=worker_cleanup stage=investigator_assessment "
                "request_id=%s session=%s lane_released=True handler_cancelled=%s "
                "worker_cancelled=%s error_type=%s injection=False",
                request.request_id,
                session,
                handler_cancelled,
                task.cancelled(),
                error,
            )

        job.add_done_callback(done)
        try:
            result = await asyncio.shield(job)
        except asyncio.CancelledError:
            handler_cancelled = True
            LOGGER.info(
                "role=investigator event=handler_cancelled "
                "stage=investigator_assessment "
                "request_id=%s session=%s worker_continues=True injection=False",
                request.request_id,
                session,
            )
            raise
        sending = monotonic()
        try:
            await ctx.send(sender, result)
        finally:
            LOGGER.info(
                "role=investigator event=response_send stage=investigator_assessment "
                "request_id=%s session=%s response_send_ms=%.3f injection=False",
                request.request_id,
                session,
                (monotonic() - sending) * 1000,
            )

    agent.include(protocol)


async def offline_recommend(inputs, test_timeout=False, *, timeout=15):
    """Offline SDK-handler harness; no Agent construction or real transport."""
    from types import SimpleNamespace

    from uagents import Model

    from coverwise.provider import install_provider

    service = Coordinator(
        "offline-investigator",
        timeout=0.05 if test_timeout else timeout,
        provider="offline-provider",
    )
    protocols = []
    install_investigator(
        SimpleNamespace(include=protocols.append), "offline-coordinator"
    )
    install_provider(SimpleNamespace(include=protocols.append), "offline-coordinator")
    session = uuid4()

    async def send(destination, message):
        if destination == "offline-coordinator":
            await service.accept_result(coordinator_ctx, tool_sender[0], message)
        else:
            protocol = protocols[1 if destination == "offline-provider" else 0]
            handler = protocol.signed_message_handlers[
                Model.build_schema_digest(type(message))
            ]
            tool_sender[0] = destination
            await handler(tool_ctx, "offline-coordinator", message)
        return SimpleNamespace(status=DeliveryStatus.DELIVERED)

    tool_sender = [None]
    coordinator_ctx = SimpleNamespace(session=session, send=send)
    tool_ctx = SimpleNamespace(session=session, send=send)
    return await service.recommend(coordinator_ctx, inputs, test_timeout=test_timeout)
