"""Transport-independent data contracts, with no insurance decision logic."""

from datetime import date
from typing import Annotated, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]
Paise = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CoveredMember(Contract):
    member_id: Nonempty
    display_name: Nonempty | None = None
    date_of_birth: date | None = None
    relationship: Nonempty | None = None


class UserProfile(Contract):
    profile_id: Nonempty
    members: list[CoveredMember] = Field(min_length=1)
    annual_budget_inr_paise: Paise | None = None

    @model_validator(mode="after")
    def unique_members(self) -> Self:
        ids = [member.member_id for member in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("member identifiers must be unique within a profile")
        return self


class PolicyDocument(Contract):
    document_id: Nonempty
    document_version: Nonempty
    sha256: Sha256
    source_type: Literal["pdf", "pasted_text"]
    title: Nonempty | None = None
    page_count: PositiveInt | None = None


class PdfLocator(Contract):
    kind: Literal["pdf"] = "pdf"
    page: PositiveInt


class TextLocator(Contract):
    kind: Literal["pasted_text"] = "pasted_text"
    section: Nonempty
    line_start: PositiveInt
    line_end: PositiveInt

    @model_validator(mode="after")
    def ordered_lines(self) -> Self:
        if self.line_end < self.line_start:
            raise ValueError("line_end must be on or after line_start")
        return self


class ClauseEvidence(Contract):
    evidence_id: Nonempty
    document: PolicyDocument
    clause_id: Nonempty | None = None
    locator: Annotated[PdfLocator | TextLocator, Field(discriminator="kind")]
    excerpt: Nonempty

    @model_validator(mode="after")
    def matching_source(self) -> Self:
        if self.locator.kind != self.document.source_type:
            raise ValueError("locator kind must match document source_type")
        return self


class ExtractedTerm(Contract):
    name: Nonempty
    status: Literal["stated", "not_stated", "ambiguous", "conflict"]
    value: Nonempty | None
    evidence: list[ClauseEvidence] = Field(max_length=4)

    @model_validator(mode="after")
    def consistent_status(self) -> Self:
        if self.status == "not_stated":
            if self.value is not None or self.evidence:
                raise ValueError("not_stated must have no value or evidence")
        elif not self.evidence:
            raise ValueError("extracted terms require evidence")
        if (self.status == "stated") != (self.value is not None):
            raise ValueError("only unambiguous stated terms have a value")
        return self


class PolicyInspection(Contract):
    document: PolicyDocument
    terms: list[ExtractedTerm] = Field(max_length=17)
    limitations: list[Nonempty]

    @model_validator(mode="after")
    def consistent_document(self) -> Self:
        if self.document.source_type != "pdf" or self.document.page_count is None:
            raise ValueError(
                "policy inspection requires a PDF document with page count"
            )
        for term in self.terms:
            for evidence in term.evidence:
                if evidence.document != self.document:
                    raise ValueError("evidence must reference the inspected document")
                if evidence.locator.page > self.document.page_count:
                    raise ValueError("evidence page exceeds the document page count")
        return self


class StressTestScenario(Contract):
    scenario_id: Nonempty
    profile_id: Nonempty
    member_ids: list[Nonempty] = Field(min_length=1)
    description: Nonempty
    event_start: date
    event_end: date | None = None

    @model_validator(mode="after")
    def valid_interval_and_members(self) -> Self:
        if self.event_end is not None and self.event_end < self.event_start:
            raise ValueError("event_end must be on or after event_start")
        if len(self.member_ids) != len(set(self.member_ids)):
            raise ValueError("scenario member identifiers must be unique")
        return self


class CoverageAssessment(Contract):
    assessment_id: Nonempty
    scenario_id: Nonempty
    document: PolicyDocument
    status: Literal["covered", "excluded", "conditional", "insufficient_information"]
    assessed_at: AwareDatetime
    evidence_ids: list[Nonempty]
    missing_information: list[Nonempty]
    restrictions: list[Nonempty] | None
    next_action: Nonempty | None


class JobChangeScenario(StressTestScenario):
    """Single-member dated slice; legacy scenario contracts remain compatible."""

    profile_id: Nonempty | None
    member_ids: list[
        Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]{1,64}$")]
    ] = Field(min_length=1, max_length=1)
    final_employment_date: date
    new_employer_coverage_start: date
    event_type: Literal["illness_hospitalization"]

    @model_validator(mode="after")
    def job_change_order(self) -> Self:
        if self.new_employer_coverage_start <= self.final_employment_date:
            raise ValueError(
                "new employer coverage start must be after final employment date"
            )
        if self.event_end is not None and self.event_end != self.event_start:
            raise ValueError("this slice supports a single hospitalization date")
        if not date(1900, 1, 1) <= min(self.event_start, self.final_employment_date):
            raise ValueError("scenario dates must be between 1900 and 2100")
        if max(self.event_start, self.new_employer_coverage_start) > date(2100, 12, 31):
            raise ValueError("scenario dates must be between 1900 and 2100")
        return self
