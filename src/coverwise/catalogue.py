"""Provider-owned, versioned synthetic list catalogue; no quote generation."""

import hashlib
from datetime import datetime, timezone

from pydantic import AwareDatetime, Field, model_validator

from coverwise.contracts import Contract, Nonempty, Paise, Sha256
from coverwise.policies import ASSET_ROOT, CANDIDATES, PolicyError

CATALOGUE_PATH = ASSET_ROOT / "fixtures" / "catalogue.v1.json"
PREMIUM_BASIS = (
    "Indicative annual family list premium for up to 2 eligible adults; "
    "not a quote; no additional taxes or fees in this demo."
)


class Eligibility(Contract):
    min_age: int = Field(strict=True, ge=0, le=100)
    max_age: int = Field(strict=True, ge=0, le=100)
    max_members: int = Field(strict=True, ge=1, le=2)
    relationships: list[str]
    no_preexisting_required: bool

    @model_validator(mode="after")
    def supported(self):
        if self.min_age > self.max_age or self.relationships != ["self", "spouse"]:
            raise ValueError("unsupported eligibility range or relationships")
        if not self.no_preexisting_required:
            raise ValueError("this catalogue requires explicit absence disclosures")
        return self


class DocumentRef(Contract):
    document_id: Nonempty
    document_version: Nonempty
    sha256: Sha256


class Product(Contract):
    product_id: Nonempty
    name: Nonempty
    insurer: Nonempty
    document: DocumentRef
    annual_premium_paise: Paise
    premium_basis: str
    family_limit_paise: Paise
    uncapped_private_room: bool | None
    policy_days: int = Field(strict=True, ge=1, le=366)
    initial_wait_days: int = Field(strict=True, ge=1, le=365)
    eligibility: Eligibility

    @model_validator(mode="after")
    def registered(self):
        spec = CANDIDATES.get(self.document.document_id)
        if spec is None or self.product_id != self.document.document_id:
            raise ValueError("catalogue document is not allowlisted")
        if self.document.document_version != spec.version:
            raise ValueError("unsupported document version")
        if self.premium_basis != PREMIUM_BASIS or not self.insurer.startswith(
            "Fictional "
        ):
            raise ValueError(
                "catalogue must label fictional insurer and indicative basis"
            )
        if self.initial_wait_days >= self.policy_days:
            raise ValueError("wait must finish before the proposed term ends")
        return self


class Catalogue(Contract):
    catalogue_version: Nonempty
    synthetic: bool
    published_at: AwareDatetime
    products: list[Product] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def unique(self):
        ids = [p.product_id for p in self.products]
        if not self.synthetic or len(ids) != len(set(ids)):
            raise ValueError("synthetic catalogue requires unique product IDs")
        return self


class CatalogueSnapshot(Contract):
    catalogue: Catalogue
    source_sha256: Sha256
    retrieved_at: AwareDatetime


def load_catalogue() -> CatalogueSnapshot:
    try:
        with CATALOGUE_PATH.open("rb") as stream:
            data = stream.read(32769)
        if len(data) > 32768:
            raise ValueError("oversized catalogue")
        catalogue = Catalogue.model_validate_json(data)
    except (OSError, ValueError):
        raise PolicyError("catalogue_unavailable") from None
    return CatalogueSnapshot(
        catalogue=catalogue,
        source_sha256=hashlib.sha256(data).hexdigest(),
        retrieved_at=datetime.now(timezone.utc),
    )
