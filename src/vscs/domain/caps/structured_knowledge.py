"""Persisted structured production knowledge for Canonical Asset Profiles."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vscs.domain.caps.production_contract import (
    CanonicalConstraint,
    CanonicalFact,
    FunctionalCapability,
)


class KnowledgeAuthority(StrEnum):
    """Review authority attached to one structured production-knowledge item."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    CANONICAL = "canonical"


class PersistedCanonicalFact(CanonicalFact):
    """Canonical fact with review authority and optional extraction confidence."""

    authority: KnowledgeAuthority = KnowledgeAuthority.APPROVED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PersistedFunctionalCapability(FunctionalCapability):
    """Functional capability persisted with provenance and review authority."""

    source: str = ""
    authority: KnowledgeAuthority = KnowledgeAuthority.APPROVED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class PersistedCanonicalConstraint(CanonicalConstraint):
    """Canonical constraint persisted with provenance and review authority."""

    source: str = ""
    authority: KnowledgeAuthority = KnowledgeAuthority.APPROVED
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class StructuredCAPKnowledge(BaseModel):
    """Versioned machine-readable production knowledge owned by one CAP."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    schema_version: int = Field(default=1, ge=1)
    facts: tuple[PersistedCanonicalFact, ...] = ()
    functional_identity: tuple[PersistedFunctionalCapability, ...] = ()
    constraints: tuple[PersistedCanonicalConstraint, ...] = ()
    semantic_tags: tuple[str, ...] = ()
    production_classifications: tuple[str, ...] = ()
    behaviour_references: tuple[str, ...] = ()
    production_metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator("semantic_tags", "production_classifications", "behaviour_references")
    @classmethod
    def normalize_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.strip() for item in value if item.strip()))

    @field_validator("production_metadata")
    @classmethod
    def normalize_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            str(key).strip(): str(item).strip()
            for key, item in value.items()
            if str(key).strip() and str(item).strip()
        }


def is_production_authority(authority: KnowledgeAuthority) -> bool:
    """Return whether structured knowledge may satisfy production contracts."""

    return authority in {KnowledgeAuthority.APPROVED, KnowledgeAuthority.CANONICAL}
