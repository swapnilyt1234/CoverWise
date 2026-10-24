"""Typed sandbox workflow contracts; no real payment or identity credentials."""

from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from coverwise.catalogue import Product
from coverwise.contracts import Contract, Paise, PolicyInspection, Sha256
from coverwise.recommend import RecommendationInput

Reference = Annotated[str, StringConstraints(pattern=r"^(q|a|op)-[0-9a-f]{32}$")]
Challenge = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{24}$")]
Action = Literal["quote", "apply", "review", "approve", "status", "details", "cancel"]
State = Literal[
    "quote_active",
    "quote_expired",
    "review",
    "approved",
    "payment_pending",
    "completed",
    "failed",
    "cancelled",
    "needs_review",
    "operation_pending",
    "rejected",
]


class ApplicationFields(Contract):
    confirm_demo: Annotated[bool, Field(strict=True)]
    payment_outcome: Literal["success", "failure", "unknown"]

    @model_validator(mode="after")
    def confirmed(self):
        if not self.confirm_demo:
            raise ValueError("confirm the synthetic details explicitly")
        return self


class SandboxCommand(Contract):
    action: Action
    product_id: (
        Annotated[str, StringConstraints(min_length=1, max_length=64)] | None
    ) = None
    inputs: RecommendationInput | None = None
    reference: Reference | None = None
    application: ApplicationFields | None = None
    replacement_quote: Reference | None = None
    revision: Annotated[int, Field(strict=True, ge=1)] | None = None
    challenge: Challenge | None = None

    @model_validator(mode="after")
    def fields_for_action(self):
        present = {
            k
            for k in (
                "product_id",
                "inputs",
                "reference",
                "application",
                "replacement_quote",
                "revision",
                "challenge",
            )
            if getattr(self, k) is not None
        }
        expected = {
            "quote": {"product_id", "inputs"},
            "apply": {"reference", "application"},
            "review": {"reference"},
            "approve": {"reference", "revision", "challenge"},
            "status": {"reference"},
            "details": {"reference"},
            "cancel": {"reference"},
        }[self.action]
        if self.action == "review" and self.application is not None:
            expected = {"reference", "application", "replacement_quote"}
            if self.replacement_quote is None or not self.replacement_quote.startswith(
                "q-"
            ):
                raise ValueError("revision requires a replacement quote ID")
        if present != expected:
            raise ValueError(
                "supply exactly the fields required by the workflow action"
            )
        if self.action == "apply" and not self.reference.startswith("q-"):
            raise ValueError("apply requires a quote reference")
        if self.action in (
            "review",
            "approve",
            "cancel",
        ) and not self.reference.startswith("a-"):
            raise ValueError("action requires an application reference")
        return self


class QuoteTerms(Contract):
    provider_version: str
    pricing_rule_version: str
    catalogue_version: str
    catalogue_sha256: Sha256
    product: Product
    inputs: RecommendationInput
    premium_paise: Paise
    currency: Literal["INR"] = "INR"
    premium_basis: str
    cover_start: date
    cover_end: date
    wait_start: date
    wait_end: date
    first_post_wait_day: date
    immediate_status: str
    restrictions: list[str]
    required_disclosures: list[str]
    evidence: PolicyInspection


class SandboxQuote(QuoteTerms):
    quote_id: Reference
    created_at: AwareDatetime
    expires_at: AwareDatetime


class ApplicationView(Contract):
    application_id: Reference
    revision: int = Field(ge=1)
    state: State
    quote: SandboxQuote
    fields: ApplicationFields
    review_digest: Sha256
    challenge_expires_at: AwareDatetime


class PaymentView(Contract):
    payment_id: str
    state: Literal["succeeded", "failed", "unknown"]
    amount_paise: Paise
    currency: Literal["INR"]
    confirmation: str | None
    transaction_reference: str


class SandboxReply(Contract):
    sandbox: Literal[True] = True
    notice: Literal["Sandbox/demo — no real policy issued. No real money moved."] = (
        "Sandbox/demo — no real policy issued. No real money moved."
    )
    operation_id: Reference
    action: Action
    scope: Sha256
    state: State
    reference: Reference
    quote: SandboxQuote | None = None
    application: ApplicationView | None = None
    payment: PaymentView | None = None
    challenge: Challenge | None = None
    error_code: str | None = None
    next_commands: list[str] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def consistent(self):
        if self.state in ("quote_active", "quote_expired") and self.quote is None:
            raise ValueError("quote state requires a quote")
        if (
            self.state in ("review", "approved", "cancelled", "needs_review")
            and self.application is None
        ):
            raise ValueError("application state requires an application")
        if self.quote and self.reference != self.quote.quote_id:
            raise ValueError("quote reference mismatch")
        if self.application:
            if (
                self.reference != self.application.application_id
                or self.state != self.application.state
            ):
                raise ValueError("application reference/state mismatch")
        if self.state in ("completed", "failed", "payment_pending"):
            expected = {
                "completed": "succeeded",
                "failed": "failed",
                "payment_pending": "unknown",
            }[self.state]
            if (
                self.application is None
                or self.payment is None
                or self.payment.state != expected
            ):
                raise ValueError("payment state mismatch")
            if (self.state == "completed") != (self.payment.confirmation is not None):
                raise ValueError("only completed payments have confirmations")
            if self.payment.amount_paise != self.application.quote.premium_paise:
                raise ValueError("payment amount differs from reviewed quote")
        if self.challenge and (self.application is None or self.state != "review"):
            raise ValueError("challenges are returned only for an explicit review")
        return self
