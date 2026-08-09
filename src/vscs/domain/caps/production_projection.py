"""Stable downstream production projection contract.

Production Planning and later systems consume this immutable projection rather than
CAP persistence or presentation models.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vscs.domain.caps.production_contract import (
    CanonicalConstraint,
    CanonicalFact,
    CanonicalIdentity,
    FunctionalCapability,
    ProductionReference,
)
from vscs.domain.caps.readiness import ReadinessReport


class ProductionProjection(BaseModel):
    """Immutable, versioned canonical asset projection for downstream production."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    schema_version: str = Field(default="2.0", min_length=1, max_length=32)
    identity: CanonicalIdentity
    canonical_description: str = Field(min_length=1)
    facts: tuple[CanonicalFact, ...] = ()
    visual_identity: str = ""
    functional_identity: tuple[FunctionalCapability, ...] = ()
    constraints: tuple[CanonicalConstraint, ...] = ()
    production_guidance: str = ""
    semantic_tags: tuple[str, ...] = ()
    production_classifications: tuple[str, ...] = ()
    behaviour_references: tuple[str, ...] = ()
    production_metadata: dict[str, str] = Field(default_factory=dict)
    structured_schema_version: int = Field(default=1, ge=1)
    references: tuple[ProductionReference, ...] = ()
    readiness: ReadinessReport
    source_cap_version: str = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_identity_alignment(self) -> ProductionProjection:
        if self.readiness.asset_id != self.identity.asset_id:
            raise ValueError("Projection identity and readiness asset IDs must match")
        reference_ids = [reference.reference_id for reference in self.references]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("Production projection reference IDs must be unique")
        return self

    @property
    def production_ready(self) -> bool:
        """Return the authoritative production gate from the readiness report."""
        return self.readiness.production_ready

    @property
    def generation_ready(self) -> bool:
        return self.readiness.generation_ready

    def checksum(self) -> str:
        """Return a deterministic content fingerprint for cache/invalidation consumers."""
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


ProductionProjectionResult = ProductionProjection
