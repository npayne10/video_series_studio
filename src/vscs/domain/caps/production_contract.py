"""Canonical production-contract domain models for Phase 18.2.11.2.2.

These models define the stable, scene-independent contract that CAP publishes to
future production systems. They intentionally coexist with the legacy CAP
persistence models until the dedicated migration phases are implemented.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vscs.domain.assets.models import AssetCategory


class CanonicalConstraintKind(StrEnum):
    """Strength/direction of one machine-consumable canonical constraint."""

    REQUIRED = "required"
    FORBIDDEN = "forbidden"
    PREFERRED = "preferred"
    OPTIONAL = "optional"


class CanonicalReferenceFamily(StrEnum):
    """Production grouping for canonical references."""

    MASTER = "master"
    PRODUCTION_VIEW = "production_view"
    DETAIL = "detail"
    INTERIOR = "interior"
    VARIANT = "variant"


class CanonicalReferenceView(StrEnum):
    """Viewpoint/production purpose of a canonical reference."""

    MASTER = "master"
    PRIMARY_THREE_QUARTER = "primary_three_quarter"
    FRONT = "front"
    REAR = "rear"
    LEFT = "left"
    RIGHT = "right"
    PORT = "port"
    STARBOARD = "starboard"
    TOP = "top"
    BOTTOM = "bottom"
    PROFILE_LEFT = "profile_left"
    PROFILE_RIGHT = "profile_right"
    FULL_BODY = "full_body"
    FACE = "face"
    AERIAL = "aerial"
    ORBIT = "orbit"
    SURFACE = "surface"
    INTERIOR = "interior"
    DETAIL = "detail"
    VARIANT = "variant"


class CanonicalReferenceOrigin(StrEnum):
    """Authoring/provenance source for a canonical reference."""

    CHATGPT_MASTER = "chatgpt_master"
    VSCS_DERIVED = "vscs_derived"
    IMPORTED_LEGACY = "imported_legacy"
    EXTERNAL = "external"


class CanonicalReferenceLifecycle(StrEnum):
    """Production-contract lifecycle independent of legacy persistence status."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    LOCKED = "locked"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class CAPReadinessState(StrEnum):
    """State of one independent CAP readiness gate."""

    INCOMPLETE = "incomplete"
    READY = "ready"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class CanonicalIdentity(BaseModel):
    """Stable identity published by CAP; never scene-specific."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, max_length=64)
    canonical_name: str = Field(min_length=1, max_length=200)
    category: AssetCategory
    aliases: tuple[str, ...] = ()
    version: str = Field(default="1.0", min_length=1, max_length=32)

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return value.upper().replace(" ", "-")

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(alias.strip() for alias in value if alias.strip()))


class CanonicalFact(BaseModel):
    """One structured fact that downstream consumers may use without parsing prose."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    key: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)
    unit: str | None = Field(default=None, max_length=32)
    source: str = ""


class FunctionalCapability(BaseModel):
    """Scene-independent capability or behaviour of an asset."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    capability: str = Field(min_length=1, max_length=160)
    description: str = ""


class CanonicalConstraint(BaseModel):
    """Explicit production boundary that downstream systems must respect."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    kind: CanonicalConstraintKind
    rule: str = Field(min_length=1)
    rationale: str = ""


class ProductionReference(BaseModel):
    """Reference metadata published through the production contract.

    MASTER is the one authoritative ChatGPT-authored visual reference. Derived
    references must point to that master (or another explicit parent) and are
    never canonical authorities by themselves.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    reference_id: str = Field(min_length=1, max_length=96)
    family: CanonicalReferenceFamily
    view: CanonicalReferenceView
    origin: CanonicalReferenceOrigin
    lifecycle: CanonicalReferenceLifecycle = CanonicalReferenceLifecycle.CANDIDATE
    version: str = Field(default="1.0", min_length=1, max_length=32)
    parent_reference_id: str | None = Field(default=None, max_length=96)
    file_path: str = Field(min_length=1)
    generator: str | None = Field(default=None, max_length=160)
    approved_by: str | None = Field(default=None, max_length=200)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_master_and_derivation(self) -> ProductionReference:
        is_master = self.family is CanonicalReferenceFamily.MASTER
        if is_master:
            if self.view is not CanonicalReferenceView.MASTER:
                raise ValueError("MASTER family references must use the MASTER view")
            if self.origin is not CanonicalReferenceOrigin.CHATGPT_MASTER:
                raise ValueError("MASTER references must originate from ChatGPT")
            if self.parent_reference_id is not None:
                raise ValueError("MASTER references cannot have a parent reference")
        elif self.origin is CanonicalReferenceOrigin.VSCS_DERIVED:
            if not self.parent_reference_id:
                raise ValueError("VSCS-derived references require a parent reference")
            if self.view is CanonicalReferenceView.MASTER:
                raise ValueError("Derived references cannot use the MASTER view")
        return self


class CAPReadiness(BaseModel):
    """Independent readiness gates published by CAP."""

    model_config = ConfigDict(frozen=True)

    identity: CAPReadinessState = CAPReadinessState.INCOMPLETE
    references: CAPReadinessState = CAPReadinessState.INCOMPLETE
    generation: CAPReadinessState = CAPReadinessState.INCOMPLETE
    production: CAPReadinessState = CAPReadinessState.INCOMPLETE
    canonical_locked: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


class CanonicalProductionContract(BaseModel):
    """Authoritative CAP-owned, scene-independent production contract."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    identity: CanonicalIdentity
    canonical_description: str = Field(min_length=1)
    facts: tuple[CanonicalFact, ...] = ()
    visual_identity: str = ""
    functional_identity: tuple[FunctionalCapability, ...] = ()
    constraints: tuple[CanonicalConstraint, ...] = ()
    production_guidance: str = ""
    references: tuple[ProductionReference, ...]
    readiness: CAPReadiness = Field(default_factory=CAPReadiness)

    @model_validator(mode="after")
    def enforce_reference_contract(self) -> CanonicalProductionContract:
        reference_ids = [reference.reference_id for reference in self.references]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("Production reference IDs must be unique within a CAP")

        masters = [
            reference
            for reference in self.references
            if reference.family is CanonicalReferenceFamily.MASTER
        ]
        if len(masters) != 1:
            raise ValueError("A Canonical Production Contract requires exactly one MASTER reference")

        master_id = masters[0].reference_id
        known_ids = set(reference_ids)
        for reference in self.references:
            if reference.parent_reference_id and reference.parent_reference_id not in known_ids:
                raise ValueError(
                    f"Parent reference {reference.parent_reference_id!r} is not part of this CAP"
                )
            if reference.origin is CanonicalReferenceOrigin.VSCS_DERIVED:
                if reference.parent_reference_id != master_id:
                    raise ValueError(
                        "Phase 18.2.11 requires VSCS-derived production views to trace directly "
                        "to the current MASTER reference"
                    )
        return self


class ProductionAssetProjection(BaseModel):
    """Read-only shape intended for downstream production consumers.

    Production Planning and later systems consume this projection rather than
    repository/UI-specific CAP persistence models.
    """

    model_config = ConfigDict(frozen=True)

    identity: CanonicalIdentity
    facts: tuple[CanonicalFact, ...]
    visual_identity: str
    functional_identity: tuple[FunctionalCapability, ...]
    constraints: tuple[CanonicalConstraint, ...]
    production_guidance: str
    references: tuple[ProductionReference, ...]
    readiness: CAPReadiness

    @classmethod
    def from_contract(cls, contract: CanonicalProductionContract) -> ProductionAssetProjection:
        return cls(
            identity=contract.identity,
            facts=contract.facts,
            visual_identity=contract.visual_identity,
            functional_identity=contract.functional_identity,
            constraints=contract.constraints,
            production_guidance=contract.production_guidance,
            references=tuple(
                reference
                for reference in contract.references
                if reference.lifecycle
                in {
                    CanonicalReferenceLifecycle.APPROVED,
                    CanonicalReferenceLifecycle.LOCKED,
                }
            ),
            readiness=contract.readiness,
        )
