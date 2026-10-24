"""Exact deterministic commands and state-specific reviews; no model decisions."""

import json
from datetime import timezone

from pydantic import ValidationError

from coverwise.money import display_money, inr
from coverwise.policies import MAX_REPLY, PolicyError
from coverwise.recommend import input_text
from coverwise.recommend import parse_input as recommendation_input
from coverwise.sandbox import LABEL
from coverwise.sandbox_contracts import ApplicationFields, SandboxCommand, SandboxReply

HELP = (
    "Sandbox/demo: quote → review → deliberate approval → mock payment → status. "
    "No real policy or money. Start the labelled fictional employer-only demo:\n"
    "```text\n/quote preset\n```\n"
    "Then copy the exact generated apply, approve, cancel or status command from "
    "the reply. Do not type placeholders or a bare yes. Complete persisted terms "
    "and evidence: use the generated /sandbox-details command; append a page "
    "number from 1 to 64 or copy its next-page command.\n"
    "For explicit inputs, the syntax is /quote followed by product ID and the "
    "eleven /recommend fields; send /recommend for field guidance. "
    "Synthetic explicit example:\n```text\n"
    "/quote candidate-horizon employer-only 3000000 100000000 uncapped-private "
    "2027-01-01 2026-12-31 2027-02-01 2027-01-15 2027-02-10 member-02 "
    "member-01:1992-04-10:self:absent,member-02:1994-08-15:spouse:absent\n```\n"
    "Use synthetic data only; never send card, banking, Aadhaar or PAN details."
)
START = (
    "Native cards: /cards (also opened by /start). "
    "You can ask a job-change insurance question or say 'Show me the job-change "
    "demo'. Conversational messages may be processed by ASI; use synthetic data "
    "only. /clear-chat clears drafts, not purchase records. "
    "CoverWise explains fictional policy evidence and dated coverage limits. "
    "Choose a labelled synthetic demo (these are not your personal details):\n"
    "Compare existing policies:\n```text\n/stress-test preset\n```\n"
    "Compare candidate plans:\n```text\n/recommend preset\n```\n"
    "Keep existing personal cover in the comparison:\n"
    "```text\n/recommend preset-existing\n```\n"
    "Try a sandbox quote and review:\n```text\n/quote preset\n```\n"
    "A quote never purchases anything. Review first, then deliberately copy the "
    "generated approval command. No real policy or money. "
    "Send /sandbox for workflow/explicit-input guidance, /recommend or "
    "/stress-test for input fields, or /policies for documents. "
    "Only use synthetic data."
)
PREFIXES = (
    "/quote",
    "/apply",
    "/review",
    "/approve",
    "/sandbox-status",
    "/sandbox-details",
    "/cancel",
)


def parse_command(text):
    if len(text) > 2000:
        raise ValueError("Sandbox input exceeds 2000 characters. Use /sandbox.")
    text = text.strip()
    parts = text.split(" ")
    if any(not p for p in parts):
        raise ValueError("Use single spaces and every required field. " + HELP)
    command, *args = parts
    try:
        if command == "/quote":
            if args == ["preset"]:
                product, inputs = "candidate-horizon", recommendation_input("preset")
            else:
                product, payload = text[len("/quote ") :].split(" ", 1)
                inputs = recommendation_input(payload)
            return SandboxCommand(action="quote", product_id=product, inputs=inputs)
        if command == "/apply" and len(args) == 3 and args[1] == "confirm-demo":
            return SandboxCommand(
                action="apply",
                reference=args[0],
                application=ApplicationFields(
                    confirm_demo=True, payment_outcome=args[2]
                ),
            )
        if command == "/review" and len(args) == 1:
            return SandboxCommand(action="review", reference=args[0])
        if command == "/review" and len(args) == 4 and args[2] == "confirm-demo":
            return SandboxCommand(
                action="review",
                reference=args[0],
                replacement_quote=args[1],
                application=ApplicationFields(
                    confirm_demo=True, payment_outcome=args[3]
                ),
            )
        if (
            command == "/approve"
            and len(args) == 3
            and args[1].isascii()
            and args[1].isdigit()
        ):
            return SandboxCommand(
                action="approve",
                reference=args[0],
                revision=int(args[1]),
                challenge=args[2],
            )
        if command in ("/sandbox-status", "/cancel") and len(args) == 1:
            return SandboxCommand(
                action="status" if command == "/sandbox-status" else "cancel",
                reference=args[0],
            )
        if command == "/sandbox-details" and len(args) in (1, 2):
            details_page(text)
            return SandboxCommand(
                action="details",
                reference=args[0],
            )
    except ValidationError as exc:
        locations = {tuple(e["loc"]) for e in exc.errors(include_input=False)}
        if ("application", "payment_outcome") in locations or (
            "payment_outcome",
        ) in locations:
            reason = "Use exactly success, failure or unknown as the demo outcome."
        elif ("reference",) in locations:
            reason = "Copy the complete quote/application reference from its reply."
        else:
            reason = "Copy the exact generated command; do not include code fences."
        raise ValueError(
            "Invalid sandbox fields. " + reason + " Use /sandbox."
        ) from None
    except ValueError:
        raise ValueError(
            "Invalid sandbox fields; use only synthetic demo data. " + HELP
        ) from None
    raise ValueError("Supply the exact sandbox command and required fields. " + HELP)


def details_page(text):
    value = text.split(" ")[2] if len(text.split(" ")) == 3 else "1"
    if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 64:
        raise ValueError("Choose a details page from 1 to 64.")
    return int(value)


def quote_command(quote):
    return f"/quote {quote.product.product_id} {input_text(quote.inputs)}"


def command_block(command):
    return "```text\n" + command + "\n```"


def utc(value):
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def details_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def detail_records(value, path=()):
    record = dict(path=list(path), kind="value", value=value)
    if len(details_json(record).encode("utf-8")) <= 6000:
        yield record
    elif isinstance(value, (dict, list)):
        yield dict(
            path=list(path),
            kind="object" if isinstance(value, dict) else "array",
            length=len(value),
        )
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for key, child in items:
            yield from detail_records(child, (*path, key))
    elif isinstance(value, str):
        offset = 0
        while offset < len(value):
            record = dict(
                path=list(path),
                kind="string_segment",
                offset=offset,
                total_characters=len(value),
                value="",
            )
            low, high = 0, len(value) - offset
            while low < high:
                middle = (low + high + 1) // 2
                record["value"] = value[offset : offset + middle]
                if len(details_json(record).encode("utf-8")) <= 6000:
                    low = middle
                else:
                    high = middle - 1
            if low == 0:
                raise PolicyError("result_too_large")
            record["value"] = value[offset : offset + low]
            yield record
            offset += low
    else:
        raise PolicyError("result_too_large")


def render_details_page(reference, page, total, records, *, invalid=False):
    envelope = dict(reference=reference, page=page, total=total, records=records)
    if invalid:
        envelope["error"] = "page_out_of_range"
    lines = [
        LABEL,
        f"Persisted terms/evidence: {reference}; page {page}/{total}.",
        "Records identify paths in the persisted snapshot. "
        "Approval expiry is historical metadata, not an action.",
        "```json\n" + details_json(envelope) + "\n```",
    ]
    if invalid:
        lines += [
            "Choose a valid page:",
            command_block(f"/sandbox-details {reference} 1"),
        ]
    elif page > 1:
        lines += [
            "Previous details page:",
            command_block(f"/sandbox-details {reference} {page - 1}"),
        ]
    if not invalid and page < total:
        lines += [
            "Next details page:",
            command_block(f"/sandbox-details {reference} {page + 1}"),
        ]
    lines += ["Current status:", command_block("/sandbox-status " + reference)]
    return "\n".join(lines)


def present_details(reply, page):
    # Explicit whitelist excludes plaintext challenges and approval commands.
    snapshot = dict(
        state=reply.state,
        quote=reply.quote.model_dump(mode="json") if reply.quote else None,
        application=(
            reply.application.model_dump(mode="json") if reply.application else None
        ),
        payment=reply.payment.model_dump(mode="json") if reply.payment else None,
    )
    pages, current = [], []
    for record in detail_records(snapshot):
        candidate = [*current, record]
        # Reserve the full envelope and both navigation commands, including digits.
        rendered = render_details_page(reply.reference, 32, 64, candidate)
        if len(rendered.encode("utf-8")) > MAX_REPLY:
            if not current:
                raise PolicyError("result_too_large")
            pages.append(current)
            current = [record]
        else:
            current = candidate
    pages.append(current)
    if len(pages) > 64:
        raise PolicyError("result_too_large")
    valid = 1 <= page <= len(pages)
    text = render_details_page(
        reply.reference,
        page,
        len(pages),
        pages[page - 1] if valid else [],
        invalid=not valid,
    )
    if len(text.encode("utf-8")) > MAX_REPLY:
        raise PolicyError("result_too_large")
    return text


def present(reply: SandboxReply, *, page=1, summary=False):
    if reply.action == "details" and reply.state != "rejected" and not summary:
        return present_details(reply, page)
    app = reply.application
    q = reply.quote or (app.quote if app else None)
    lines = [LABEL, "State: " + reply.state]
    if q:
        lines.append(
            f"{q.product.name} / {q.product.insurer}; {inr(q.premium_paise)}/year INR."
        )
    if app:
        lines.append("Application: " + app.application_id)
    elif not q:
        lines.append("Reference: " + reply.reference)
    if reply.state in ("quote_active", "quote_expired", "review") and q:
        lines += [
            "Members: "
            + "; ".join(
                f"{m.member_id} ({m.relationship}"
                + (
                    f", born {m.date_of_birth}, pre-existing {m.preexisting}"
                    if reply.state == "review"
                    else ""
                )
                + ")"
                for m in q.inputs.members
            ),
            f"Proposed cover {q.cover_start} to {q.cover_end}, inclusive.",
            f"Illness wait {q.wait_start} to {q.wait_end}, inclusive; "
            f"first post-wait day {q.first_post_wait_day}. "
            "No continuity credit/waiver.",
            f"Illustrative illness hospitalization {q.inputs.immediate_event}: "
            f"{q.immediate_status}. "
            "An event inside the wait is excluded; purchase does not remove the wait.",
            f"Quote: {q.quote_id}; expires {utc(q.expires_at)}.",
        ]
    if reply.state == "review" and app:
        lines += [
            "Material restrictions:\n"
            + "\n".join("- " + display_money(r) for r in q.restrictions),
            "Synthetic disclosures: " + "; ".join(q.required_disclosures),
            f"Application review revision {app.revision}; "
            f"approval expiry {utc(app.challenge_expires_at)}.",
            f"Sandbox payment test outcome: {app.fields.payment_outcome}. "
            "Approval is scoped to this observed sender/session, "
            "not verified identity. It authorizes the exact reviewed terms; "
            "changes require a fresh review/approval.",
        ]
    if reply.payment:
        p = reply.payment
        lines += [
            f"Payment: {p.payment_id} ({p.state}); amount {inr(p.amount_paise)} INR.",
            "Transaction: " + p.transaction_reference,
        ]
        if p.confirmation:
            lines.append("Confirmation: " + p.confirmation)
    outcomes = {
        "completed": "Sandbox purchase completed. Status returns the recorded result. "
        "Future claims are not guaranteed.",
        "payment_pending": "Payment outcome is unknown. Reconciliation is required. "
        "Do not pay again; use status below.",
        "operation_pending": "Operation outcome is not known. Reconcile status; "
        "do not create another purchase or repeat payment.",
        "failed": "Payment definitely failed. No purchase completed and no "
        "confirmation issued. Status retrieves the recorded failure.",
        "cancelled": "Cancelled before execution. No purchase completed.",
        "needs_review": "Prior review is no longer actionable. Retrieve terms "
        "and follow the new quote/review guidance below.",
        "approved": "Approval recorded; completion is not established. "
        "Use status to reconcile the authorized operation.",
        "quote_expired": "This quote has expired. "
        "A fresh quote and review/approval are required.",
    }
    if reply.state in outcomes:
        lines.append(outcomes[reply.state])
    if reply.error_code:
        lines.append(
            "Result: "
            + reply.error_code
            + ". Use scoped status; no success is assumed."
        )
    if q and reply.state not in ("quote_active", "quote_expired", "review"):
        lines.append(
            f"Illness wait {q.wait_start} to {q.wait_end}; "
            "policy exclusions still apply. No claim payment is promised."
        )
    if reply.state in ("quote_active", "quote_expired", "review"):
        lines.append(
            "Date checks do not guarantee claim approval or payment. "
            "Complete terms and evidence are available below."
        )
    for command in reply.next_commands:
        verb = command.split(" ", 1)[0]
        labels = {
            "/apply": "Prepare review (no payment yet):",
            "/approve": "Approve this exact review:",
            "/cancel": "Cancel before execution:",
            "/review": "Request a fresh review/challenge:",
            "/quote": "Request a fresh quote:",
            "/sandbox-status": "Retrieve/reconcile status:",
        }
        if verb in labels:
            lines.append(labels[verb])
        lines.append(command_block(command))
    if q:
        lines += [
            "Complete persisted terms and evidence:",
            command_block("/sandbox-details " + reply.reference),
        ]
    text = "\n".join(lines)
    if len(text) > MAX_REPLY:
        raise PolicyError("result_too_large")
    return text
