"""Typed models for VSCS production projects."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ProductionSettings(BaseModel):
    """Default production settings stored with a project."""

    renderer: str = "comfyui"
    width: int = Field(default=1920, ge=1)
    height: int = Field(default=1080, ge=1)
    frame_rate: float = Field(default=24.0, gt=0)
    profile: str = "production"


class ProjectPaths(BaseModel):
    """Project-relative paths used by VSCS subsystems."""

    database: Path = Path("database/project.db")
    assets: Path = Path("assets")
    story: Path = Path("story")
    production: Path = Path("production")
    renders: Path = Path("renders")
    exports: Path = Path("exports")
    cache: Path = Path("cache")

    @field_validator("*")
    @classmethod
    def require_relative_paths(cls, value: Path) -> Path:
        """Prevent project metadata from escaping the project directory."""
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("Project paths must remain relative to the project directory")
        return value


class ProjectMetadata(BaseModel):
    """Persistent metadata for a Video Series Studio project."""

    schema_version: int = 1
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    author: str = ""
    project_version: str = "0.1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    production: ProductionSettings = Field(default_factory=ProductionSettings)
    paths: ProjectPaths = Field(default_factory=ProjectPaths)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Trim project names and reject whitespace-only values."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Project name cannot be empty")
        return normalized
