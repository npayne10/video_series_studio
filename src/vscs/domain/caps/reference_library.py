"""Reference library and lifecycle domain models for Phase 18.2.11.2.3."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vscs.domain.caps.production_contract import (
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
)


class ReferenceLifecycleAction(StrEnum):
    """Auditable actions that may change reference governance state."""

    REGISTER = "register"
    MARK_CANDIDATE = "mark_candidate"
    APPROVE = "approve"
    LOCK = "lock"
    REJECT = "reject"
    RETURN_TO_CANDIDATE = "return_to_candidate"
    ARCHIVE = "archive"
    UPDATE_METADATA = "update_metadata"


class ReferenceLifecycleEvent(BaseModel):
    """One immutable reference-library audit event."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    action: ReferenceLifecycleAction
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    actor: str = ""
    note: str = ""
    from_lifecycle: CanonicalReferenceLifecycle | None = None
    to_lifecycle: CanonicalReferenceLifecycle | None = None


class ReferenceLibraryEntry(BaseModel):
    """Production metadata overlay for one structured CanonicalReference record."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    reference_record_id: int = Field(gt=0)
    asset_id: str = Field(min_length=1, max_length=64)
    reference_id: str = Field(min_length=1, max_length=96)
    family: CanonicalReferenceFamily
    view: CanonicalReferenceView
    origin: CanonicalReferenceOrigin
    lifecycle: CanonicalReferenceLifecycle = CanonicalReferenceLifecycle.CANDIDATE
    parent_reference_id: str | None = Field(default=None, max_length=96)
    generator: str | None = Field(default=None, max_length=160)
    source_master_version: str | None = Field(default=None, max_length=32)
    registered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    approved_by: str | None = Field(default=None, max_length=200)
    approved_at: datetime | None = None
    history: tuple[ReferenceLifecycleEvent, ...] = ()

    @model_validator(mode="after")
    def validate_reference_semantics(self) -> ReferenceLibraryEntry:
        is_master = self.family is CanonicalReferenceFamily.MASTER
        if is_master:
            if self.view is not CanonicalReferenceView.MASTER:
                raise ValueError("MASTER library entries must use the MASTER view")
            if self.origin is not CanonicalReferenceOrigin.CHATGPT_MASTER:
                raise ValueError("MASTER library entries must originate from ChatGPT")
            if self.parent_reference_id is not None:
                raise ValueError("MASTER library entries cannot have a parent reference")
        elif self.origin is CanonicalReferenceOrigin.VSCS_DERIVED:
            if self.view is CanonicalReferenceView.MASTER:
                raise ValueError("Derived reference entries cannot use the MASTER view")
            if not self.parent_reference_id:
                raise ValueError("VSCS-derived references require the MASTER parent reference ID")
        return self


class ReferenceLibrarySnapshot(BaseModel):
    """Versioned project-local reference-library state."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    entries: tuple[ReferenceLibraryEntry, ...] = ()

    @model_validator(mode="after")
    def validate_uniqueness(self) -> ReferenceLibrarySnapshot:
        record_ids = [entry.reference_record_id for entry in self.entries]
        reference_ids = [entry.reference_id for entry in self.entries]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Reference-library record IDs must be unique")
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("Reference-library reference IDs must be unique")
        return self
