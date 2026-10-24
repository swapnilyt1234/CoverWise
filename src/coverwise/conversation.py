"""Bounded conversational drafts and an allowlisted, typed SDK service dispatcher."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from time import monotonic
from typing import Literal

from pydantic import Field

from coverwise.contracts import Contract, JobChangeScenario, PolicyInspection
from coverwise.money import inr
from coverwise.policies import CANDIDATES, REGISTRY
from coverwise.policies import present as present_policy
from coverwise.recommend import Member, Recommendation, RecommendationInput
from coverwise.recommend import parse_input as preset_input
from coverwise.recommend import present as present_recommendation
from coverwise.sandbox_contracts import SandboxCommand, SandboxReply
from coverwise.sandbox_ui import present as present_sandbox
from coverwise.stress import Comparison, Rules, interpret, present_comparison

PRIVACY = (
    "Conversational messages may be processed by ASI."
    " Use synthetic information only. Slash commands "
    "avoid this intent parser. /clear-chat clears "
    "drafts, not persisted quotes or purchases. "
    "Sender/session isolation is not verified "
    "identity."
)
FALLBACK = (
    "Conversation parsing is unavailable or "
    "ambiguous. Use /start or an exact command; no "
    "proposed action was executed."
)
INDIA = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")


class Fragments(Contract):
    # These are verbatim user spans, never model-computed dates or amounts.
    policy: str | None = Field(default=None, max_length=80)
    product: str | None = Field(default=None, max_length=80)
    final_date: str | None = Field(default=None, max_length=64)
    new_start: str | None = Field(default=None, max_length=64)
    proposed_start: str | None = Field(default=None, max_length=64)
    event_date: str | None = Field(default=None, max_length=64)
    later_date: str | None = Field(default=None, max_length=64)
    personal_cover: str | None = Field(default=None, max_length=80)
    budget: str | None = Field(default=None, max_length=64)
    minimum_cover: str | None = Field(default=None, max_length=64)
    room: str | None = Field(default=None, max_length=64)
    members: str | None = Field(default=None, max_length=500)
    disclosures: str | None = Field(default=None, max_length=200)
    event_type: str | None = Field(default=None, max_length=64)
    member_id: str | None = Field(default=None, max_length=64)


class Intent(Contract):
    action: Literal[
        "job_change",
        "inspect",
        "update",
        "stress",
        "compare",
        "quote",
        "status",
        "demo",
        "clarify",
    ]
    fields: Fragments = Field(default_factory=Fragments)


def resolve_date(text, clock):
    value = text.casefold().strip()
    now = clock()
    if now.utcoffset() is None:
        raise ValueError("An aware clock is required; use explicit commands.")
    today = now.astimezone(INDIA).date()
    if value in ("today", "tomorrow"):
        result = today + timedelta(days=value == "tomorrow")
    elif match := re.fullmatch(r"in (\d{1,3}) days?", value):
        if int(match[1]) > 366:
            raise ValueError(
                "Use a date within 366 days or an explicit YYYY-MM-DD date."
            )
        result = today + timedelta(days=int(match[1]))
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        result = date.fromisoformat(value)
    else:
        raise ValueError(
            (
                "Use YYYY-MM-DD, today, tomorrow, or in N days; "
                "other relative dates are ambiguous."
            )
        )
    if not date(1900, 1, 1) <= result <= date(2100, 12, 31):
        raise ValueError("Use a date between 1900 and 2100.")
    return result


def paise(text):
    value = text.casefold().strip()
    if value.startswith("₹"):
        value = value[1:].strip() + " rupees"
    match = re.fullmatch(
        r"(\d+|\d{1,3}(?:,\d{2})*,\d{3})(?:\.(\d{1,2}))?\s*(rupees|inr|paise)", value
    )
    if not match:
        raise ValueError(
            "Give an explicit amount and rupees/paise, for example 30000 rupees."
        )
    whole, fraction, unit = match.groups()
    if unit == "paise" and fraction:
        raise ValueError("Paise must be an integer.")
    result = int(whole.replace(",", ""))
    if unit != "paise":
        result = result * 100 + int((fraction or "").ljust(2, "0"))
    if result > 10**12:
        raise ValueError("Amount exceeds the supported demo input bound.")
    return result


def document_id(span, candidates=False):
    choices = CANDIDATES if candidates else REGISTRY | CANDIDATES
    value = span.casefold().strip()
    matches = [
        key
        for key, spec in choices.items()
        if value in (key, spec.title.casefold(), spec.title.casefold().split()[-1])
    ]
    if len(matches) != 1:
        raise ValueError("Choose one exact preloaded policy ID from /policies.")
    return matches[0]


def member_list(text):
    result = []
    for item in text.split(","):
        parts = item.strip().split(":")
        if len(parts) not in (3, 4):
            raise ValueError(
                (
                    "Supply members as "
                    "member-ID:YYYY-MM-DD:self/spouse/child; omit "
                    "disclosure to retain unknown."
                )
            )
        identifier, born, relation = parts[:3]
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", identifier):
            raise ValueError("Use a supported member identifier.")
        result.append(
            Member(
                member_id=identifier,
                date_of_birth=date.fromisoformat(born),
                relationship=relation,
                preexisting=parts[3] if len(parts) == 4 else "unknown",
            )
        )
    if not 1 <= len(result) <= 4 or len({m.member_id for m in result}) != len(result):
        raise ValueError("Supply one to four distinct members.")
    return result


@dataclass
class Draft:
    expires: float
    busy: bool = False
    privacy_sent: bool = False
    goal: str = ""
    pending: str = ""
    values: dict = field(default_factory=dict)
    final_confirmed: bool = False
    facts: Rules | None = None
    citation: str = ""
    refs: list[str] = field(default_factory=list)


class Conversation:
    def __init__(
        self,
        services,
        adapter,
        *,
        clock=lambda: datetime.now(timezone.utc),
        timer=monotonic,
        ttl=900,
        capacity=128,
    ):
        self.services, self.adapter = services, adapter
        self.clock, self.timer = clock, timer
        self.ttl, self.capacity = ttl, capacity
        self.drafts = {}

    def clear(self, sender, session):
        self.drafts.pop((sender, session), None)
        return (
            "Conversational draft cleared. Persisted quotes, "
            "applications and purchases were not deleted. Use"
            " their exact scoped status commands."
        )

    def remember(self, sender, session, reply, expected):
        draft = self.drafts.get((sender, session))
        if (
            draft is expected
            and draft
            and draft.expires > self.timer()
            and reply.state != "rejected"
            and (reply.quote or reply.application)
        ):
            draft.refs = [*draft.refs[-7:], reply.reference]

    def current(self, key, draft):
        if self.drafts.get(key) is not draft or draft.expires <= self.timer():
            raise ValueError(
                (
                    "Draft expired or was cleared. Use /start; "
                    "persisted records remain available through exact"
                    " status commands."
                )
            )

    async def dispatch(
        self,
        ctx,
        sender,
        action: Literal["inspect", "stress", "compare", "quote", "status"],
        payload: str
        | RecommendationInput
        | JobChangeScenario
        | tuple[str, RecommendationInput],
    ):
        # No action accepts an executable string, approval, payment mode or scope.
        if action == "inspect":
            result = await self.services.delegate(ctx, "", policy_id=payload)
            if result.status != "success":
                raise ValueError(
                    (
                        "Investigator inspection unavailable. Use "
                        "/inspect and retry; no facts invented."
                    )
                )
            return PolicyInspection.model_validate_json(result.report_json)
        if action == "compare":
            result = await self.services.recommend(ctx, payload)
            if result.status != "success":
                raise ValueError(
                    (
                        "Recommendation incomplete. Use /recommend; "
                        "Provider/Investigator facts unavailable."
                    )
                )
            return Recommendation.model_validate_json(result.payload_json)
        if action == "stress":
            result = await self.services.delegate(ctx, "", scenario=payload)
            if result.status != "success":
                raise ValueError(
                    "Stress assessment incomplete. Use /stress-test; "
                    "no findings invented."
                )
            return Comparison.model_validate_json(result.report_json)
        if action in ("quote", "status"):
            command = (
                SandboxCommand(action="quote", product_id=payload[0], inputs=payload[1])
                if action == "quote"
                else SandboxCommand(action="details", reference=payload)
            )
            result = await self.services.sandbox_operation(ctx, sender, command)
            if result.status != "success":
                return None, (
                    (
                        "Provider operation incomplete. Do not create "
                        "another purchase; reconcile:\n"
                        "```text\n"
                        "/sandbox-status op-"
                    )
                    + result.request_id.hex
                    + "\n```"
                )
            return SandboxReply.model_validate_json(result.payload_json), None
        raise ValueError("Unsupported conversational tool action. Use /start.")

    def apply(self, draft, proposal, text):
        values = dict(draft.values)
        for name, span in proposal.fields.model_dump(exclude_none=True).items():
            if not span or span.casefold() not in text.casefold():
                raise ValueError(
                    (
                        "The proposed fields were not stated explicitly. "
                        "Please clarify one field; no action executed."
                    )
                )
            value = span.strip().casefold()
            if name in (
                "final_date",
                "new_start",
                "proposed_start",
                "event_date",
                "later_date",
            ):
                values[name] = resolve_date(span, self.clock)
            elif name in ("budget", "minimum_cover"):
                values[name] = paise(span)
                if name == "minimum_cover" and values[name] == 0:
                    raise ValueError("Minimum family cover must be positive.")
            elif name in ("policy", "product"):
                values[name] = document_id(span, name == "product")
            elif name == "members":
                values[name] = member_list(span)
            elif name == "personal_cover":
                mapping = {
                    "i have no personal cover": "none",
                    "no personal cover": "none",
                    "no personal insurance": "none",
                    "none": "none",
                    "i have personal cover": "existing",
                    "existing personal cover": "existing",
                    "i have existing personal cover": "existing",
                    "unknown": "unknown",
                    "not sure": "unknown",
                    "i don't know": "unknown",
                }
                if value not in mapping:
                    raise ValueError(
                        (
                            "State 'I have no personal cover', 'I have "
                            "personal cover', or 'unknown'."
                        )
                    )
                values[name] = mapping[value]
            elif name == "room":
                mapping = {
                    "uncapped-private": "uncapped-private",
                    "uncapped private room": "uncapped-private",
                    "any-room": "any-room",
                    "any room": "any-room",
                }
                if value not in mapping:
                    raise ValueError("Choose uncapped private room or any room.")
                values[name] = mapping[value]
            elif name == "event_type":
                if value not in ("illness hospitalization", "illness_hospitalization"):
                    raise ValueError(
                        (
                            "Only explicit illness hospitalization is "
                            "supported; no event has been assumed."
                        )
                    )
                values[name] = "illness_hospitalization"
            elif name == "member_id":
                if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", span):
                    raise ValueError("Supply the exact event member ID.")
                values[name] = span
            elif name == "disclosures":
                members = values.get("members", [])
                updates = {}
                for part in value.split(","):
                    match = re.fullmatch(
                        r"\s*([a-z0-9-]+)[: ]+(absent|present|unknown)\s*", part
                    )
                    if not match or match[1] not in {m.member_id for m in members}:
                        raise ValueError(
                            (
                                "State each member-ID:absent/present/unknown "
                                "using synthetic data only."
                            )
                        )
                    updates[match[1]] = match[2]
                values["members"] = [
                    m.model_copy(
                        update={"preexisting": updates.get(m.member_id, m.preexisting)}
                    )
                    for m in members
                ]
        if values.get("final_date") != draft.values.get("final_date"):
            draft.final_confirmed = False
        if values.get("policy") != draft.values.get("policy"):
            draft.facts = None
        draft.values = values

    def ask(self, draft, name, question):
        draft.pending = name
        return question

    async def read_status(self, ctx, sender, key, draft, ref):
        reply, error = await self.dispatch(ctx, sender, "status", ref)
        self.current(key, draft)
        if reply:
            self.remember(sender, ctx.session, reply, draft)
        draft.pending = "next"
        return error or (
            "Read-only status; use the exact status command below "
            "for reconciliation.\n" + present_sandbox(reply, summary=True)
        )

    async def job(self, ctx, sender, key, draft):
        v = draft.values
        if not v.get("policy"):
            return self.ask(
                draft,
                "policy",
                (
                    "I can check the documented employer continuation"
                    " rule. Which preloaded policy: existing-employer"
                    " or existing-personal? They are fictional "
                    "samples, not proof of your insurance."
                ),
            )
        if draft.facts is None:
            report = await self.dispatch(ctx, sender, "inspect", v["policy"])
            self.current(key, draft)
            draft.facts = interpret(report)
            terms = [
                t
                for t in report.terms
                if t.name in ("Employment termination", "Policy dates")
            ]
            draft.citation = "; ".join(
                f"p{e.locator.page}/{e.clause_id} {e.evidence_id}: {e.excerpt}"
                for t in terms
                for e in t.evidence
            )
        rules = draft.facts
        if rules.employment_linked.value is False:
            return (
                (
                    "This synthetic policy is not employment-linked; "
                    "passing dates does not guarantee coverage. "
                )
                + draft.citation
                + "\nInspect complete terms with /inspect "
                + v["policy"]
                + ". Would you like a dated comparison?"
            )
        if rules.employment_linked.value is None:
            return (
                "Employment linkage is unknown or conflicting; continuation "
                "cannot be determined. Obtain the missing terms. " + draft.citation
            )
        if not v.get("final_date"):
            return self.ask(
                draft,
                "final_date",
                draft.citation
                + (
                    "\n"
                    "What is your explicit final working date "
                    "(YYYY-MM-DD, today, tomorrow, or in N days)?"
                ),
            )
        if not draft.final_confirmed:
            return self.ask(
                draft,
                "confirm_final",
                f"Proposed final working date: {v['final_date']} "
                "(resolved using Asia/Kolkata). Reply 'confirm final date' "
                "or correct it. No scenario has run.",
            )
        fixed = rules.termination.value
        if fixed is None or rules.period.value is None:
            return (
                "The relevant termination/period term is unknown "
                "or conflicting; obtain clarification. "
            ) + draft.citation
        if v["final_date"] != fixed.final_employment_date:
            return self.ask(
                draft,
                "final_date",
                f"Contradiction: you confirmed {v['final_date']}; "
                f"this synthetic PDF fixes {fixed.final_employment_date} inclusive. "
                "The PDF was not overridden and is not your actual policy. "
                "Correct the date or explicitly say 'Show me the job-change demo'. "
                "Evidence: " + draft.citation,
            )
        last = min(fixed.final_employment_date, rules.period.value.end)
        finding = (
            f"For listed members, this synthetic employer protection ends {last} "
            "inclusive; it does not continue afterward. Other terms/eligibility "
            f"remain. Evidence: {draft.citation}\n"
        )
        if "personal_cover" not in v:
            return self.ask(
                draft,
                "personal_cover",
                finding
                + (
                    "Do you have existing personal cover: no personal"
                    " cover, existing personal cover, or unknown?"
                ),
            )
        return self.ask(
            draft,
            "next",
            finding
            + "Existing personal cover is "
            + v["personal_cover"]
            + (
                ". This alone does not establish a gap in all "
                "protection. Would you like to inspect "
                "existing-personal or request a dated plan "
                "comparison? No illness event has been assumed."
            ),
        )

    def inputs(self, draft):
        v = draft.values
        return RecommendationInput(
            path="employer-only"
            if v["personal_cover"] == "none"
            else "existing-personal",
            members=v["members"],
            annual_budget_paise=v["budget"],
            minimum_family_limit_paise=v["minimum_cover"],
            room_requirement=v["room"],
            proposed_start=v["proposed_start"],
            final_employment=v["final_date"],
            assumed_new_employer_start=v["new_start"],
            immediate_event=v["event_date"],
            later_event=v["later_date"],
            event_member_id=v["member_id"],
            event_type=v["event_type"],
        )

    def stress_inputs(self, draft):
        v = draft.values
        return JobChangeScenario(
            scenario_id="conversation-job-change",
            profile_id=None,
            member_ids=[v["member_id"]],
            description="Explicit synthetic event illustration",
            final_employment_date=v["final_date"],
            new_employer_coverage_start=v["new_start"],
            event_start=v["event_date"],
            event_type=v["event_type"],
        )

    def stress_review(self, draft):
        v = draft.values
        if "final_date" in v and not draft.final_confirmed:
            return self.ask(
                draft,
                "confirm_final",
                f"Final working date: {v['final_date']} (Asia/Kolkata). "
                "Reply 'confirm final date' or correct it.",
            )
        for name, question in (
            ("final_date", "What is the explicit final working date?"),
            (
                "new_start",
                "For the gap calculation, what new-employer coverage "
                "start date do you assume? Insurance is unverified.",
            ),
            (
                "event_type",
                "Which event do you explicitly request? Only illness "
                "hospitalization is supported; no event is assumed.",
            ),
            (
                "event_date",
                "What is the illustrative hospitalization date (YYYY-MM-DD)?",
            ),
            ("member_id", "Which listed member ID should be assessed?"),
        ):
            if name not in v:
                return self.ask(draft, name, question)
        try:
            s = self.stress_inputs(draft)
        except ValueError:
            return self.ask(
                draft,
                "correction",
                "Date/member ordering is invalid. "
                "Correct explicit inputs; see /stress-test.",
            )
        return self.ask(
            draft,
            "review",
            "Review stress inputs: preloaded fictional "
            "existing-employer and existing-personal, not proof you own both; "
            f"member {s.member_ids[0]}; final working date {s.final_employment_date}; "
            f"assumed new-employer start {s.new_employer_coverage_start}; "
            f"event {s.event_type} on {s.event_start}. Reply 'confirm inputs' "
            "to run this assessment, or correct one field.",
        )

    def comparison_review(self, draft):
        v = draft.values
        questions = [
            (
                "personal_cover",
                (
                    "Do you have no personal cover, existing personal"
                    " cover, or unknown? Only the preloaded fictional"
                    " policies can be compared."
                ),
            ),
            (
                "final_date",
                (
                    "What is the final working date? Use YYYY-MM-DD, "
                    "today, tomorrow, or in N days."
                ),
            ),
            (
                "members",
                (
                    "Which synthetic members need cover? Supply "
                    "member-ID:YYYY-MM-DD:self/spouse/child, "
                    "comma-separated. Omitted health disclosures "
                    "remain unknown."
                ),
            ),
            ("budget", "What annual premium budget, with explicit rupees or paise?"),
            (
                "minimum_cover",
                (
                    "What minimum shared family sum insured, with "
                    "explicit rupees or paise?"
                ),
            ),
            ("room", "Is the room requirement uncapped private room or any room?"),
            ("proposed_start", "What is the proposed new-policy start date?"),
            (
                "new_start",
                (
                    "For the employer-gap illustration, what "
                    "new-employer coverage start date do you assume? "
                    "This does not verify that insurance exists."
                ),
            ),
            (
                "event_type",
                (
                    "Do you explicitly want an illness "
                    "hospitalization illustration? That is the only "
                    "supported dated event; otherwise inspect a plan "
                    "instead. No illness is assumed."
                ),
            ),
            (
                "event_date",
                "What is the explicit illustrative illness hospitalization date?",
            ),
            (
                "later_date",
                (
                    "What separate later event date should every "
                    "policy be assessed against?"
                ),
            ),
            ("member_id", "Which supplied member ID is the illustrative patient?"),
        ]
        if v.get("personal_cover") == "unknown":
            return self.ask(
                draft,
                "personal_cover",
                (
                    "Baseline cover is unknown. Clarify no personal "
                    "cover or existing personal cover before a "
                    "comparison; I will not remove existing cover."
                ),
            )
        if v.get("final_date") and not draft.final_confirmed:
            return self.ask(
                draft,
                "confirm_final",
                f"Proposed final working date: {v['final_date']} (Asia/Kolkata). "
                "Reply 'confirm final date' or correct it.",
            )
        for name, question in questions:
            if name not in v:
                return self.ask(draft, name, question)
        if draft.goal == "quote":
            if v["personal_cover"] != "none":
                return self.ask(
                    draft,
                    "next",
                    (
                        "Existing personal cover is retained. The "
                        "existing Provider blocks this automatic quote "
                        "path; obtain missing terms before considering "
                        "duplicate cover. Use /recommend preset-existing "
                        "for the labelled demo."
                    ),
                )
            if "product" not in v:
                return self.ask(
                    draft,
                    "product",
                    (
                        "Which explicit preloaded product ID should be "
                        "quoted? Choose candidate-economy, "
                        "candidate-query or candidate-horizon; no plan "
                        "was selected for you."
                    ),
                )
            if any(m.preexisting == "unknown" for m in v["members"]):
                return self.ask(
                    draft,
                    "disclosures",
                    (
                        "The Provider requires synthetic health "
                        "disclosures before a quote. State each "
                        "member-ID:absent/present/unknown; absence is "
                        "never assumed."
                    ),
                )
        try:
            inputs = self.inputs(draft)
        except ValueError:
            return self.ask(
                draft,
                "correction",
                (
                    "Dates/member relationships or order are invalid."
                    " Correct the explicit dates/members; use "
                    "/recommend for contract guidance."
                ),
            )
        members = "; ".join(
            f"{m.member_id}, {m.date_of_birth}, {m.relationship}, "
            f"pre-existing {m.preexisting}"
            for m in inputs.members
        )
        return self.ask(
            draft,
            "review",
            f"Review synthetic inputs for {draft.goal} only (not purchase): "
            f"baseline {inputs.path}; members {members}; "
            f"annual budget {inr(inputs.annual_budget_paise)}; "
            f"minimum shared limit {inr(inputs.minimum_family_limit_paise)}; "
            f"room {inputs.room_requirement}; "
            f"final working date {inputs.final_employment}; "
            f"proposed start {inputs.proposed_start}; assumed/unverified "
            f"new-employer start {inputs.assumed_new_employer_start}; "
            f"illness hospitalization {inputs.immediate_event}, "
            f"separate later event {inputs.later_event}, "
            f"member {inputs.event_member_id}; "
            f"product {v.get('product', 'not selected for purchase')}. "
            "Reply 'confirm inputs' or correct one field. "
            "All policy findings still come from tools.",
        )

    async def handle(self, ctx, sender, text, notify):
        key = (sender, ctx.session)
        for old_key in [k for k, d in self.drafts.items() if d.expires <= self.timer()]:
            del self.drafts[old_key]
        draft = self.drafts.get(key)
        if draft and draft.busy:
            return (
                "This conversation is still processing its "
                "previous message. Wait for that reply, then send"
                " the correction again."
            )
        if draft is None:
            if len(self.drafts) >= self.capacity:
                return (
                    "Conversation capacity reached. Use /start and "
                    "exact commands or retry after drafts expire."
                )
            draft = self.drafts[key] = Draft(expires=self.timer() + self.ttl)
        draft.expires = self.timer() + self.ttl
        draft.busy = True
        value = text.casefold().strip().rstrip(".!?")
        try:
            if not draft.privacy_sent:
                await notify(PRIVACY)
                self.current(key, draft)
                draft.privacy_sent = True
            if (
                value in ("yes", "buy it", "approve", "purchase", "apply")
                or any(c in text for c in ('"', "“", "”", "`", "/"))
                or "http" in value
            ):
                return (
                    "Natural text cannot prepare or approve a "
                    "purchase or execute quoted instructions. Use the"
                    " exact application/approval commands from the "
                    "Provider. For draft data only, use 'confirm "
                    "final date' or 'confirm inputs' when asked. "
                    "/start lists tools."
                )
            if value in ("show me the job-change demo", "show me the job change demo"):
                draft.goal, draft.pending = "demo", "demo"
                return (
                    "Labelled synthetic demo: self member-01 born "
                    "1992-04-10 and spouse member-02 born 1994-08-15;"
                    " both explicitly absent pre-existing conditions."
                    " Budget ₹30,000/year, shared family limit at "
                    "least ₹10,00,000, uncapped private room. Final "
                    "working date 2026-12-31; proposed start "
                    "2027-01-01; assumed new employer cover "
                    "2027-02-01; illness hospitalization for "
                    "member-02 on 2027-01-15 and separate later date "
                    "2027-02-10. These are not your characteristics. "
                    "Reply 'run synthetic demo' to use these "
                    "fictional inputs; no purchase will occur."
                )
            if value == "run synthetic demo":
                if draft.pending != "demo":
                    return (
                        "First explicitly request 'Show me the job-change"
                        " demo' to review its fictional inputs."
                    )
                inputs = preset_input("preset")
                draft.values = dict(
                    personal_cover="none",
                    members=inputs.members,
                    budget=inputs.annual_budget_paise,
                    minimum_cover=inputs.minimum_family_limit_paise,
                    room=inputs.room_requirement,
                    final_date=inputs.final_employment,
                    proposed_start=inputs.proposed_start,
                    new_start=inputs.assumed_new_employer_start,
                    event_date=inputs.immediate_event,
                    later_date=inputs.later_event,
                    member_id=inputs.event_member_id,
                    event_type=inputs.event_type,
                )
                draft.final_confirmed = True
                draft.goal = "compare"
                report = await self.dispatch(ctx, sender, "compare", inputs)
                self.current(key, draft)
                draft.pending = "next"
                return "Explicit synthetic demo.\n" + present_recommendation(report)
            if draft.pending == "status_reference" and re.fullmatch(
                r"(?:q|a|op)-[0-9a-f]{32}", text.strip()
            ):
                return await self.read_status(ctx, sender, key, draft, text.strip())
            if value == "confirm final date":
                if draft.pending != "confirm_final" or "final_date" not in draft.values:
                    return (
                        "No final-date proposal is awaiting confirmation."
                        " Supply an explicit date first."
                    )
                draft.final_confirmed = True
            elif value == "confirm inputs":
                if draft.pending != "review" or draft.goal not in (
                    "compare",
                    "quote",
                    "stress",
                ):
                    return (
                        "No input review awaits confirmation. This phrase"
                        " cannot approve a purchase."
                    )
                draft.pending = "next"
                if draft.goal == "stress":
                    report = await self.dispatch(
                        ctx, sender, "stress", self.stress_inputs(draft)
                    )
                    self.current(key, draft)
                    return present_comparison(report)
                inputs = self.inputs(draft)
                if draft.goal == "compare":
                    report = await self.dispatch(ctx, sender, "compare", inputs)
                    self.current(key, draft)
                    return present_recommendation(report)
                reply, error = await self.dispatch(
                    ctx, sender, "quote", (draft.values["product"], inputs)
                )
                self.current(key, draft)
                if reply:
                    self.remember(sender, ctx.session, reply, draft)
                return error or present_sandbox(reply)
            else:
                if draft.pending == "policy":
                    available = REGISTRY | CANDIDATES
                    selection = text.strip()
                    if selection not in available:
                        return self.ask(
                            draft,
                            "policy",
                            "Choose one exact preloaded policy ID: "
                            + ", ".join(available)
                            + ".",
                        )
                    proposal = Intent(
                        action="update", fields=Fragments(policy=selection)
                    )
                else:
                    try:
                        proposal = await self.adapter.parse_intent(text, draft.pending)
                    except Exception:
                        return FALLBACK
                self.current(key, draft)
                if not isinstance(proposal, Intent):
                    return FALLBACK
                if proposal.action in ("demo", "clarify"):
                    return (
                        "Please state one supported request or explicitly"
                        " say 'Show me the job-change demo'. Use /start "
                        "for commands."
                    )
                gates = {
                    "job_change": (
                        "\\b(leav|leaving|leave|job|company|employer|continue)"
                    ),
                    "compare": r"\b(compare|comparison|recommend|plans)\b",
                    "quote": r"\b(quote|quotation)\b",
                    "stress": r"\b(stress|assess|hospitalization)\b",
                    "status": r"\bstatus\b",
                }
                if proposal.action in gates and not re.search(
                    gates[proposal.action], value
                ):
                    return (
                        "The proposed action wasn't explicitly requested."
                        " Please clarify; no action executed."
                    )
                if proposal.action == "status":
                    refs = re.findall(r"\b(?:q|a|op)-[0-9a-f]{32}\b", text)
                    if len(refs) > 1:
                        return "Which single reference should be retrieved?"
                    ref = refs[0] if refs else draft.refs[-1] if draft.refs else None
                    if not ref:
                        return self.ask(
                            draft,
                            "status_reference",
                            (
                                "What application reference from your own review "
                                "should I retrieve? After restart you can use its"
                                " exact /sandbox-status command."
                            ),
                        )
                    return await self.read_status(ctx, sender, key, draft, ref)
                self.apply(draft, proposal, text)
                if proposal.action != "update":
                    draft.goal = proposal.action
                if draft.goal == "inspect":
                    if not draft.values.get("policy"):
                        return self.ask(
                            draft,
                            "policy",
                            (
                                "Which exact preloaded policy ID should I "
                                "inspect? Send /policies to see supported "
                                "documents."
                            ),
                        )
                    report = await self.dispatch(
                        ctx, sender, "inspect", draft.values["policy"]
                    )
                    self.current(key, draft)
                    return present_policy(report)
            if draft.goal == "job_change":
                return await self.job(ctx, sender, key, draft)
            if draft.goal in ("compare", "quote"):
                return self.comparison_review(draft)
            if draft.goal == "stress":
                return self.stress_review(draft)
            return (
                "Would you like a job-change check, policy "
                "inspection or plan comparison? Use /start for "
                "exact commands."
            )
        except ValueError as exc:
            # Only bounded local operational messages; never model payloads/profiles.
            return (
                str(exc)
                if type(exc) is ValueError
                else "Input fields are invalid. Please clarify one field or use /start."
            )
        finally:
            draft.busy = False
