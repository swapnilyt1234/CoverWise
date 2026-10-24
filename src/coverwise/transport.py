"""SDK transport models; deliberately separate from domain contracts."""

import hashlib
from typing import Literal
from uuid import UUID

from pydantic.v1 import Field, root_validator
from uagents import Model

MAX_TEXT = 4096


class DiagnosticRequest(Model):
    request_id: UUID
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class DiagnosticResult(Model):
    request_id: UUID
    status: Literal["success", "error"]
    sha256: str | None = Field(default=None, regex=r"^[0-9a-f]{64}$")
    character_count: int | None = Field(default=None, ge=0, le=MAX_TEXT)
    error: Literal["invalid_text", "timeout", "delivery_failed", "busy"] | None = None

    @root_validator(skip_on_failure=True)
    def coherent_result(cls, values):
        success = values["status"] == "success"
        complete = (
            values["sha256"] is not None and values["character_count"] is not None
        )
        empty = values["sha256"] is None and values["character_count"] is None
        if (success and (not complete or values["error"] is not None)) or (
            not success and (not empty or values["error"] is None)
        ):
            raise ValueError(
                "success requires measurements; error must not contain them"
            )
        return values


def diagnose(request: DiagnosticRequest) -> DiagnosticResult:
    try:
        encoded = request.text.encode("utf-8")
    except UnicodeEncodeError:
        return DiagnosticResult(
            request_id=request.request_id, status="error", error="invalid_text"
        )
    return DiagnosticResult(
        request_id=request.request_id,
        status="success",
        sha256=hashlib.sha256(encoded).hexdigest(),
        character_count=len(request.text),
    )


class PolicyInspectionRequest(Model):
    request_id: UUID
    policy_id: str = Field(min_length=1, max_length=64)


class StressTestRequest(Model):
    request_id: UUID
    scenario_json: str = Field(min_length=1, max_length=2048)


class PolicyInspectionResult(Model):
    request_id: UUID
    policy_id: str = Field(min_length=1, max_length=64)
    status: Literal["success", "error"]
    report_json: str | None = Field(default=None, max_length=65536)
    error: str | None = Field(default=None, max_length=40)

    @root_validator(skip_on_failure=True)
    def coherent_result(cls, values):
        if values["status"] == "success":
            if values["report_json"] is None or values["error"] is not None:
                raise ValueError("success requires a report and no error")
        elif values["report_json"] is not None or values["error"] is None:
            raise ValueError("error requires a code and no findings")
        return values


class StressTestResult(Model):
    request_id: UUID
    status: Literal["success", "error"]
    report_json: str | None = Field(default=None, max_length=131072)
    error: str | None = Field(default=None, max_length=40)

    @root_validator(skip_on_failure=True)
    def coherent_result(cls, values):
        if values["status"] == "success":
            if values["report_json"] is None or values["error"] is not None:
                raise ValueError("success requires a report and no error")
        elif values["report_json"] is not None or values["error"] is None:
            raise ValueError("error requires a code and no findings")
        return values


class CatalogueRequest(Model):
    request_id: UUID
    test_timeout: bool = False


class CandidateAssessmentRequest(Model):
    request_id: UUID
    input_json: str = Field(min_length=1, max_length=4096)
    catalogue_json: str = Field(min_length=1, max_length=32768)


class ToolResult(Model):
    request_id: UUID
    status: Literal["success", "error"]
    payload_json: str | None = Field(default=None, max_length=262144)
    error: str | None = Field(default=None, max_length=40)

    @root_validator(skip_on_failure=True)
    def coherent(cls, values):
        success = values["status"] == "success"
        if success != (values["payload_json"] is not None) or success == (
            values["error"] is not None
        ):
            raise ValueError("success requires payload only; error requires code only")
        return values


class CatalogueResult(ToolResult):
    pass


class CandidateAssessmentResult(ToolResult):
    pass


class SandboxRequest(Model):
    request_id: UUID
    observed_sender: str = Field(min_length=1, max_length=128)
    observed_session: UUID
    command_json: str = Field(min_length=1, max_length=8192)


class SandboxResult(ToolResult):
    pass
