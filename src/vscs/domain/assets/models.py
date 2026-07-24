"""Domain models for production assets."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssetCategory(StrEnum):
    """Supported production asset categories."""

    CHARACTER = "character"
    LOCATION = "location"
    PROP = "prop"
    SHIP = "ship"
    VEHICLE = "vehicle"
    ENVIRONMENT = "environment"
    PLANET = "planet"
    UNIFORM = "uniform"
    TECHNOLOGY = "technology"
    EFFECT = "effect"
    AUDIO = "audio"
    CAMERA = "camera"
    LIGHTING = "lighting"
    REFERENCE = "reference"
    OTHER = "other"


class AssetStatus(StrEnum):
    """Canonical production readiness state for an asset."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ARCHIVED = "archived"


class AssetCreate(BaseModel):
    """Validated input for creating an asset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    category: AssetCategory
    description: str = ""
    status: AssetStatus = AssetStatus.DRAFT
    file_path: Path | None = None
    tags: tuple[str, ...] = ()

    @field_validator("asset_id")
    @classmethod
    def normalize_asset_id(cls, value: str) -> str:
        """Normalize identifiers while preserving readable separators."""
        normalized = value.upper().replace(" ", "-")
        valid = all(
            character.isalnum() or character in {"-", "_"} for character in normalized
        )
        if not valid:
            raise ValueError(
                "Asset IDs may contain only letters, numbers, hyphens, and underscores"
            )
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Remove empty and duplicate tags without changing their order."""
        return tuple(dict.fromkeys(tag.strip() for tag in value if tag.strip()))


class AssetUpdate(BaseModel):
    """Validated partial update for an existing asset."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: AssetCategory | None = None
    description: str | None = None
    status: AssetStatus | None = None
    file_path: Path | None = None
    tags: tuple[str, ...] | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """Remove empty and duplicate tags without changing their order."""
        if value is None:
            return None
        return tuple(dict.fromkeys(tag.strip() for tag in value if tag.strip()))


class Asset(BaseModel):
    """Project asset returned by the application layer."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_id: str
    name: str
    category: AssetCategory
    description: str
    status: AssetStatus
    file_path: Path | None
    tags: tuple[str, ...]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
