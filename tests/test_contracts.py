from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from coverwise.contracts import (
    ClauseEvidence,
    CoverageAssessment,
    PolicyDocument,
    StressTestScenario,
    UserProfile,
)


def document(source_type="pdf"):
    return {
        "document_id": "existing-employer",
        "document_version": "1",
        "sha256": "a" * 64,
        "source_type": source_type,
    }


@pytest.mark.parametrize(
    ("source_type", "locator"),
    [
        ("pdf", {"kind": "pdf", "page": 2}),
        (
            "pasted_text",
            {
                "kind": "pasted_text",
                "section": "Benefits",
                "line_start": 3,
                "line_end": 5,
            },
        ),
    ],
)
def test_evidence_round_trip_preserves_document_reference(source_type, locator):
    evidence = ClauseEvidence(
        evidence_id="ev-1",
        document=document(source_type),
        clause_id="EMP-02",
        locator=locator,
        excerpt="Coverage ends on the final employment date.",
    )
    restored = ClauseEvidence.model_validate_json(evidence.model_dump_json())
    assert restored == evidence
    assert restored.document.document_version == "1"
    assert restored.document.sha256 == "a" * 64


@pytest.mark.parametrize("sha256", ["a" * 63, "a" * 65, "g" * 64, ""])
def test_invalid_document_hash(sha256):
    with pytest.raises(ValidationError):
        PolicyDocument(**{**document(), "sha256": sha256})


@pytest.mark.parametrize(
    ("source_type", "locator", "excerpt"),
    [
        ("pdf", {"kind": "pdf", "page": 0}, "term"),
        ("pdf", {"kind": "pdf", "page": -1}, "term"),
        ("pdf", {"kind": "pdf"}, "term"),
        ("pdf", {"kind": "url", "page": 1}, "term"),
        ("pdf", {"kind": "pdf", "page": 1}, "   "),
        ("pasted_text", {"kind": "pdf", "page": 1}, "term"),
        (
            "pasted_text",
            {"kind": "pasted_text", "section": "", "line_start": 1, "line_end": 2},
            "term",
        ),
        (
            "pasted_text",
            {"kind": "pasted_text", "section": "Terms", "line_start": 3, "line_end": 2},
            "term",
        ),
    ],
)
def test_invalid_evidence(source_type, locator, excerpt):
    with pytest.raises(ValidationError):
        ClauseEvidence(
            evidence_id="ev-1",
            document=document(source_type),
            locator=locator,
            excerpt=excerpt,
        )


def test_unknowns_survive_serialization():
    profile = UserProfile(profile_id="p-1", members=[{"member_id": "m-1"}])
    restored = UserProfile.model_validate_json(profile.model_dump_json())
    assert restored.annual_budget_inr_paise is None
    assert restored.members[0].date_of_birth is None
    assessment = CoverageAssessment(
        assessment_id="a-1",
        scenario_id="s-1",
        document=document(),
        status="insufficient_information",
        assessed_at=datetime(2026, 10, 23, tzinfo=UTC),
        evidence_ids=[],
        missing_information=["Waiting-period term not supplied"],
        restrictions=None,
        next_action="Request the missing policy schedule",
    )
    restored_assessment = CoverageAssessment.model_validate_json(
        assessment.model_dump_json()
    )
    assert restored_assessment.restrictions is None
    assert restored_assessment.missing_information == assessment.missing_information
    with pytest.raises(ValidationError):
        CoverageAssessment.model_validate(
            {**assessment.model_dump(), "assessed_at": datetime(2026, 10, 23)}
        )


def test_duplicate_members_rejected():
    with pytest.raises(ValidationError, match="unique"):
        UserProfile(
            profile_id="p-1", members=[{"member_id": "m-1"}, {"member_id": "m-1"}]
        )


@pytest.mark.parametrize("budget", [-1, 1.5, True])
def test_budget_requires_nonnegative_integer_paise(budget):
    with pytest.raises(ValidationError):
        UserProfile(
            profile_id="p-1",
            members=[{"member_id": "m-1"}],
            annual_budget_inr_paise=budget,
        )


def test_scenario_interval_and_member_references():
    data = {
        "scenario_id": "job-change",
        "profile_id": "p-1",
        "member_ids": ["m-1"],
        "description": "Employment transition",
        "event_start": "2027-01-01",
        "event_end": "2027-01-31",
    }
    scenario = StressTestScenario(**data)
    assert scenario.member_ids == ["m-1"]
    assert scenario.event_end > scenario.event_start
    assert StressTestScenario(**{**data, "event_end": "2027-01-01"})
    assert StressTestScenario(**{**data, "event_end": None}).event_end is None
    with pytest.raises(ValidationError, match="event_end"):
        StressTestScenario(**{**data, "event_end": "2026-12-31"})
    with pytest.raises(ValidationError, match="unique"):
        StressTestScenario(**{**data, "member_ids": ["m-1", "m-1"]})
