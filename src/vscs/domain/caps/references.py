"""Domain models for structured Canonical Asset Profile references."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CanonicalReferenceType(StrEnum):
    """Supported media categories for canonical references."""

    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    MATERIAL = "material"


class CanonicalReferenceRole(StrEnum):
    """Importance of a reference within an asset's canonical definition."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUPPLEMENTARY = "supplementary"


class CanonicalReferenceStatus(StrEnum):
    """Lifecycle status for a canonical reference."""

    IMPORTED = "imported"
    CANDIDATE = "candidate"
    APPROVED = "approved"
    ARCHIVED = "archived"

class CanonicalReferenceCreate(BaseModel):
    """Validated input for attaching a structured reference to a CAP."""

    model_config = ConfigDict(str_strip_whitespace=True)

    cap_id: int = Field(gt=0)
    reference_type: CanonicalReferenceType
    role: CanonicalReferenceRole = CanonicalReferenceRole.SUPPLEMENTARY
    title: str = Field(min_length=1, max_length=200)
    file_path: Path
    description: str = ""
    notes: str = ""
    version: str = Field(default="1.0", min_length=1, max_length=32)
    status: CanonicalReferenceStatus = CanonicalReferenceStatus.IMPORTED

    @field_validator("file_path")
    @classmethod
    def require_file_path(cls, value: Path) -> Path:
        if not str(value).strip():
            raise ValueError("Canonical reference file path is required")
        return value


class CanonicalReferenceUpdate(BaseModel):
    """Validated partial update for an existing canonical reference."""

    model_config = ConfigDict(str_strip_whitespace=True)

    reference_type: CanonicalReferenceType | None = None
    role: CanonicalReferenceRole | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    file_path: Path | None = None
    description: str | None = None
    notes: str | None = None
    version: str | None = Field(default=None, min_length=1, max_length=32)
    status: CanonicalReferenceStatus | None = None


class CanonicalReference(BaseModel):
    """One typed, versioned file that contributes to a CAP's canonical truth."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cap_id: int
    reference_type: CanonicalReferenceType
    role: CanonicalReferenceRole
    title: str
    file_path: Path
    description: str
    notes: str
    version: str
    status: CanonicalReferenceStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
