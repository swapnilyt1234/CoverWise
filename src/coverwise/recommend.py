"""Evidence-backed synthetic candidate assessment; no quotes or purchase state."""

import argparse
import asyncio
import re
import sys
from datetime import date
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from coverwise.catalogue import CatalogueSnapshot, Eligibility, Product
from coverwise.contracts import Contract, JobChangeScenario, Paise, PolicyInspection
from coverwise.money import display_money, inr
from coverwise.policies import MAX_REPLY, PolicyError, inspect_policies
from coverwise.stress import DAY, Assessment, Fact, Finding, assess, interpret

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,64}$")]
ROOM = (
    "Private single room without a daily monetary cap; "
    "overall family limit still applies."
)
HELP = (
    "Fictional recommendations only. /recommend preset | preset-low | "
    "preset-clarify | preset-existing. "
    "Explicit: /recommend <employer-only|existing-personal> "
    "<budget-paise> <minimum-family-limit-paise> <uncapped-private|any-room> "
    "<proposed-start> <final-employment> <assumed-new-employer-start> "
    "<immediate-event> <later-event> <event-member-id> "
    "<comma-separated members, each id:YYYY-MM-DD:relationship:disclosure>. "
    "Dates: YYYY-MM-DD; illness hospitalization only. "
    "Full evidence: /recommend-evidence <document-id> <page> <same inputs>. "
    "Timeout test: /recommend-timeout preset. No user characteristics inferred."
)


class Member(Contract):
    member_id: Identifier
    date_of_birth: date
    relationship: Literal["self", "spouse", "child"]
    preexisting: Literal["absent", "present", "unknown"]


class RecommendationInput(Contract):
    path: Literal["employer-only", "existing-personal"]
    members: list[Member] = Field(min_length=1, max_length=4)
    annual_budget_paise: Paise
    minimum_family_limit_paise: Annotated[int, Field(strict=True, gt=0)]
    room_requirement: Literal["uncapped-private", "any-room"]
    proposed_start: date
    final_employment: date
    assumed_new_employer_start: date
    immediate_event: date
    later_event: date
    event_member_id: Identifier
    event_type: Literal["illness_hospitalization"]

    @model_validator(mode="after")
    def coherent(self):
        ids = [m.member_id for m in self.members]
        if len(ids) != len(set(ids)) or self.event_member_id not in ids:
            raise ValueError(
                "unique member IDs and an event member from that list are required"
            )
        if self.later_event <= self.immediate_event:
            raise ValueError("later event must be strictly after immediate event")
        dates = [
            self.proposed_start,
            self.final_employment,
            self.assumed_new_employer_start,
            self.immediate_event,
            self.later_event,
        ]
        if min(dates) < date(1900, 1, 1) or max(dates) > date(2100, 12, 31):
            raise ValueError("scenario dates must be between 1900 and 2100")
        if any(
            m.date_of_birth > min(self.proposed_start, self.immediate_event)
            or m.date_of_birth < date(1900, 1, 1)
            for m in self.members
        ):
            raise ValueError(
                "birth dates must be valid and on/before proposed start and event"
            )
        scenario(self, self.immediate_event)
        return self


def scenario(inputs: RecommendationInput, event: date) -> JobChangeScenario:
    return JobChangeScenario(
        scenario_id=f"recommend-{event}-{inputs.event_member_id}",
        profile_id=None,
        member_ids=[inputs.event_member_id],
        description="Explicit synthetic illness illustration",
        event_start=event,
        final_employment_date=inputs.final_employment,
        new_employer_coverage_start=inputs.assumed_new_employer_start,
        event_type=inputs.event_type,
    )


class Dimension(Contract):
    status: Literal["pass", "fail", "unknown"]
    reasons: list[str]
    evidence_ids: list[str]


class PolicyEvents(Contract):
    immediate: Assessment
    later: Assessment


class Candidate(PolicyEvents):
    product_id: str
    eligibility: Dimension
    budget: Dimension
    requirements: Dimension
    material_unknowns: list[str]
    disposition: Literal["rejected", "clarify", "qualifies"]
    first_eligible_day: date


class Recommendation(Contract):
    inputs: RecommendationInput
    catalogue: CatalogueSnapshot
    inspections: list[PolicyInspection] = Field(min_length=2, max_length=5)
    baseline: list[PolicyEvents] = Field(min_length=1, max_length=2)
    candidates: list[Candidate] = Field(min_length=1, max_length=3)
    shortlist: list[str]
    outcome: Literal[
        "shortlist",
        "no_suitable_option",
        "provider_clarification_required",
        "keep_existing_obtain_terms",
        "correct_scenario",
    ]
    employer_gap: str

    @model_validator(mode="after")
    def bound(self):
        docs = {p.document.document_id: p for p in self.inspections}
        if len(docs) != len(self.inspections):
            raise ValueError("duplicate inspections")
        baseline_ids = ["existing-employer"]
        if self.inputs.path == "existing-personal":
            baseline_ids.append("existing-personal")
        if [p.immediate.document.document_id for p in self.baseline] != baseline_ids:
            raise ValueError("baseline policy mismatch")
        if [c.product_id for c in self.candidates] != [
            p.product_id for p in self.catalogue.catalogue.products
        ]:
            raise ValueError("candidate set differs from Provider catalogue")
        for pair in [*self.baseline, *self.candidates]:
            for assessment, event in (
                (pair.immediate, self.inputs.immediate_event),
                (pair.later, self.inputs.later_event),
            ):
                report = docs.get(assessment.document.document_id)
                if report is None or report.document != assessment.document:
                    raise ValueError("assessment document mismatch")
                if assessment.scenario_id != scenario(self.inputs, event).scenario_id:
                    raise ValueError("assessment scenario mismatch")
                ids = {e.evidence_id for t in report.terms for e in t.evidence}
                used = set(assessment.evidence_ids) | {
                    i for f in assessment.findings for i in f.evidence_ids
                }
                if not used <= ids:
                    raise ValueError("foreign assessment evidence")
        for candidate in self.candidates:
            if (
                candidate.immediate.document.document_id != candidate.product_id
                or candidate.later.document.document_id != candidate.product_id
            ):
                raise ValueError("candidate assessment policy mismatch")
            ids = {
                e.evidence_id
                for t in docs[candidate.product_id].terms
                for e in t.evidence
            }
            all_ids = {
                e.evidence_id
                for p in self.inspections
                for t in p.terms
                for e in t.evidence
            }
            if (
                not set(
                    candidate.eligibility.evidence_ids
                    + candidate.requirements.evidence_ids
                )
                <= ids
            ):
                raise ValueError("foreign candidate evidence")
            if not set(candidate.budget.evidence_ids) <= all_ids:
                raise ValueError("foreign budget evidence")
        if any(
            p
            not in {
                c.product_id for c in self.candidates if c.disposition == "qualifies"
            }
            for p in self.shortlist
        ):
            raise ValueError("shortlist contains nonqualifying product")
        return self


def term(report, name, parse):
    terms = [t for t in report.terms if t.name == name]
    ids = [e.evidence_id for t in terms for e in t.evidence]
    value = None
    if len(terms) == 1 and terms[0].status == "stated":
        try:
            value = parse(terms[0].value)
        except ValueError:
            pass
    return Fact(
        value=value,
        evidence_ids=ids,
        unknown=None
        if value is not None
        else f"{name}: missing, conflicting or unsupported",
    )


def matched_integer(value, pattern):
    match = re.fullmatch(pattern, value)
    return int(match[1]) if match else None


def candidate_facts(report, product: Product):
    def eligibility(value):
        m = re.fullmatch(
            r"Self required; spouse optional; entry ages (\d+) through (\d+) inclusive "
            r"at proposed start; maximum (\d+) members; "
            r"pre-existing conditions must be declared absent\.",
            value,
        )
        return (
            Eligibility(
                min_age=int(m[1]),
                max_age=int(m[2]),
                max_members=int(m[3]),
                relationships=["self", "spouse"],
                no_preexisting_required=True,
            )
            if m
            else None
        )

    facts = {
        "identity": term(report, "Identity", lambda v: v),
        "eligibility": term(report, "Eligibility", eligibility),
        "premium": term(
            report,
            "Annual premium",
            lambda v: matched_integer(
                v, r"(\d+) INR paise, indicative annual family list premium\."
            ),
        ),
        "basis": term(report, "Premium basis", lambda v: v),
        "limit": term(
            report,
            "Sum insured",
            lambda v: matched_integer(
                v,
                r"(\d+) INR paise per policy year, "
                r"shared family hospitalization limit\.",
            ),
        ),
        "room": term(
            report,
            "Room rent",
            lambda v: (
                True
                if v == ROOM
                else False
                if re.fullmatch(
                    r"\d+ INR paise per day maximum room reimbursement\.", v
                )
                else None
            ),
        ),
        "days": term(
            report,
            "Policy dates",
            lambda v: matched_integer(
                v,
                r"(\d+) days from proposed start, inclusive; "
                r"independent of employment\.",
            ),
        ),
        "wait": term(
            report,
            "Waiting period",
            lambda v: matched_integer(
                v,
                r"Initial illness wait is (\d+) days from proposed start, inclusive\. "
                r"No continuity credit or waiver is granted\.",
            ),
        ),
    }
    expected = dict(
        identity=f"{product.name}; insurer {product.insurer}; synthetic only.",
        eligibility=product.eligibility,
        premium=product.annual_premium_paise,
        basis=product.premium_basis,
        limit=product.family_limit_paise,
        room=product.uncapped_private_room,
        days=product.policy_days,
        wait=product.initial_wait_days,
    )
    if any(facts[k].value != value for k, value in expected.items()):
        raise PolicyError("catalogue_pdf_disagreement")
    return facts


def events(report, inputs):
    rules = interpret(
        report, inputs.proposed_start, [m.member_id for m in inputs.members]
    )
    return PolicyEvents(
        immediate=assess(report, scenario(inputs, inputs.immediate_event), rules),
        later=assess(report, scenario(inputs, inputs.later_event), rules),
    )


def evaluate(
    inputs: RecommendationInput,
    snapshot: CatalogueSnapshot,
    inspections: list[PolicyInspection],
) -> Recommendation:
    docs = {p.document.document_id: p for p in inspections}
    expected = {
        "existing-employer",
        *(p.document.document_id for p in snapshot.catalogue.products),
    }
    if inputs.path == "existing-personal":
        expected.add("existing-personal")
    if set(docs) != expected or len(docs) != len(inspections):
        raise PolicyError("invalid_result")
    baseline = [events(docs["existing-employer"], inputs)]
    retained_value = 0
    retained_ids = []
    # Zero here is an explicit employer-only path, not an absent premium inference.
    if inputs.path == "existing-personal":
        baseline.append(events(docs["existing-personal"], inputs))
        retained = term(
            docs["existing-personal"],
            "Annual premium",
            lambda v: matched_integer(
                v, r"(\d+) INR paise, total annual premium for both members\."
            ),
        )
        retained_value = retained.value
        retained_ids = retained.evidence_ids
    candidates = []
    for product in snapshot.catalogue.products:
        report = docs[product.document.document_id]
        if (
            report.document.sha256 != product.document.sha256
            or report.document.document_version != product.document.document_version
        ):
            raise PolicyError("catalogue_pdf_disagreement")
        facts = candidate_facts(report, product)
        eligibility = facts["eligibility"].value
        reasons = []
        unknown = []
        if len(inputs.members) > eligibility.max_members:
            reasons.append(f"maximum {eligibility.max_members} members")
        relationships = [m.relationship for m in inputs.members]
        if relationships.count("self") != 1 or relationships.count("spouse") > 1:
            reasons.append("one self and at most one spouse required")
        for member in inputs.members:
            dob = member.date_of_birth
            age = (
                inputs.proposed_start.year
                - dob.year
                - (
                    (inputs.proposed_start.month, inputs.proposed_start.day)
                    < (dob.month, dob.day)
                )
            )
            if not eligibility.min_age <= age <= eligibility.max_age:
                reasons.append(
                    f"{member.member_id} age {age} outside "
                    f"{eligibility.min_age}–{eligibility.max_age}"
                )
            if member.relationship not in eligibility.relationships:
                reasons.append(f"{member.member_id}: {member.relationship} unsupported")
            if member.preexisting == "present":
                reasons.append(
                    f"{member.member_id}: declared pre-existing condition not eligible"
                )
            elif member.preexisting == "unknown":
                unknown.append(f"{member.member_id}: absence disclosure required")
        elig = Dimension(
            status="fail" if reasons else "unknown" if unknown else "pass",
            reasons=reasons + unknown
            or [
                "all supplied ages, relationships and disclosures satisfy stated rules"
            ],
            evidence_ids=facts["eligibility"].evidence_ids,
        )
        budget = Dimension(
            status="unknown"
            if retained_value is None
            else "pass"
            if product.annual_premium_paise + retained_value
            <= inputs.annual_budget_paise
            else "fail",
            reasons=[
                "retained annual premium unknown"
                if retained_value is None
                else "annual total "
                f"{inr(product.annual_premium_paise + retained_value)} "
                f"including retained personal premium {inr(retained_value)}; "
                f"budget {inr(inputs.annual_budget_paise)}"
            ],
            evidence_ids=facts["premium"].evidence_ids + retained_ids,
        )
        failures = []
        unclear = []
        if facts["limit"].value < inputs.minimum_family_limit_paise:
            failures.append("family limit below required minimum")
        if inputs.room_requirement == "uncapped-private":
            if facts["room"].value is False:
                failures.append(
                    "daily room cap fails uncapped private-room requirement"
                )
            elif facts["room"].value is None:
                unclear.append("room schedule absent; uncapped private room unverified")
        fit = Dimension(
            status="fail" if failures else "unknown" if unclear else "pass",
            reasons=failures + unclear or ["family limit and room requirement met"],
            evidence_ids=facts["limit"].evidence_ids + facts["room"].evidence_ids,
        )
        pair = events(report, inputs)
        if elig.status != "pass":
            detail = "; ".join(elig.reasons)
            for assessment in (pair.immediate, pair.later):
                assessment.findings.append(
                    Finding(
                        check="eligibility",
                        outcome="excluded" if elig.status == "fail" else "unknown",
                        detail=detail,
                        evidence_ids=elig.evidence_ids,
                    )
                )
                if elig.status == "fail":
                    assessment.status = "excluded"
                    assessment.next_action = (
                        "Members fail the stated entry rules; "
                        "no candidate cover established."
                    )
                else:
                    assessment.missing_information.append(detail)
                    if assessment.status != "excluded":
                        assessment.status = "insufficient_information"
                    assessment.next_action = (
                        "Clarify required member disclosures "
                        "before any eligibility conclusion."
                    )
        unknown.extend(
            pair.immediate.missing_information
            + pair.later.missing_information
            + unclear
        )
        if retained_value is None:
            unknown.append("existing personal premium unknown")
        unknown = list(dict.fromkeys(unknown))
        dimensions = [elig.status, budget.status, fit.status]
        disposition = (
            "rejected"
            if "fail" in dimensions
            else "clarify"
            if "unknown" in dimensions or unknown
            else "rejected"
            if pair.later.status == "excluded"
            else "qualifies"
        )
        candidates.append(
            Candidate(
                product_id=product.product_id,
                **pair.model_dump(),
                eligibility=elig,
                budget=budget,
                requirements=fit,
                material_unknowns=unknown,
                disposition=disposition,
                first_eligible_day=inputs.proposed_start + DAY * facts["wait"].value,
            )
        )
    shortlist = [
        c.product_id
        for c in sorted(
            (c for c in candidates if c.disposition == "qualifies"),
            key=lambda c: (
                next(
                    p.annual_premium_paise
                    for p in snapshot.catalogue.products
                    if p.product_id == c.product_id
                ),
                c.product_id,
            ),
        )
    ]
    employer = baseline[0]
    correction = (
        employer.immediate.temporal == "correction_required"
        or employer.later.temporal == "correction_required"
    )
    if correction:
        outcome = "correct_scenario"
        shortlist = []
    elif inputs.path == "existing-personal":
        outcome = "keep_existing_obtain_terms"
        shortlist = []
    else:
        outcome = (
            "shortlist"
            if shortlist
            else "provider_clarification_required"
            if any(c.disposition == "clarify" for c in candidates)
            else "no_suitable_option"
        )
    rules = interpret(docs["existing-employer"])
    if (
        correction
        or rules.period.value is None
        or rules.termination.value is None
        or rules.members.value is None
        or inputs.event_member_id not in rules.members.value
    ):
        gap = "Employer-protection gap unknown; resolve scenario/document terms."
    else:
        end = min(rules.period.value.end, rules.termination.value.final_employment_date)
        gap = f"Employer protection ends {end} inclusive; " + (
            f"employer-protection gap {end + DAY} through "
            f"{inputs.assumed_new_employer_start - DAY} inclusive."
            if end + DAY < inputs.assumed_new_employer_start
            else "no gap before assumed new cover."
        )
    return Recommendation(
        inputs=inputs,
        catalogue=snapshot,
        inspections=inspections,
        baseline=baseline,
        candidates=candidates,
        shortlist=shortlist,
        outcome=outcome,
        employer_gap=gap,
    )


def run(inputs, snapshot):
    ids = ["existing-employer"]
    if inputs.path == "existing-personal":
        ids.append("existing-personal")
    ids.extend(p.document.document_id for p in snapshot.catalogue.products)
    return evaluate(inputs, snapshot, inspect_policies(ids))


def parse_input(payload: str) -> RecommendationInput:
    if len(payload) > 1500:
        raise ValueError("Recommendation input exceeds 1500 characters. " + HELP)
    presets = {
        "preset": ("employer-only", "3000000"),
        "preset-low": ("employer-only", "1000000"),
        "preset-clarify": ("employer-only", "2000000"),
        "preset-existing": ("existing-personal", "3000000"),
    }
    if payload in presets:
        path, budget = presets[payload]
        payload = (
            f"{path} {budget} 100000000 uncapped-private "
            "2027-01-01 2026-12-31 2027-02-01 2027-01-15 2027-02-10 member-02 "
            "member-01:1992-04-10:self:absent,member-02:1994-08-15:spouse:absent"
        )
    parts = payload.split(" ")
    if len(parts) != 11 or any(not p for p in parts):
        raise ValueError(
            "Clarification required: supply all eleven explicit fields. " + HELP
        )
    (
        path,
        budget,
        minimum,
        room,
        start,
        final,
        new,
        event,
        later,
        event_member,
        members,
    ) = parts
    try:
        if not all(re.fullmatch(r"\d{1,16}", n) for n in (budget, minimum)):
            raise ValueError("budget and minimum limit must be integer paise")
        if not all(
            re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)
            for d in (start, final, new, event, later)
        ):
            raise ValueError("dates must use YYYY-MM-DD")
        member_inputs = []
        for raw in members.split(","):
            identifier, dob, relationship, disclosure = raw.split(":")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dob):
                raise ValueError("birth dates must use YYYY-MM-DD")
            member_inputs.append(
                Member(
                    member_id=identifier,
                    date_of_birth=dob,
                    relationship=relationship,
                    preexisting=disclosure,
                )
            )
        return RecommendationInput(
            path=path,
            members=member_inputs,
            annual_budget_paise=int(budget),
            minimum_family_limit_paise=int(minimum),
            room_requirement=room,
            proposed_start=start,
            final_employment=final,
            assumed_new_employer_start=new,
            immediate_event=event,
            later_event=later,
            event_member_id=event_member,
            event_type="illness_hospitalization",
        )
    except ValueError as exc:
        raise ValueError(f"Clarification required: {exc}. " + HELP) from None


def reference(report, document_id, names):
    inspection = next(
        p for p in report.inspections if p.document.document_id == document_id
    )
    return ", ".join(
        dict.fromkeys(
            f"p{e.locator.page}/{e.clause_id}"
            for t in inspection.terms
            if t.name in names
            for e in t.evidence
        )
    )


def present(report: Recommendation) -> str:
    i = report.inputs
    lines = [
        "Result: " + report.outcome.replace("_", " ") + ".",
        "Fictional/synthetic catalogue; indicative annual family list prices, "
        "not quotes.",
        f"Requirements: {len(i.members)} members "
        f"({', '.join(m.member_id for m in i.members)}); "
        f"budget {inr(i.annual_budget_paise)}/year including retained cover; "
        f"family limit ≥{inr(i.minimum_family_limit_paise)}; "
        f"room={i.room_requirement}.",
        f"Assumptions: proposed start {i.proposed_start}; "
        f"final employment {i.final_employment}; "
        f"new employer cover assumed {i.assumed_new_employer_start} (unverified). "
        f"Event member {i.event_member_id}; illness hospitalization "
        f"{i.immediate_event}; separate later scenario {i.later_event}, "
        "identical across policies.",
        "Ages and disclosures use explicit synthetic inputs; no user facts inferred.",
        report.employer_gap
        + " ["
        + reference(
            report, "existing-employer", ["Policy dates", "Employment termination"]
        )
        + "]",
        "Baseline: "
        + "; ".join(
            f"{p.immediate.document.document_id}: "
            f"immediate {p.immediate.status}, later {p.later.status}"
            for p in report.baseline
        )
        + ".",
    ]
    lines.append(
        "Baseline limits: "
        + "; ".join(
            dict.fromkeys(
                m for p in report.baseline for m in p.immediate.missing_information
            )
        )
        + ". Passing temporal checks is not coverage assurance."
    )
    if i.path == "existing-personal":
        personal = next(
            p
            for p in report.inspections
            if p.document.document_id == "existing-personal"
        )
        values = "; ".join(
            display_money(t.value)
            for t in personal.terms
            if t.name in ("Sum insured", "Room rent", "Annual premium") and t.value
        )
        waiting = next(
            f.detail
            for f in report.baseline[1].immediate.findings
            if f.check == "waiting"
        )
        lines.append(
            "Existing personal retained: "
            + values
            + " "
            + waiting
            + " ["
            + reference(
                report,
                "existing-personal",
                ["Sum insured", "Room rent", "Waiting period", "Annual premium"],
            )
            + "]"
        )
    for c, p in zip(report.candidates, report.catalogue.catalogue.products):
        reason = "; ".join(c.requirements.reasons)
        if c.eligibility.status != "pass":
            reason += "; " + "; ".join(c.eligibility.reasons)
        if c.budget.status != "pass":
            reason += "; " + "; ".join(c.budget.reasons)
        if c.material_unknowns:
            reason += "; unresolved: " + "; ".join(c.material_unknowns)
        inspection = next(
            x for x in report.inspections if x.document.document_id == c.product_id
        )
        room_term = next(t for t in inspection.terms if t.name == "Room rent")
        room_display = (
            display_money(room_term.value)
            if room_term.value
            else "unknown room schedule"
        )
        lines.append(
            f"{p.name} ({p.product_id}), {inr(p.annual_premium_paise)}/year: "
            f"family limit {inr(p.family_limit_paise)}; {room_display} "
            f"eligibility {c.eligibility.status}; budget {c.budget.status}; "
            f"requirements {c.requirements.status}; {c.disposition}. {reason}. "
            f"Immediate {c.immediate.status}; later {c.later.status}. ["
            + reference(
                report,
                c.product_id,
                ["Eligibility", "Annual premium", "Sum insured", "Room rent"],
            )
            + "]"
        )
    lines.append(
        "Fresh waits; no continuity credit/waiver. "
        + "; ".join(
            f"{c.product_id}: N={p.initial_wait_days}; "
            f"first post-wait day {c.first_eligible_day} "
            f"[{reference(report, c.product_id, ['Waiting period'])}]"
            for c, p in zip(report.candidates, report.catalogue.catalogue.products)
        )
        + ". Immediate event cannot be covered during that wait, "
        "even for a longer-term shortlist."
    )
    action = {
        "shortlist": "Prospective shortlist: "
        + ", ".join(report.shortlist)
        + ". Ranking: hard failures/unknowns removed first, then lowest annual "
        "list premium, product ID tie-break. Confirm eligibility and document "
        "terms before any future application.",
        "no_suitable_option": "No suitable option for these inputs; "
        "revise requirements/budget or seek another catalogue.",
        "provider_clarification_required": "Provider clarification required; "
        "obtain the missing room schedule/disclosures. "
        "No suitable option is established.",
        "keep_existing_obtain_terms": "Keep existing personal cover in the comparison; "
        "obtain missing terms before considering additional cover. "
        "Its waiting result is date-dependent; family/room restrictions and "
        "scoped/unknown terms remain. No replacement or duplicate-cover purchase is "
        "recommended.",
        "correct_scenario": "Correct the scenario/document employment-date "
        "mismatch and rerun; no shortlist established.",
    }[report.outcome]
    lines.extend(
        [
            action,
            "Limits: unknown terms remain visible in detailed evidence; "
            "later conditional results remain subject to exclusions and eligibility; "
            "no automatic stacking, acceptance, claim approval or payout promise. "
            "No cover issued or purchase made.",
            f"Catalogue {report.catalogue.catalogue.catalogue_version}. "
            "Detailed assessment/evidence with the same explicit inputs:\n```text\n"
            + "/recommend-evidence candidate-horizon 3 "
            + input_text(i)
            + "\n```",
        ]
    )
    text = "\n".join(lines)
    if len(text) > MAX_REPLY:
        raise PolicyError("result_too_large")
    return text


def input_text(inputs: RecommendationInput) -> str:
    """Serialize all existing explicit command fields without profile defaults."""
    i = inputs
    members = ",".join(
        f"{m.member_id}:{m.date_of_birth}:{m.relationship}:{m.preexisting}"
        for m in i.members
    )
    return (
        f"{i.path} {i.annual_budget_paise} {i.minimum_family_limit_paise} "
        f"{i.room_requirement} {i.proposed_start} {i.final_employment} "
        f"{i.assumed_new_employer_start} {i.immediate_event} {i.later_event} "
        f"{i.event_member_id} {members}"
    )


def present_evidence(report: Recommendation, document_id: str, page: int) -> str:
    inspection = next(
        (p for p in report.inspections if p.document.document_id == document_id), None
    )
    if inspection is None or not 1 <= page <= inspection.document.page_count:
        return "Choose an assessed document and a valid PDF page (1–6)."
    lines = [
        f"Detailed synthetic evidence: {document_id}, "
        f"p{page}/{inspection.document.page_count}; "
        f"SHA-256 {inspection.document.sha256}",
        f"Catalogue {report.catalogue.catalogue.catalogue_version}; "
        f"source SHA-256 {report.catalogue.source_sha256}",
        f"Inputs: {report.inputs.model_dump_json()}",
    ]
    for term_ in inspection.terms:
        for evidence in term_.evidence:
            if evidence.locator.page == page:
                lines.append(
                    f"{term_.name}: {term_.status}; {evidence.clause_id}; "
                    f"{evidence.evidence_id}\n{evidence.excerpt}"
                )
    pairs = [
        p
        for p in [*report.baseline, *report.candidates]
        if p.immediate.document.document_id == document_id
    ]
    for pair in pairs:
        if isinstance(pair, Candidate):
            for name in ("eligibility", "budget", "requirements"):
                dimension = getattr(pair, name)
                lines.append(
                    f"{name}: {dimension.status}; {'; '.join(dimension.reasons)}; "
                    f"evidence {', '.join(dimension.evidence_ids)}"
                )
        for label, assessment in (
            ("Immediate", pair.immediate),
            ("Separate later scenario", pair.later),
        ):
            lines.append(
                f"{label}: {assessment.status}; temporal {assessment.temporal}; "
                f"scenario {assessment.scenario_id}"
            )
            lines.extend(
                f"{f.check}: {f.outcome}: {f.detail} [{', '.join(f.evidence_ids)}]"
                for f in assessment.findings
            )
            lines.append("Missing: " + "; ".join(assessment.missing_information))
            lines.append("Next: " + assessment.next_action)
    lines.append(
        "Next evidence page:\n```text\n/recommend-evidence "
        f"{document_id} {page % inspection.document.page_count + 1} "
        + input_text(report.inputs)
        + "\n```\nNo payment assurance."
    )
    text = "\n".join(lines)
    if len(text) > MAX_REPLY:
        raise PolicyError("result_too_large")
    return text


def main() -> int:
    from coverwise.agents import offline_recommend

    parser = argparse.ArgumentParser(description=HELP)
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("--provider-timeout", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(
            offline_recommend(parse_input(" ".join(args.inputs)), args.provider_timeout)
        )
        if result.status != "success":
            print(
                "Offline handler harness: recommendation incomplete "
                f"({result.error}); no recommendation fabricated."
            )
            return 2
        report = Recommendation.model_validate_json(result.payload_json)
        output = (
            report.model_dump_json(indent=2)
            if args.json
            else "Offline SDK handler harness; not live transport.\n" + present(report)
        )
        sys.stdout.buffer.write((output + "\n").encode("utf-8"))
        return 0
    except (ValueError, PolicyError) as exc:
        print(f"Recommendation unavailable: {exc}")
        return 1


if __name__ == "__main__":
    # Keep contract identities canonical when the offline SDK harness imports us.
    from coverwise.recommend import main as cli_main

    raise SystemExit(cli_main())
