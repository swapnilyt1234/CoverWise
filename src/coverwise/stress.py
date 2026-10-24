"""Deterministic interpretation of the documented synthetic PDF clause grammar."""

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Generic, Literal, TypeVar

from pydantic import Field, model_validator

from coverwise.contracts import (
    Contract,
    CoverageAssessment,
    JobChangeScenario,
    PolicyInspection,
)
from coverwise.policies import MAX_REPLY, PolicyError, inspect_policy

T = TypeVar("T")
DAY = timedelta(days=1)
DATE = r"(\d{4}-\d{2}-\d{2})"
USAGE = (
    "/stress-test preset OR /stress-test <member-id> <final-employment YYYY-MM-DD> "
    "<assumed-new-cover YYYY-MM-DD> <hospitalization YYYY-MM-DD> "
    "illness_hospitalization"
)


class Interval(Contract):
    start: date
    end: date
    endpoints: Literal["inclusive"] = "inclusive"

    @model_validator(mode="after")
    def ordered(self):
        if self.end < self.start:
            raise ValueError("interval end precedes start")
        return self


class Fact(Contract, Generic[T]):
    value: T | None
    evidence_ids: list[str]
    unknown: str | None

    @model_validator(mode="after")
    def sourced(self):
        if self.value is not None and (not self.evidence_ids or self.unknown):
            raise ValueError("interpreted fact requires evidence and no unknown reason")
        if self.value is None and not self.unknown:
            raise ValueError("unknown fact requires a reason")
        return self


class Termination(Contract):
    final_employment_date: date
    rule: Literal["earlier_of_final_employment_and_policy_expiry"] = (
        "earlier_of_final_employment_and_policy_expiry"
    )
    endpoint: Literal["inclusive"] = "inclusive"


class Rules(Contract):
    period: Fact[Interval]
    members: Fact[list[str]]
    employment_linked: Fact[bool]
    termination: Fact[Termination]
    waiting: Fact[Interval | Literal["none"]]
    exclusions: Fact[list[str]]


class Finding(Contract):
    check: str
    outcome: Literal["pass", "excluded", "unknown", "conflict"]
    detail: str
    evidence_ids: list[str]


class Assessment(CoverageAssessment):
    temporal: Literal["passes", "excluded", "unknown", "correction_required"]
    findings: list[Finding]


class Comparison(Contract):
    scenario: JobChangeScenario
    inspections: list[PolicyInspection] = Field(min_length=2, max_length=2)
    assessments: list[Assessment] = Field(min_length=2, max_length=2)
    employer_last_day: date | None
    gap: Interval | None
    gap_known: bool

    @model_validator(mode="after")
    def bound_evidence(self):
        if [p.document.document_id for p in self.inspections] != [
            "existing-employer",
            "existing-personal",
        ]:
            raise ValueError("comparison requires the two existing policies in order")
        for inspection, assessment in zip(self.inspections, self.assessments):
            ids = {e.evidence_id for t in inspection.terms for e in t.evidence}
            if assessment.document != inspection.document:
                raise ValueError("assessment document mismatch")
            if assessment.scenario_id != self.scenario.scenario_id:
                raise ValueError("assessment scenario mismatch")
            used = set(assessment.evidence_ids)
            used.update(e for f in assessment.findings for e in f.evidence_ids)
            if not used <= ids:
                raise ValueError("assessment references foreign evidence")
        return self


def interpret(
    report: PolicyInspection,
    proposed_start: date | None = None,
    proposed_members: list[str] | None = None,
) -> Rules:
    def read(name, parse):
        terms = [t for t in report.terms if t.name == name]
        ids = [e.evidence_id for t in terms for e in t.evidence]
        reason = "missing"
        value = None
        if len(terms) == 1:
            term = terms[0]
            reason = term.status
            if term.status == "stated":
                try:
                    value = parse(term.value)
                except (ValueError, TypeError):
                    value = None
                reason = "unrecognized or invalid synthetic syntax"
        elif terms:
            reason = "conflicting duplicate terms"
        return Fact(
            value=value,
            evidence_ids=ids,
            unknown=None if value is not None else f"{name}: {reason}",
        )

    def period(value):
        relative = re.fullmatch(
            r"(\d{1,3}) days from proposed start, inclusive; "
            r"independent of employment\.",
            value,
        )
        if relative:
            if proposed_start is None or int(relative[1]) < 1:
                return None
            return Interval(
                start=proposed_start, end=proposed_start + DAY * (int(relative[1]) - 1)
            )
        match = re.fullmatch(
            DATE
            + " through "
            + DATE
            + r" inclusive(\.|; subject to employment termination\.)",
            value,
        )
        return Interval(start=match[1], end=match[2]) if match else None

    def linked(value):
        if period(value) is None:
            return None
        return value.endswith("; subject to employment termination.")

    def members(value):
        if value == "Proposed members subject to eligibility; no cover is issued.":
            return proposed_members
        pattern = (
            r"([A-Za-z0-9-]{1,64}) [A-Za-z ]+ \((?:self|spouse), born " + DATE + r"\)"
        )
        parts = value.removesuffix(".").split("; ")
        matches = [re.fullmatch(pattern, part) for part in parts]
        if not value.endswith(".") or not all(matches):
            return None
        for match in matches:
            date.fromisoformat(match[2])
        ids = [match[1] for match in matches]
        return ids if len(ids) == len(set(ids)) else None

    def termination(value):
        match = re.fullmatch(
            r"Coverage for both members ends on [A-Za-z ]+'s final employment date, "
            + DATE
            + r" inclusive, or policy expiry if earlier\. "
            r"No conversion or continuity benefit\.",
            value,
        )
        return Termination(final_employment_date=match[1]) if match else None

    def waiting(value):
        relative = re.fullmatch(
            r"Initial illness wait is (\d{1,3}) days from proposed start, inclusive\. "
            r"No continuity credit or waiver is granted\.",
            value,
        )
        if relative:
            if proposed_start is None or int(relative[1]) < 1:
                return None
            return Interval(
                start=proposed_start, end=proposed_start + DAY * (int(relative[1]) - 1)
            )
        if (
            value == "None for initial illness hospitalization "
            "under this synthetic employer policy."
        ):
            return "none"
        match = re.fullmatch(
            "Initial illness waiting interval is "
            + DATE
            + " through "
            + DATE
            + r" inclusive\. No continuity credit or waiver is granted\.",
            value,
        )
        return Interval(start=match[1], end=match[2]) if match else None

    return Rules(
        period=read("Policy dates", period),
        members=read("Covered members", members),
        employment_linked=read("Policy dates", linked),
        termination=read("Employment termination", termination),
        waiting=read("Waiting period", waiting),
        exclusions=read(
            "Exclusions",
            lambda v: (
                ["cosmetic_treatment", "elective_dental_treatment"]
                if v == "Cosmetic treatment and elective dental treatment are excluded."
                else ["illness_hospitalization"]
                if v == "Illness hospitalization is excluded."
                else None
            ),
        ),
    )


def assess(
    report: PolicyInspection, scenario: JobChangeScenario, rules: Rules
) -> Assessment:
    findings = []

    def add(check, outcome, detail, fact):
        findings.append(
            Finding(
                check=check,
                outcome=outcome,
                detail=detail,
                evidence_ids=fact.evidence_ids,
            )
        )

    member = scenario.member_ids[0]
    event = scenario.event_start
    for name, fact in (
        ("member", rules.members),
        ("period", rules.period),
        ("waiting", rules.waiting),
        ("exclusions", rules.exclusions),
    ):
        if fact.value is None:
            add(name, "unknown", fact.unknown, fact)
        elif name == "member":
            listed = member in fact.value
            add(
                name,
                "pass" if listed else "excluded",
                f"{member} is {'listed' if listed else 'not listed'}.",
                fact,
            )
        elif name == "period":
            inside = fact.value.start <= event <= fact.value.end
            add(
                name,
                "pass" if inside else "excluded",
                f"Event {'within' if inside else 'outside'} policy period "
                f"{fact.value.start} through {fact.value.end}, inclusive.",
                fact,
            )
        elif name == "waiting":
            interval = fact.value
            inside = interval != "none" and interval.start <= event <= interval.end
            detail = (
                "Explicitly no initial illness waiting interval."
                if interval == "none"
                else f"Illness wait {interval.start} through {interval.end}, "
                "inclusive; "
                + (
                    "event inside wait."
                    if inside
                    else "elapsed on event date."
                    if event > interval.end
                    else "not yet started on event date."
                )
            )
            add(name, "excluded" if inside else "pass", detail, fact)
        else:
            excluded = scenario.event_type in fact.value
            add(
                name,
                "excluded" if excluded else "pass",
                "Explicit exclusions: "
                + ", ".join(fact.value)
                + (
                    "; event excluded."
                    if excluded
                    else "; none matches the supplied illness event type. "
                    "Event classification is a scenario assumption."
                ),
                fact,
            )

    if rules.employment_linked.value is None:
        add(
            "termination",
            "unknown",
            rules.employment_linked.unknown,
            rules.employment_linked,
        )
    elif (
        rules.employment_linked.value
        or rules.termination.value is not None
        or rules.termination.evidence_ids
    ):
        fact = rules.termination
        if fact.value is None:
            add("termination", "unknown", fact.unknown, fact)
        else:
            end = fact.value.final_employment_date
            if scenario.final_employment_date != end:
                add(
                    "scenario_date",
                    "conflict",
                    f"Scenario final employment {scenario.final_employment_date} "
                    f"differs from PDF {end}; correct the scenario or document. "
                    "PDF not overridden.",
                    fact,
                )
            add(
                "termination",
                "excluded" if event > end else "pass",
                f"Employment protection ends {end} inclusive, "
                "or policy expiry if earlier; "
                f"event {'after' if event > end else 'on/before'} termination. "
                "No conversion or continuity benefit.",
                fact,
            )

    # These affect coverage, even when all supported temporal checks pass.
    missing = [f.detail for f in findings if f.outcome in ("unknown", "conflict")]
    restrictions = []
    for name in (
        "Sum insured",
        "Room rent",
        "Deductible",
        "Co-payment",
        "Pre-existing condition wait",
        "Event sublimits",
        "Room deduction rule",
    ):
        terms = [t for t in report.terms if t.name == name]
        if len(terms) != 1 or terms[0].status != "stated":
            term = terms[0] if len(terms) == 1 else None
            detail = f"{name}: {term.status if term else 'missing/conflicting'}"
            missing.append(detail)
            findings.append(
                Finding(
                    check=name,
                    outcome="unknown",
                    detail=detail,
                    evidence_ids=[e.evidence_id for t in terms for e in t.evidence],
                )
            )
        else:
            term = terms[0]
            restrictions.append(f"{name}: {term.value}")
            if (
                "other events are not specified" in term.value
                or "other procedures are not specified" in term.value
            ):
                missing.append(
                    f"{name}: applicability to unspecified illness "
                    "hospitalization is unknown"
                )

    correction = any(f.outcome == "conflict" for f in findings)
    temporal_findings = [
        f for f in findings if f.check in ("period", "termination", "waiting")
    ]
    temporal = (
        "correction_required"
        if correction
        else "excluded"
        if any(f.outcome == "excluded" for f in temporal_findings)
        else "unknown"
        if any(f.outcome == "unknown" for f in temporal_findings)
        else "passes"
    )
    status = (
        "insufficient_information"
        if correction
        else "excluded"
        if any(f.outcome == "excluded" for f in findings)
        else "insufficient_information"
        if missing
        else "conditional"
    )
    return Assessment(
        assessment_id=f"{scenario.scenario_id}:{report.document.document_id}",
        scenario_id=scenario.scenario_id,
        document=report.document,
        status=status,
        assessed_at=datetime.now(timezone.utc),
        evidence_ids=list(
            dict.fromkeys(e.evidence_id for t in report.terms for e in t.evidence)
        ),
        missing_information=missing,
        restrictions=restrictions,
        next_action="Correct the scenario/document termination-date mismatch and rerun."
        if correction
        else "Obtain missing terms and confirm event eligibility with the insurer; "
        "no claim approval or payout assurance.",
        temporal=temporal,
        findings=findings,
    )


def compare(
    scenario: JobChangeScenario, inspections: list[PolicyInspection]
) -> Comparison:
    rules = [interpret(p) for p in inspections]
    assessments = [assess(p, scenario, r) for p, r in zip(inspections, rules)]
    employer = rules[0]
    known = (
        employer.period.value is not None
        and employer.termination.value is not None
        and employer.employment_linked.value is True
        and employer.members.value is not None
        and scenario.member_ids[0] in employer.members.value
        and scenario.final_employment_date
        == employer.termination.value.final_employment_date
    )
    last = (
        min(employer.period.value.end, employer.termination.value.final_employment_date)
        if known
        else None
    )
    gap = (
        Interval(start=last + DAY, end=scenario.new_employer_coverage_start - DAY)
        if last is not None and last + DAY < scenario.new_employer_coverage_start
        else None
    )
    return Comparison(
        scenario=scenario,
        inspections=inspections,
        assessments=assessments,
        employer_last_day=last,
        gap=gap,
        gap_known=known,
    )


def run(scenario: JobChangeScenario) -> Comparison:
    return compare(
        scenario,
        [inspect_policy(p) for p in ("existing-employer", "existing-personal")],
    )


def parse_input(payload: str) -> JobChangeScenario:
    if len(payload) > 512:
        raise ValueError("Stress-test input exceeds 512 characters. " + USAGE)
    if payload == "preset":
        fields = [
            "member-01",
            "2026-12-31",
            "2027-02-01",
            "2027-01-15",
            "illness_hospitalization",
        ]
    else:
        fields = payload.split(" ")
    if len(fields) != 5 or any(not f for f in fields):
        raise ValueError("Supply all five fields separated by single spaces. " + USAGE)
    member, final, new, event, kind = fields
    if any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) is None for d in (final, new, event)):
        raise ValueError("Use valid calendar dates in YYYY-MM-DD form. " + USAGE)
    try:
        return JobChangeScenario(
            scenario_id="synthetic-job-change"
            if payload == "preset"
            else "explicit-job-change",
            profile_id=None,
            member_ids=[member],
            description="Synthetic dated job-change illustration",
            event_start=event,
            final_employment_date=final,
            new_employer_coverage_start=new,
            event_type=kind,
        )
    except ValueError as exc:
        raise ValueError(f"Invalid scenario: {exc}. {USAGE}") from None


def present_comparison(report: Comparison) -> str:
    from coverwise.money import display_money

    s = report.scenario
    lines = [
        "Synthetic stress test: employer "
        + report.assessments[0].status
        + "; existing personal "
        + report.assessments[1].status
        + ".",
        "Passing temporal checks is not guaranteed coverage; "
        "missing terms remain material.",
        f"Scenario assumptions: member={s.member_ids[0]}; "
        f"final employment={s.final_employment_date}; "
        f"hospitalization={s.event_start}; event={s.event_type}.",
        f"Assumed new employer coverage begins {s.new_employer_coverage_start}: "
        "user-supplied assumption, insurance existence/eligibility unverified.",
    ]
    for label, inspection, assessment in zip(
        ("A and B: existing employer", "B only: existing personal"),
        report.inspections,
        report.assessments,
    ):
        refs = {e.evidence_id: e for t in inspection.terms for e in t.evidence}

        def cite(ids):
            return "; ".join(
                f"p{refs[i].locator.page}/{refs[i].clause_id} {i}" for i in ids
            )

        lines.extend(
            [
                f"{label}: {assessment.status}; temporal={assessment.temporal}",
            ]
        )
        for finding in assessment.findings:
            if finding.outcome == "pass" and finding.check not in (
                "waiting",
                "termination",
            ):
                continue
            lines.append(
                f"- {finding.check}: {finding.outcome}: {finding.detail}"
                + (
                    f" [{cite(finding.evidence_ids)}]"
                    if finding.evidence_ids
                    else " [no evidence supplied]"
                )
            )
        for restriction in assessment.restrictions or []:
            name = restriction.split(": ", 1)[0]
            ids = [
                e.evidence_id
                for t in inspection.terms
                if t.name == name
                for e in t.evidence
            ]
            lines.append(f"- Restriction: {display_money(restriction)} [{cite(ids)}]")
        lines.append("Missing/limits: " + "; ".join(assessment.missing_information))
        lines.append("Next: " + assessment.next_action)
    if not report.gap_known:
        lines.append(
            "Employer-protection gap unknown: resolve missing/conflicting "
            "terms or scenario mismatch."
        )
    elif report.gap:
        lines.append(
            f"Employer protection last day {report.employer_last_day}; "
            f"gap {report.gap.start} through {report.gap.end} inclusive "
            f"({(report.gap.end - report.gap.start).days + 1} days), "
            "before assumed new coverage. "
            "Source: employer period/termination findings above."
        )
    else:
        lines.append(
            f"Employer protection last day {report.employer_last_day}; "
            "no employer-protection gap before assumed new coverage."
        )
    a, b = report.assessments
    lines.extend(
        [
            f"Before A: employer alone = {a.status}. "
            f"After B: same employer = {a.status}; existing personal = {b.status}. "
            "Same member and dates throughout.",
            "Existing personal cover is retained, separately assessed; "
            "employer findings and gap are unchanged.",
            "This does not establish a gap in all protection. Missing terms and "
            "scoped restrictions remain; passing temporal checks is not guaranteed "
            "coverage. Limits are not added or automatically stacked. "
            "No reimbursement calculation.",
            "Complete PDF terms/evidence:\n```text\n/inspect existing-employer\n```\n"
            "```text\n/inspect existing-personal\n```",
        ]
    )
    text = "\n".join(lines)
    if len(text) > MAX_REPLY:
        raise PolicyError("result_too_large")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=USAGE)
    parser.add_argument("inputs", nargs="+", help="preset or the five explicit fields")
    parser.add_argument(
        "--json", action="store_true", help="full report and verbatim evidence"
    )
    args = parser.parse_args()
    try:
        report = run(parse_input(" ".join(args.inputs)))
        output = (
            report.model_dump_json(indent=2)
            if args.json
            else present_comparison(report)
        )
        sys.stdout.buffer.write((output + "\n").encode("utf-8"))
        return 0
    except (ValueError, PolicyError) as exc:
        print(f"Stress test unavailable: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
