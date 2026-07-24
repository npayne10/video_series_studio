"""Domain models for Canonical Asset Profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CAPStatus(StrEnum):
    """Review state for a Canonical Asset Profile."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class CAPCreate(BaseModel):
    """Validated input for creating a Canonical Asset Profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    version: str = Field(default="1.0", min_length=1, max_length=32)
    status: CAPStatus = CAPStatus.DRAFT
    canonical_description: str = Field(min_length=1)
    visual_identity: str = ""
    production_notes: str = ""
    reference_paths: tuple[Path, ...] = ()

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        return value.upper().replace(" ", "-")

    @field_validator("reference_paths")
    @classmethod
    def normalize_reference_paths(cls, value: tuple[Path, ...]) -> tuple[Path, ...]:
        return tuple(dict.fromkeys(value))


class CAPUpdate(BaseModel):
    """Validated partial update for an existing CAP."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    version: str | None = Field(default=None, min_length=1, max_length=32)
    status: CAPStatus | None = None
    canonical_description: str | None = Field(default=None, min_length=1)
    visual_identity: str | None = None
    production_notes: str | None = None
    reference_paths: tuple[Path, ...] | None = None

    @field_validator("reference_paths")
    @classmethod
    def normalize_reference_paths(cls, value: tuple[Path, ...] | None) -> tuple[Path, ...] | None:
        if value is None:
            return None
        return tuple(dict.fromkeys(value))


class CanonicalAssetProfile(BaseModel):
    """Canonical definition linked to a registered production asset."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: str
    title: str
    version: str
    status: CAPStatus
    canonical_description: str
    visual_identity: str
    production_notes: str
    reference_paths: tuple[Path, ...]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
