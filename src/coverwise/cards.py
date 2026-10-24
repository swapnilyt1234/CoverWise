"""Native cards: scoped inputs and opaque actions over existing SDK services."""

import asyncio
import json
import logging
import re
import secrets
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from time import monotonic
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, ValidationError
from uagents_core.contrib.protocols.chat import ChatMessage, TextContent

from coverwise.card_schemas import (
    CTA,
    Badge,
    Carousel,
    Detail,
    Form,
    FormField,
    Item,
    Option,
    Review,
    Row,
    message,
)
from coverwise.contracts import Contract, PolicyInspection
from coverwise.conversation import paise
from coverwise.money import display_money, inr
from coverwise.policies import MAX_REPLY, REGISTRY, PolicyError
from coverwise.recommend import (
    Member,
    Recommendation,
    RecommendationInput,
    parse_input,
    present_evidence,
    reference,
)
from coverwise.recommend import (
    present as present_recommendation,
)
from coverwise.sandbox_contracts import ApplicationFields, SandboxCommand, SandboxReply
from coverwise.sandbox_ui import present as present_sandbox
from coverwise.sandbox_ui import utc
from coverwise.stress import DAY, interpret

TTL = 900
MAX_SESSIONS = 128
MAX_ACTIONS = 1024
LOGGER = logging.getLogger("coverwise")
CARD_TRACE = ContextVar("coverwise_card_trace", default=None)
ONE_SHOT = {
    "entry",
    "example",
    "job",
    "job_confirm",
    "needs",
    "scenario",
    "scenario_submit",
    "confirm",
    "edit",
    "cancel",
    "restart",
}
ENTRY_NOTICE = "Demo environment — sample policies — no real insurance issued."
NOTICE = "Sandbox/demo — no real policy issued; no real money moved."
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=64)]


class Callback(Contract):
    action: Literal["coverwise_card"]
    card_token: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{32}$")]


class CallbackMetadata(Contract):
    approved: Annotated[bool, Field(strict=True)] | None = None


class ExampleForm(Contract):
    sample_cover: Literal["employer-only", "existing-personal"]


class JobForm(Contract):
    final_employment: Text
    new_cover_known: Literal["known", "unknown"]
    new_start: Text = ""
    current_cover: Literal["employer", "personal", "both", "unsure"]
    policy: Text


class NeedsForm(Contract):
    budget_rupees: Text
    who: Literal["self", "self-spouse"]
    self_dob: Text
    spouse_dob: Text = ""
    self_disclosure: Literal["absent", "present", "unknown", ""] = ""
    spouse_disclosure: Literal["absent", "present", "unknown", ""] = ""
    minimum_rupees: Text
    room: Literal["uncapped-private", "any-room"]
    current_cover: Literal["employer", "personal", "both", "unsure"]


class ScenarioForm(Contract):
    policy: Text = ""
    final_employment: Text = ""
    new_start: Text = ""
    proposed_start: Text
    immediate_event: Text
    later_event: Text
    event_member: Literal["member-01", "member-02"]


@dataclass
class JobDraft:
    final_employment: date
    new_start: date | None
    current_cover: str
    policy: str


@dataclass
class NeedsDraft:
    path: str | None
    members: list[Member]
    annual_budget_paise: int
    minimum_family_limit_paise: int
    room_requirement: str
    job: JobDraft | None = None


@dataclass
class InputsDraft:
    inputs: RecommendationInput
    policy: str
    demo: bool = False
    needs: NeedsDraft | None = None


@dataclass
class Session:
    expires: float
    epoch: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    waiting: int = 0
    review: SandboxReply | None = None
    stage: str = "entry"


@dataclass
class Action:
    scope: tuple
    epoch: int
    expires: float
    kind: Literal[
        "entry",
        "example",
        "job",
        "job_confirm",
        "needs",
        "scenario",
        "scenario_submit",
        "policy_details",
        "confirm",
        "edit",
        "cancel",
        "candidate",
        "evidence",
        "comparison",
        "operation",
        "approve",
        "restart",
    ]
    data: (
        JobDraft
        | NeedsDraft
        | PolicyInspection
        | str
        | InputsDraft
        | Recommendation
        | SandboxCommand
        | tuple[Recommendation, str, int]
        | None
    ) = None
    recovery_ref: str | None = None
    source_stage: str = "entry"
    used: bool = False


def row(label, value):
    return Row(label=label, value=str(value))


def text_reply(text):
    if len(text.encode("utf-8")) > MAX_REPLY:
        text = (
            "Details exceed the reply bound. Use /sandbox-details with its page number."
        )
    return ChatMessage(content=[TextContent(text=text)])


def exact_date(value, name):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Enter {name} as YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Enter a valid calendar date for {name}.") from None
    if not date(1900, 1, 1) <= parsed <= date(2100, 12, 31):
        raise ValueError(f"Enter {name} between 1900 and 2100.")
    return parsed


def rupees(value, name):
    try:
        return paise(value if value.startswith("₹") else value + " rupees")
    except ValueError:
        raise ValueError(
            f"Enter {name} in rupees, with up to two decimal places."
        ) from None


def job_input(raw):
    last = exact_date(raw.final_employment, "your last working day")
    start = (
        exact_date(raw.new_start, "the new cover start date")
        if raw.new_cover_known == "known"
        else None
    )
    if raw.new_cover_known == "unknown" and raw.new_start:
        raise ValueError(
            "Choose whether the new cover date is known, then enter that date."
        )
    if start is not None and start <= last:
        raise ValueError("New cover must start after your last working day.")
    if raw.policy not in REGISTRY:
        raise ValueError("Choose a sample policy from the list.")
    return JobDraft(last, start, raw.current_cover, raw.policy)


def needs_input(raw, job=None):
    members = [
        Member(
            member_id="member-01",
            relationship="self",
            date_of_birth=exact_date(raw.self_dob, "your date of birth"),
            preexisting=raw.self_disclosure or "unknown",
        )
    ]
    if raw.who == "self-spouse":
        members.append(
            Member(
                member_id="member-02",
                relationship="spouse",
                date_of_birth=exact_date(raw.spouse_dob, "your spouse's date of birth"),
                preexisting=raw.spouse_disclosure or "unknown",
            )
        )
    elif raw.spouse_dob or raw.spouse_disclosure not in ("", "unknown"):
        raise ValueError("Choose self and spouse to include your spouse's details.")
    path = (
        None
        if raw.current_cover == "unsure"
        else "employer-only"
        if raw.current_cover == "employer"
        else "existing-personal"
    )
    limit = rupees(raw.minimum_rupees, "the coverage amount")
    if not limit:
        raise ValueError("Enter a coverage amount greater than zero.")
    return NeedsDraft(
        path,
        members,
        rupees(raw.budget_rupees, "your annual budget"),
        limit,
        raw.room,
        job,
    )


def comparison_input(needs, raw):
    if needs.path is None:
        raise ValueError(
            "Confirm your current cover before comparing plans; "
            "unknown cover cannot be assumed absent."
        )
    job = needs.job
    if job and (
        raw.policy or raw.final_employment or (job.new_start and raw.new_start)
    ):
        raise ValueError("Use the job step to change the dates you already reviewed.")
    last = (
        job.final_employment
        if job
        else exact_date(raw.final_employment, "your last working day")
    )
    start = (
        job.new_start
        if job and job.new_start
        else exact_date(raw.new_start, "the assumed new cover start date")
    )
    policy = job.policy if job else raw.policy
    if policy not in REGISTRY:
        raise ValueError("Choose a sample policy from the list.")
    return InputsDraft(
        RecommendationInput(
            path=needs.path,
            members=needs.members,
            annual_budget_paise=needs.annual_budget_paise,
            minimum_family_limit_paise=needs.minimum_family_limit_paise,
            room_requirement=needs.room_requirement,
            proposed_start=exact_date(raw.proposed_start, "the policy start date"),
            final_employment=last,
            assumed_new_employer_start=start,
            immediate_event=exact_date(raw.immediate_event, "the illness date"),
            later_event=exact_date(raw.later_event, "the later illness date"),
            event_member_id=raw.event_member,
            event_type="illness_hospitalization",
        ),
        policy,
        needs=needs,
    )


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate callback fields are not accepted.")
        result[key] = value
    return result


class Cards:
    def __init__(self, services, *, timer=monotonic, clock=None):
        self.services, self.timer = services, timer
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sessions: dict[tuple, Session] = {}
        self.actions: dict[str, Action] = {}

    def prune(self):
        now = self.timer()
        for scope, session in list(self.sessions.items()):
            if session.expires <= now and not session.lock.locked():
                del self.sessions[scope]
        for token, action in list(self.actions.items()):
            if action.expires <= now or action.scope not in self.sessions:
                del self.actions[token]

    def active(self, sender, session):
        self.prune()
        return (sender, session) in self.sessions

    def clear(self, sender, session):
        scope = (sender, session)
        self.sessions.pop(scope, None)
        self.actions = {t: a for t, a in self.actions.items() if a.scope != scope}

    def cta(self, scope, session, label, kind, data=None, *, primary=None, ttl=TTL):
        self.prune()
        if len(self.actions) >= MAX_ACTIONS:
            self.actions.pop(next(iter(self.actions)))
        token = secrets.token_urlsafe(24)
        self.actions[token] = Action(
            scope,
            session.epoch,
            self.timer() + ttl,
            kind,
            data,
            source_stage=session.stage,
        )
        return CTA(
            label=label,
            primary=primary,
            selection={"action": "coverwise_card", "card_token": token},
        )

    def restart_prompt(self, scope, session, text, reason, *, validation="rejected"):
        trace = CARD_TRACE.get()
        if trace is not None:
            trace["validation"], trace["fallback"] = validation, reason
        return message(
            text,
            Detail(
                title="Card response needs attention",
                summary_rows=[
                    row(
                        "Next step",
                        "Use the current card or restart this draft. "
                        "Restarting does not cancel or repeat a persisted transaction.",
                    )
                ],
                ctas=[self.cta(scope, session, "Restart cards", "restart")],
            ),
        )

    def form(self, scope, session, stage="entry", data=None, error=None):
        if stage not in ("entry", "example", "job", "needs", "scenario"):
            raise ValueError("unsupported card stage")
        session.stage = stage
        if error:
            trace = CARD_TRACE.get()
            if trace is not None:
                trace["validation"], trace["fallback"] = "invalid", "form_validation"
        if stage == "entry":
            choices = [
                ("job", "I'm changing jobs", "Check when employer cover ends."),
                (
                    "needs",
                    "Compare health plans",
                    "Explore plans against your requirements.",
                ),
                (
                    "example",
                    "Try an example",
                    "Walk through a sample comparison and sandbox purchase.",
                ),
            ]
            return message(
                ENTRY_NOTICE,
                Carousel(
                    title="Let's check your insurance",
                    subtitle="Tell us what you need help with.",
                    items=[
                        Item(
                            id=key,
                            title=title,
                            subtitle=subtitle,
                            badges=[],
                            secondary_text="",
                            primary_cta=self.cta(
                                scope, session, "Continue", "entry", key
                            ),
                        )
                        for key, title, subtitle in choices
                    ],
                ),
            )
        fields = []

        def add(name, label, options=None, required=False):
            fields.append(
                FormField(
                    name=name,
                    label=label,
                    kind="select" if options else "text",
                    required=required,
                    options=[
                        Option(value=value, label=label) for value, label in options
                    ]
                    if options
                    else None,
                )
            )

        cover = [
            ("employer", "Employer"),
            ("personal", "Personal"),
            ("both", "Both"),
            ("unsure", "Unsure"),
        ]
        policies = [(identifier, spec.title) for identifier, spec in REGISTRY.items()]
        if stage == "example":
            title, narration, kind = (
                "Try an example",
                "Choose the cover you want to explore.",
                "example",
            )
            add(
                "sample_cover",
                "Sample cover",
                [
                    ("employer-only", "Employer cover only"),
                    ("existing-personal", "Employer and existing personal cover"),
                ],
                True,
            )
        elif stage == "job":
            title, narration, kind = "Changing jobs", "Enter the dates you know.", "job"
            add("final_employment", "Last working day (YYYY-MM-DD)", required=True)
            add(
                "new_cover_known",
                "Do you know when new cover starts?",
                [("known", "I know the date"), ("unknown", "I don't know")],
                True,
            )
            add("new_start", "New employer cover start date (YYYY-MM-DD, if known)")
            add("current_cover", "Current cover", cover, True)
            add("policy", "Choose a sample policy", policies, True)
        elif stage == "needs":
            title, narration, kind = (
                "Compare health plans",
                "Tell us who needs cover and what matters to you.",
                "needs",
            )
            add("budget_rupees", "Annual budget (₹)", required=True)
            add(
                "who",
                "Who needs cover?",
                [("self", "Self"), ("self-spouse", "Self and spouse")],
                True,
            )
            add("self_dob", "Your date of birth (YYYY-MM-DD)", required=True)
            add("spouse_dob", "Spouse's date of birth (YYYY-MM-DD, if included)")
            disclosures = [
                ("unknown", "Not known or not disclosed"),
                ("absent", "No existing conditions declared"),
                ("present", "Existing conditions declared"),
            ]
            add("self_disclosure", "Your health disclosure", disclosures)
            add("spouse_disclosure", "Spouse's health disclosure", disclosures)
            add("minimum_rupees", "Coverage amount (₹)", required=True)
            add(
                "room",
                "Room preference",
                [
                    ("uncapped-private", "Private room without a daily cap"),
                    ("any-room", "Any room"),
                ],
                True,
            )
            add("current_cover", "Current cover", cover, True)
        else:
            title, narration, kind = (
                "Optional illness scenario",
                "These dates are needed only for the dated comparison.",
                "scenario_submit",
            )
            if data.job is None:
                add("policy", "Choose a sample policy", policies, True)
                add("final_employment", "Last working day (YYYY-MM-DD)", required=True)
            if data.job is None or data.job.new_start is None:
                add("new_start", "Assumed new cover start (YYYY-MM-DD)", required=True)
            add("proposed_start", "New policy start (YYYY-MM-DD)", required=True)
            add("immediate_event", "Illness date (YYYY-MM-DD)", required=True)
            add("later_event", "Later illness date (YYYY-MM-DD)", required=True)
            add(
                "event_member",
                "Who is this scenario for?",
                [
                    (m.member_id, "You" if m.relationship == "self" else "Your spouse")
                    for m in data.members
                ],
                True,
            )
        return message(
            error or narration,
            Form(
                title=title,
                fields=fields,
                submit_cta=self.cta(
                    scope,
                    session,
                    "Review details"
                    if stage in ("job", "example", "needs", "scenario")
                    else "Continue",
                    kind,
                    data,
                ),
            ),
        )

    def job_review(self, scope, session, draft, error=None):
        session.stage = "job_review"
        rows = [
            row("Last working day", draft.final_employment),
            row(
                "New cover start (not verified)",
                draft.new_start or "Not known — no gap duration assumed",
            ),
            row("Current cover", draft.current_cover.capitalize()),
            row("Sample policy", REGISTRY[draft.policy].title),
            row(
                "Important",
                "A sample document does not establish your actual insurance.",
            ),
        ]
        return message(
            error or "Review the details before checking the sample policy.",
            Review(
                title="Review details",
                summary_rows=rows,
                approve_cta=self.cta(
                    scope, session, "Check policy", "job_confirm", draft, primary=True
                ),
                reject_cta=self.cta(scope, session, "Edit details", "entry", "job"),
            ),
        )

    def needs_review(self, scope, session, draft):
        session.stage = "needs_review"
        rows = [
            row("Annual budget", inr(draft.annual_budget_paise)),
            row("Coverage amount", inr(draft.minimum_family_limit_paise)),
            row(
                "Room preference",
                "Private room without a daily cap"
                if draft.room_requirement == "uncapped-private"
                else "Any room",
            ),
            row(
                "Current cover",
                "Unsure — clarify before assessment"
                if draft.path is None
                else "Employer only"
                if draft.path == "employer-only"
                else "Existing personal cover retained",
            ),
        ]
        rows += [
            row(
                "You" if m.relationship == "self" else "Your spouse",
                f"Born {m.date_of_birth}; health disclosure: {m.preexisting}",
            )
            for m in draft.members
        ]
        return message(
            "Dated plan results need an optional illness scenario.",
            Review(
                title="Review details",
                summary_rows=rows,
                approve_cta=self.cta(
                    scope,
                    session,
                    "Add an optional scenario"
                    if draft.path
                    else "Clarify current cover",
                    "scenario" if draft.path else "entry",
                    draft if draft.path else "needs",
                    primary=True,
                ),
                reject_cta=self.cta(scope, session, "Back", "entry", "needs"),
            ),
        )

    async def job_result(self, ctx, scope, session, draft):
        result = await self.services.delegate(ctx, "", policy_id=draft.policy)
        if result.status != "success":
            trace = CARD_TRACE.get()
            if trace is not None:
                trace["validation"], trace["fallback"] = (
                    "accepted",
                    "inspection_unavailable",
                )
            return self.job_review(
                scope,
                session,
                draft,
                "The sample policy could not be checked. Your details are saved; "
                "select Check policy to retry, or Edit details.",
            )
        report = PolicyInspection.model_validate_json(result.report_json)
        rules = interpret(report)
        rows = [row("Sample policy", report.document.title)]
        if (
            rules.employment_linked.value is True
            and rules.period.value
            and rules.termination.value
        ):
            fixed = rules.termination.value.final_employment_date
            refs = "; ".join(
                f"p{e.locator.page}/{e.clause_id} [{e.evidence_id}]"
                for t in report.terms
                for e in t.evidence
                if e.evidence_id in rules.termination.evidence_ids
            )
            if draft.final_employment != fixed:
                return self.form(
                    scope,
                    session,
                    "job",
                    error=f"Your last working day conflicts with this sample "
                    f"policy's fixed {fixed} ({refs}); correct the date or "
                    "choose another sample policy.",
                )
            last = min(fixed, rules.period.value.end)
            rows += [
                row(
                    "Employer protection in this sample",
                    f"For listed members, ends {last}, inclusive; "
                    "it does not continue afterward.",
                ),
                row("Evidence", refs),
            ]
            if draft.new_start:
                days = max(0, (draft.new_start - last).days - 1)
                rows.append(
                    row(
                        "Gap in employer protection",
                        f"{days} days"
                        + (
                            f", {last + DAY} to {draft.new_start - DAY}, inclusive."
                            if days
                            else "; dates are contiguous."
                        ),
                    )
                )
            else:
                rows.append(
                    row(
                        "Gap in employer protection",
                        "Duration unknown until the new employer cover start "
                        "is confirmed.",
                    )
                )
        elif rules.employment_linked.value is False:
            rows.append(
                row(
                    "Employment link",
                    "This sample is not tied to employment; its dates, "
                    "waiting periods and exclusions still apply.",
                )
            )
        else:
            rows.append(
                row(
                    "Remaining uncertainty",
                    "Employment or date terms are missing/conflicting; "
                    "continuation cannot be determined.",
                )
            )
        if draft.current_cover in ("personal", "both"):
            rows.append(
                row(
                    "Personal cover",
                    "Keep existing cover; obtain its actual missing terms "
                    "before considering another plan.",
                )
            )
        if draft.current_cover == "unsure":
            rows.append(
                row(
                    "Current cover",
                    "Not confirmed; no absence of personal protection is assumed.",
                )
            )
        facts = [rules.period, rules.members, rules.employment_linked]
        if rules.employment_linked.value is True:
            facts.append(rules.termination)
        unknowns = [
            fact.unknown for fact in facts if fact.value is None and fact.unknown
        ]
        if unknowns:
            rows.append(row("Missing or conflicting terms", "; ".join(unknowns)))
        rows.append(
            row(
                "Limits",
                "No illness event was assumed. This is not a gap-in-all-protection "
                "finding or a guarantee of cover; actual membership and policy "
                "terms must be checked.",
            )
        )
        session.stage = "job_result"
        return message(
            "Here is what the sample policy says.",
            Detail(
                title="Your job-change check",
                summary_rows=rows,
                ctas=[
                    self.cta(
                        scope, session, "View policy evidence", "policy_details", report
                    ),
                    self.cta(scope, session, "Compare health plans", "entry", draft),
                    self.cta(scope, session, "Back", "edit"),
                ],
            ),
        )

    async def input_review(self, ctx, scope, session, draft):
        reports = []
        for identifier in dict.fromkeys([draft.policy, "existing-employer"]):
            result = await self.services.delegate(ctx, "", policy_id=identifier)
            if result.status != "success":
                return self.restart_prompt(
                    scope,
                    session,
                    "Policy inspection incomplete. Use /inspect or restart this draft.",
                    "inspection_unavailable",
                    validation="accepted",
                )
            reports.append(PolicyInspection.model_validate_json(result.report_json))
        employer = next(
            p for p in reports if p.document.document_id == "existing-employer"
        )
        termination = interpret(employer).termination
        if (
            termination.value
            and termination.value.final_employment_date != draft.inputs.final_employment
        ):
            fact = termination.value.final_employment_date
            refs = "; ".join(
                f"p{e.locator.page}/{e.clause_id} [{e.evidence_id}]"
                for t in employer.terms
                for e in t.evidence
                if e.evidence_id in termination.evidence_ids
            )
            i = draft.inputs
            needs = NeedsDraft(
                i.path,
                i.members,
                i.annual_budget_paise,
                i.minimum_family_limit_paise,
                i.room_requirement,
            )
            return self.form(
                scope,
                session,
                "scenario",
                needs,
                f"Your last working day conflicts with this sample policy's "
                f"fixed {fact} ({refs}); correct the date or choose another "
                "sample policy.",
            )
        i = draft.inputs
        session.stage = "input_review"
        rows = [
            row(
                "Demo",
                "Example profile — sample details, not your insurance"
                if draft.demo
                else "Your reviewed scenario",
            ),
            row(
                "Current cover",
                "Employer only"
                if i.path == "employer-only"
                else "Existing personal cover retained",
            ),
            row("Sample policy", REGISTRY[draft.policy].title),
        ]
        rows.extend(
            row(
                "You" if m.relationship == "self" else "Your spouse",
                f"Born {m.date_of_birth}; pre-existing {m.preexisting}",
            )
            for m in i.members
        )
        rows += [
            row("Annual budget", inr(i.annual_budget_paise)),
            row(
                "Coverage amount / room preference",
                inr(i.minimum_family_limit_paise)
                + "; "
                + (
                    "Private room without a daily cap"
                    if i.room_requirement == "uncapped-private"
                    else "Any room"
                ),
            ),
            row("Last working day", i.final_employment),
            row(
                "Assumed new cover start",
                str(i.assumed_new_employer_start) + " — unverified assumption",
            ),
            row("New policy start", i.proposed_start),
            row("Illness illustration", f"{i.event_member_id}, {i.immediate_event}"),
            row("Later illness scenario", i.later_event),
            row(
                "Limits",
                "Unknown disclosures stay unknown. No limits stack automatically. "
                "No purchase from this review.",
            ),
        ]
        return message(
            "Review the sample profile and dates."
            if draft.demo
            else "Review your optional scenario before comparing plans.",
            Review(
                title="Review details",
                summary_rows=rows,
                approve_cta=self.cta(
                    scope,
                    session,
                    "Confirm inputs · compare",
                    "confirm",
                    draft,
                    primary=True,
                ),
                reject_cta=self.cta(scope, session, "Back", "edit"),
            ),
        )

    def results(self, scope, session, report):
        session.stage = "results"
        items = []
        for candidate, product in zip(
            report.candidates, report.catalogue.catalogue.products
        ):
            reason = "; ".join(
                candidate.requirements.reasons
                + candidate.eligibility.reasons
                + candidate.budget.reasons
                + candidate.material_unknowns
            )
            items.append(
                Item(
                    id=product.product_id,
                    title=product.name,
                    subtitle=reason + f" Immediate {candidate.immediate.status}; "
                    f"separate later {candidate.later.status}. "
                    f"New-policy illness wait: {product.initial_wait_days} days; "
                    f"first post-wait {candidate.first_eligible_day}. "
                    "No immediate continuity credit.",
                    badges=[
                        Badge(
                            label={
                                "rejected": "Rejected",
                                "clarify": "Clarification needed",
                                "qualifies": "Prospective shortlist",
                            }[candidate.disposition],
                            variant="success"
                            if candidate.disposition == "qualifies"
                            else "warning",
                        )
                    ],
                    secondary_text=(
                        f"{inr(product.annual_premium_paise)}/year indicative · "
                        f"family limit {inr(product.family_limit_paise)}"
                    ),
                    primary_cta=self.cta(
                        scope,
                        session,
                        "View findings & evidence",
                        "candidate",
                        (report, product.product_id, 1),
                    ),
                )
            )
        keep = (
            " Existing personal cover retained; obtain missing terms, "
            "no duplicate-cover purchase shortcut."
            if report.inputs.path == "existing-personal"
            else ""
        )
        return message(
            "Here are the plan results for your reviewed scenario.",
            Carousel(
                title="Your plan comparison",
                subtitle="Indicative annual prices, not quotes. "
                + report.employer_gap
                + keep
                + " Passing temporal checks never guarantees coverage or claims.",
                items=items,
            ),
        )

    def candidate(self, scope, session, report, identifier):
        session.stage = "candidate"
        c = next(c for c in report.candidates if c.product_id == identifier)
        p = next(
            p for p in report.catalogue.catalogue.products if p.product_id == identifier
        )
        rows = [
            row("Result", c.disposition),
            row("Indicative annual price", inr(p.annual_premium_paise)),
            row("Family limit", inr(p.family_limit_paise)),
        ]
        for name in ("eligibility", "budget", "requirements"):
            d = getattr(c, name)
            rows.append(row(name, d.status + ": " + "; ".join(d.reasons)))
        rows += [
            row(
                "Immediate illness",
                str(report.inputs.immediate_event) + ": " + c.immediate.status,
            ),
            row(
                "Separate later illness",
                str(report.inputs.later_event) + ": " + c.later.status,
            ),
            row(
                "Initial waiting limitation",
                f"{p.initial_wait_days} days from proposed start "
                f"{report.inputs.proposed_start}; first post-wait "
                f"{c.first_eligible_day}. No continuity waiver.",
            ),
            row(
                "Remaining limits",
                "; ".join(
                    c.material_unknowns
                    + c.immediate.missing_information
                    + c.immediate.restrictions
                )
                or "Terms and exclusions apply; no acceptance or payout guarantee.",
            ),
            row(
                "Evidence",
                reference(
                    report,
                    identifier,
                    ["Eligibility", "Room rent", "Waiting period", "Sum insured"],
                ),
            ),
        ]
        ctas = []
        if (
            report.inputs.path == "employer-only"
            and c.product_id in report.shortlist
            and c.disposition == "qualifies"
            and not c.material_unknowns
            and all(
                d.status == "pass" for d in (c.eligibility, c.budget, c.requirements)
            )
        ):
            ctas.append(
                self.cta(
                    scope,
                    session,
                    "Request computed quote",
                    "operation",
                    SandboxCommand(
                        action="quote", product_id=identifier, inputs=report.inputs
                    ),
                    primary=True,
                )
            )
        ctas += [
            self.cta(
                scope,
                session,
                "Full findings & evidence",
                "evidence",
                (report, identifier, 1),
            ),
            self.cta(scope, session, "Comparison & baseline", "comparison", report),
        ]
        return message(
            "Check waiting periods and unresolved terms before requesting a quote.",
            Detail(title=p.name + " · actual findings", summary_rows=rows, ctas=ctas),
        )

    def sandbox_card(self, scope, session, reply):
        session.stage = (
            "application_review" if reply.state == "review" else "sandbox_status"
        )
        app = reply.application
        q = reply.quote or (app.quote if app else None)
        if reply.state == "review" and reply.challenge:
            session.review = reply
        elif reply.state != "review" and session.review:
            if session.review.application.application_id == reply.reference:
                session.review = None
        status = self.cta(
            scope,
            session,
            "Check status",
            "operation",
            SandboxCommand(action="status", reference=reply.reference),
        )
        details = self.cta(
            scope,
            session,
            "Complete terms & evidence",
            "operation",
            SandboxCommand(action="details", reference=reply.reference),
        )
        titles = {
            "quote_active": "Your quote",
            "quote_expired": "Quote expired",
            "review": "Review application",
            "completed": "Sandbox purchase completed",
            "payment_pending": "Payment outcome unknown",
            "operation_pending": "Checking your request",
            "failed": "Sandbox payment failed",
            "cancelled": "Application cancelled",
            "needs_review": "Review needed",
            "approved": "Approval recorded",
            "rejected": "Request rejected",
        }
        rows = []
        if q:
            rows += [
                row("Plan / provider", q.product.name + " / " + q.product.insurer),
                row("Computed annual premium", inr(q.premium_paise) + " INR"),
            ]
        if q and reply.state in ("quote_active", "quote_expired", "review"):
            rows += [
                row(
                    "Members",
                    "; ".join(m.relationship.capitalize() for m in q.inputs.members),
                ),
                row("Cover dates, inclusive", f"{q.cover_start} to {q.cover_end}"),
                row(
                    "Initial illness wait, inclusive",
                    f"{q.wait_start} to {q.wait_end}; first post-wait "
                    f"{q.first_post_wait_day}. No waiver/continuity credit.",
                ),
                row(
                    "Immediate illustrative illness",
                    f"{q.inputs.immediate_event}: {q.immediate_status}. "
                    "Purchase does not remove exclusions.",
                ),
            ]
        ctas = [status, details]
        if reply.state == "quote_active" and any(
            command.startswith("/apply ") for command in reply.next_commands
        ):
            rows.append(row("Quote expiry", utc(q.expires_at)))
            ttl = max(0, (q.expires_at - self.clock()).total_seconds())
            ctas = [
                self.cta(
                    scope,
                    session,
                    "Prepare sandbox application",
                    "operation",
                    SandboxCommand(
                        action="apply",
                        reference=q.quote_id,
                        application=ApplicationFields(
                            confirm_demo=True, payment_outcome="success"
                        ),
                    ),
                    primary=True,
                    ttl=min(TTL, ttl),
                ),
                details,
                self.cta(scope, session, "Cancel card journey", "cancel"),
            ]
        elif reply.state == "quote_active":
            rows.append(
                row(
                    "Application",
                    "Already prepared; retrieve its authoritative status.",
                )
            )
            for command in reply.next_commands:
                if command.startswith("/sandbox-status a-"):
                    ctas.insert(
                        0,
                        self.cta(
                            scope,
                            session,
                            "View application status",
                            "operation",
                            SandboxCommand(
                                action="status", reference=command.split(" ")[1]
                            ),
                            primary=True,
                        ),
                    )
        elif reply.state == "review":
            bound = session.review
            if (
                bound
                and bound.application.application_id == app.application_id
                and bound.application.review_digest == app.review_digest
                and bound.challenge
                and self.clock() < min(app.challenge_expires_at, q.expires_at)
            ):
                rows += [
                    row(
                        "Review revision / expiry",
                        f"{app.revision}; {utc(app.challenge_expires_at)}",
                    ),
                    row("Quote expiry", utc(q.expires_at)),
                    row("Sandbox payment test mode", app.fields.payment_outcome),
                    row(
                        "Health disclosures",
                        "; ".join(
                            f"{m.relationship.capitalize()}: born {m.date_of_birth}, "
                            f"pre-existing {m.preexisting}"
                            for m in q.inputs.members
                        ),
                    ),
                    row(
                        "Material restrictions",
                        "\n".join(display_money(r) for r in q.restrictions),
                    ),
                    row("Required disclosures", "\n".join(q.required_disclosures)),
                    row(
                        "Authorization",
                        "Observed sender/session is demo isolation, not verified "
                        "personal identity. Exact terms, premium, members, dates "
                        "and revision are bound. No real money moves.",
                    ),
                ]
                ttl = min(
                    TTL,
                    (
                        min(app.challenge_expires_at, q.expires_at) - self.clock()
                    ).total_seconds(),
                )
                return message(
                    NOTICE
                    + "\n"
                    + "```text\n/sandbox-details "
                    + app.application_id
                    + "\n```",
                    Review(
                        title="Review sandbox purchase",
                        summary_rows=rows,
                        approve_cta=self.cta(
                            scope,
                            session,
                            "Approve sandbox purchase — " + inr(q.premium_paise),
                            "approve",
                            SandboxCommand(
                                action="approve",
                                reference=app.application_id,
                                revision=app.revision,
                                challenge=bound.challenge,
                            ),
                            primary=True,
                            ttl=ttl,
                        ),
                        reject_cta=self.cta(
                            scope,
                            session,
                            "Cancel",
                            "operation",
                            SandboxCommand(
                                action="cancel", reference=app.application_id
                            ),
                        ),
                    ),
                )
            ctas.insert(
                0,
                self.cta(
                    scope,
                    session,
                    "Refresh review · new approval required",
                    "operation",
                    SandboxCommand(action="review", reference=app.application_id),
                ),
            )
        if reply.payment:
            rows += [row("Payment outcome", reply.payment.state)]
            if reply.payment.confirmation:
                rows.append(
                    row("Stable sandbox confirmation", reply.payment.confirmation)
                )
        if reply.state in ("payment_pending", "operation_pending", "approved"):
            rows.append(
                row(
                    "Safe next step",
                    "Outcome unknown. Check status to reconcile; do not pay again.",
                )
            )
        if reply.error_code:
            reasons = {
                "invalid_review_or_challenge": "This review has changed; "
                "request a fresh review before approving.",
                "quote_expired": "This quote has expired; a new quote "
                "and review are required.",
                "review_or_quote_expired": "The review or quote has expired; "
                "refresh it before approving.",
                "eligibility_budget_or_terms_unresolved": "Eligibility, budget "
                "or important terms need clarification before a quote.",
                "new_review_required": "This review can no longer be approved; "
                "check status before continuing.",
            }
            rows.append(
                row(
                    "What happened",
                    reasons.get(
                        reply.error_code,
                        "The provider could not complete this request; "
                        "check status and complete terms.",
                    ),
                )
            )
        if reply.state in ("needs_review", "quote_expired") or reply.error_code in (
            "quote_expired",
            "review_or_quote_expired",
            "approval_expired",
            "invalid_review_or_challenge",
        ):
            rows.append(
                row(
                    "Next step",
                    "Obtain a fresh quote/review and new explicit approval. "
                    "Use /sandbox.",
                )
            )
        rows.append(
            row("Limits", "Future claim acceptance or payout is not guaranteed.")
        )
        fallback = NOTICE
        if reply.state not in ("quote_active", "review"):
            fallback += (
                "\nStatus / restart recovery:\n```text\n/sandbox-status "
                + reply.reference
                + "\n```"
            )
        return message(
            fallback,
            Detail(
                title=titles[reply.state],
                summary_rows=rows,
                ctas=ctas,
            ),
        )

    async def operation(self, ctx, scope, session, action):
        command = (
            SandboxCommand(action="status", reference=action.recovery_ref)
            if action.recovery_ref
            else action.data
        )
        result = await self.services.sandbox_operation(ctx, scope[0], command)
        if result.status != "success":
            session.stage = "operation_pending"
            trace = CARD_TRACE.get()
            if trace is not None:
                trace["fallback"] = "provider_incomplete"
            action.recovery_ref = "op-" + result.request_id.hex
            status = self.cta(
                scope,
                session,
                "Check status",
                "operation",
                SandboxCommand(action="status", reference=action.recovery_ref),
            )
            return message(
                NOTICE + " Operation outcome unknown. Do not repeat payment.\n"
                "```text\n/sandbox-status " + action.recovery_ref + "\n```",
                Detail(
                    title="Reconciliation required",
                    summary_rows=[
                        row("Outcome", result.error or "unknown"),
                        row(
                            "Next step",
                            "Check authoritative status; no success assumed "
                            "and no second payment offered.",
                        ),
                    ],
                    ctas=[status],
                ),
            )
        reply = SandboxReply.model_validate_json(result.payload_json)
        if command.action == "details":
            return text_reply(present_sandbox(reply))
        if command.action not in ("status", "details"):
            action.recovery_ref = (
                reply.operation_id if reply.state == "rejected" else reply.reference
            )
        try:
            return self.sandbox_card(scope, session, reply)
        except ValueError:
            return text_reply(present_sandbox(reply))

    async def dispatch(self, ctx, scope, session, action, fields):
        if action.kind == "entry":
            if fields:
                return self.restart_prompt(
                    scope,
                    session,
                    "Use the choices on the current card; no action executed.",
                    "unexpected_fields",
                )
            session.epoch += 1
            stage = "needs" if isinstance(action.data, JobDraft) else action.data
            return self.form(
                scope,
                session,
                stage,
                action.data if isinstance(action.data, JobDraft) else None,
            )
        if action.kind == "example":
            try:
                raw = ExampleForm.model_validate(fields)
            except ValidationError as exc:
                return self.form(scope, session, "example", error=self.error(exc))
            session.epoch += 1
            draft = InputsDraft(
                parse_input(
                    "preset-existing"
                    if raw.sample_cover == "existing-personal"
                    else "preset"
                ),
                "existing-employer",
                True,
            )
            return await self.input_review(ctx, scope, session, draft)
        if action.kind == "job":
            try:
                draft = job_input(JobForm.model_validate(fields))
            except ValueError as exc:
                return self.form(scope, session, "job", error=self.error(exc))
            session.epoch += 1
            return self.job_review(scope, session, draft)
        if action.kind == "needs":
            try:
                draft = needs_input(NeedsForm.model_validate(fields), action.data)
            except ValueError as exc:
                return self.form(scope, session, "needs", action.data, self.error(exc))
            session.epoch += 1
            return self.needs_review(scope, session, draft)
        if action.kind == "scenario_submit":
            try:
                draft = comparison_input(
                    action.data, ScenarioForm.model_validate(fields)
                )
            except ValueError as exc:
                return self.form(
                    scope, session, "scenario", action.data, self.error(exc)
                )
            session.epoch += 1
            return await self.input_review(ctx, scope, session, draft)
        if fields:
            return self.restart_prompt(
                scope,
                session,
                "Unexpected callback fields. Use the original card; "
                "no action executed.",
                "unexpected_fields",
            )
        if action.kind == "job_confirm":
            return await self.job_result(ctx, scope, session, action.data)
        if action.kind == "scenario":
            return self.form(scope, session, "scenario", action.data)
        if action.kind == "policy_details":
            from coverwise.policies import present

            return text_reply(present(action.data))
        if action.kind == "confirm":
            session.epoch += 1
            result = await self.services.recommend(ctx, action.data.inputs)
            if result.status != "success":
                return self.restart_prompt(
                    scope,
                    session,
                    "Comparison incomplete; no result fabricated. "
                    "Restart this draft or use /recommend.",
                    "recommendation_unavailable",
                    validation="accepted",
                )
            report = Recommendation.model_validate_json(result.payload_json)
            try:
                return self.results(scope, session, report)
            except ValueError:
                return text_reply(present_recommendation(report))
        if action.kind in ("edit", "restart"):
            session.epoch += 1
            session.review = None
            return self.form(scope, session)
        if action.kind == "cancel":
            session.epoch += 1
            session.review = None
            session.stage = "cancelled"
            return text_reply(
                "Card draft cancelled. Persisted quotes/applications are unchanged. "
                "Use /cards or /sandbox-status."
            )
        if action.kind == "candidate":
            return self.candidate(scope, session, *action.data[:2])
        if action.kind == "evidence":
            session.stage = "evidence"
            report, identifier, page = action.data
            inspection = next(
                p for p in report.inspections if p.document.document_id == identifier
            )
            ctas = [
                self.cta(
                    scope,
                    session,
                    "Back to candidate",
                    "candidate",
                    (report, identifier, 1),
                )
            ]
            if page < inspection.document.page_count:
                ctas.append(
                    self.cta(
                        scope,
                        session,
                        "Next evidence page",
                        "evidence",
                        (report, identifier, page + 1),
                    )
                )
            if page > 1:
                ctas.append(
                    self.cta(
                        scope,
                        session,
                        "Previous evidence page",
                        "evidence",
                        (report, identifier, page - 1),
                    )
                )
            return message(
                "Full findings and source evidence; no coverage promise.",
                Detail(
                    title=f"Evidence · page {page}/{inspection.document.page_count}",
                    summary_rows=[
                        row(
                            "Source findings",
                            present_evidence(report, identifier, page),
                        )
                    ],
                    ctas=ctas,
                ),
            )
        if action.kind == "comparison":
            return text_reply(present_recommendation(action.data))
        if action.kind in ("operation", "approve"):
            return await self.operation(ctx, scope, session, action)
        return self.restart_prompt(
            scope,
            session,
            "Unsupported card action; no action executed.",
            "unsupported_action",
        )

    @staticmethod
    def error(exc):
        if not isinstance(exc, ValidationError):
            return str(exc)
        error = exc.errors(include_input=False, include_context=False)[0]
        name = error["loc"][0] if error["loc"] else ""
        messages = {
            "final_employment": "Enter your last working day as YYYY-MM-DD.",
            "new_start": "Enter the new cover start date as YYYY-MM-DD.",
            "proposed_start": "Enter the policy start date as YYYY-MM-DD.",
            "self_dob": "Enter your date of birth as YYYY-MM-DD.",
            "spouse_dob": "Enter your spouse's date of birth as YYYY-MM-DD.",
            "budget_rupees": "Enter your annual budget in rupees.",
            "minimum_rupees": "Enter the coverage amount in rupees.",
            "immediate_event": "Enter the illness date as YYYY-MM-DD.",
            "later_event": "Enter the later illness date as YYYY-MM-DD.",
            "event_member": "Choose who the illness scenario is for.",
            "current_cover": "Choose your current cover, or choose Unsure.",
            "policy": "Choose a sample policy from the list.",
            "sample_cover": "Choose the sample cover you want to explore.",
            "room": "Choose your room preference.",
            "who": "Choose who needs cover.",
            "new_cover_known": "Choose whether you know the new cover start date.",
            "self_disclosure": "Choose your health disclosure, or leave it unknown.",
            "spouse_disclosure": "Choose your spouse's health disclosure, "
            "or leave it unknown.",
        }
        if name in messages:
            return messages[name]
        reason = error["msg"]
        if "new employer coverage start" in reason:
            return "New cover must start after your last working day."
        if "later event" in reason:
            return "The later illness date must be after the first illness date."
        if "birth dates" in reason:
            return "Birth dates must be on or before the policy start and illness date."
        if "member" in reason:
            return "Choose a covered person for the illness scenario."
        return "Use the fields on the current form, then continue."

    def prose_fallback(self, scope):
        session = self.sessions.get(scope)
        if session and session.review:
            reply = session.review
            app = reply.application
            if self.clock() < min(app.challenge_expires_at, app.quote.expires_at):
                return text_reply(
                    "Card prose cannot authorize payment. Direct-mention the agent "
                    "and click the original card, or deliberately send this exact "
                    "command:\n```text\n"
                    f"/approve {app.application_id} {app.revision} "
                    f"{reply.challenge}\n```\n"
                    "No action executed from this message."
                )
        return text_reply(
            "Card selection could not be verified as structured JSON. No payment "
            "authorized. Use a direct @mention and /cards, or /sandbox for "
            "exact-command guidance."
        )

    async def handle(self, ctx, sender, text, *, source=None):
        source = source or (
            "entry_command"
            if text in ("/cards", "/start")
            else "callback"
            if text.lstrip().startswith("{")
            else "prose"
        )
        scope = (sender, ctx.session)
        current = self.sessions.get(scope)
        trace = {
            "action": "entry_command" if source == "entry_command" else "unresolved",
            "prior": current.stage if current else "none",
            "validation": "rejected",
            "fallback": "none",
        }
        trace_token = CARD_TRACE.set(trace)
        try:
            return await self._handle(ctx, sender, text, source, trace)
        except asyncio.CancelledError:
            trace["fallback"] = "cancelled"
            raise
        except Exception:
            trace["validation"], trace["fallback"] = "error", "internal_error"
            current = self.sessions.get(scope)
            if current:
                return self.restart_prompt(
                    scope,
                    current,
                    "This card could not be processed. Check saved status for "
                    "any transaction; do not repeat payment.",
                    "internal_error",
                    validation="error",
                )
            return text_reply(
                "This card could not be processed. Restart with /cards; "
                "no success is assumed."
            )
        finally:
            current = self.sessions.get(scope)
            LOGGER.info(
                "role=coordinator event=card_transition source=%s action=%s "
                "prior_stage=%s next_stage=%s validation=%s "
                "fallback_reason=%s session=%s",
                source,
                trace["action"],
                trace["prior"],
                current.stage if current else "none",
                trace["validation"],
                trace["fallback"],
                ctx.session,
            )
            CARD_TRACE.reset(trace_token)

    async def _handle(self, ctx, sender, text, source, trace):
        self.prune()
        scope = (sender, ctx.session)
        session = self.sessions.get(scope)
        if session is None:
            if len(self.sessions) >= MAX_SESSIONS:
                trace["fallback"] = "capacity"
                return text_reply(
                    "Card draft capacity reached. Restart with /cards later "
                    "or use exact commands."
                )
            session = self.sessions[scope] = Session(
                self.timer() + TTL,
                stage="entry" if source == "entry_command" else "recovery",
            )
            if source != "entry_command":
                return self.restart_prompt(
                    scope,
                    session,
                    "Card expired or belongs to another sender/session; "
                    "no action executed.",
                    "missing_session",
                )
        if session.waiting >= 4:
            return self.restart_prompt(
                scope,
                session,
                "A card action is already queued. Wait for its result; "
                "do not repeat payment.",
                "busy",
            )
        session.waiting += 1
        acquired = False
        try:
            await asyncio.wait_for(
                session.lock.acquire(), timeout=self.services.timeout * 2 + 1
            )
            acquired = True
            trace["prior"] = session.stage
            trace["validation"], trace["fallback"] = "accepted", "none"
            if self.sessions.get(scope) is not session:
                trace["fallback"] = "cleared"
                return text_reply(
                    "Card draft was cleared. Restart with /cards; no action executed."
                )
            session.expires = self.timer() + TTL
            if source == "entry_command":
                if text not in ("/cards", "/start"):
                    return self.restart_prompt(
                        scope,
                        session,
                        "Use /cards to open the card journey; no action executed.",
                        "invalid_entry",
                    )
                if session.stage not in ("entry", "recovery", "cancelled"):
                    return self.restart_prompt(
                        scope,
                        session,
                        "A card step is already open. No form submission was received "
                        "by this entry command; use the current card or choose "
                        "Restart cards.",
                        "entry_during_active_flow",
                        validation="guarded",
                    )
                session.epoch += 1
                session.review = None
                return self.form(scope, session)
            if source != "callback":
                return self.restart_prompt(
                    scope,
                    session,
                    self.prose_fallback(scope).text(),
                    "unstructured_response",
                )
            invalid_reason = "malformed_callback"
            try:
                data = json.loads(text, object_pairs_hook=unique_object)
                if not isinstance(data, dict):
                    raise ValueError("callback must be an object")
                invalid_reason = "missing_selection"
                if not {"action", "card_token"} <= data.keys():
                    raise ValueError("missing selection")
                invalid_reason = "invalid_selection"
                callback = Callback.model_validate(
                    {k: data.pop(k) for k in ("action", "card_token") if k in data}
                )
                invalid_reason = "invalid_confirmation_metadata"
                metadata = CallbackMetadata.model_validate(
                    {"approved": data.pop("approved")} if "approved" in data else {}
                )
                if metadata.model_fields_set and metadata.approved is None:
                    raise ValueError("invalid confirmation metadata")
            except ValueError:
                return self.restart_prompt(
                    scope,
                    session,
                    "That card response could not be verified; no action executed.",
                    invalid_reason,
                )
            action = self.actions.get(callback.card_token)
            if action is None or action.scope != scope:
                return self.restart_prompt(
                    scope,
                    session,
                    "Card action expired, unknown or unauthorized for this "
                    "conversation; no action executed.",
                    "unknown_or_wrong_scope",
                )
            trace["action"] = action.kind
            if action.used:
                return self.restart_prompt(
                    scope,
                    session,
                    "This card response was already used; use the latest card "
                    "or restart this draft.",
                    "already_used",
                )
            if action.epoch != session.epoch or action.expires <= self.timer():
                return self.restart_prompt(
                    scope,
                    session,
                    "This card action is expired or stale; no action executed.",
                    "expired_or_stale",
                )
            if action.kind in ONE_SHOT and action.source_stage != session.stage:
                return self.restart_prompt(
                    scope,
                    session,
                    "This response belongs to a different card step; "
                    "no action executed.",
                    "wrong_stage",
                )
            negative_action = action.kind in ("entry", "edit", "cancel", "restart") or (
                action.kind == "operation"
                and isinstance(action.data, SandboxCommand)
                and action.data.action == "cancel"
            )
            if metadata.approved is False and not negative_action:
                return self.restart_prompt(
                    scope,
                    session,
                    "Not confirmed. Use Continue, Back or Cancel on the current "
                    "card; no action executed.",
                    "not_confirmed",
                )
            if action.kind in ONE_SHOT:
                action.used = True
            response = await self.dispatch(ctx, scope, session, action, data)
            if self.sessions.get(scope) is not session:
                self.prune()
                trace["fallback"] = "cleared_during_work"
                recovery = (
                    "\n```text\n/sandbox-status " + action.recovery_ref + "\n```"
                    if action.recovery_ref
                    else ""
                )
                return text_reply(
                    "Card draft was cleared while work ran. Persisted Provider "
                    "effects are not undone; retrieve scoped status." + recovery
                )
            return response
        except (TimeoutError, ValueError, PolicyError):
            return self.restart_prompt(
                scope,
                session,
                "Card operation incomplete. Check saved transaction status; "
                "do not repeat payment blindly.",
                "operation_incomplete",
                validation="error",
            )
        finally:
            session.waiting -= 1
            if acquired:
                session.lock.release()
