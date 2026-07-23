"""Typed configuration models for Video Series Studio."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Theme(StrEnum):
    """Supported application themes."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class RendererSettings(BaseModel):
    """Configuration for an external rendering application."""

    enabled: bool = False
    executable_path: Path | None = None
    api_url: str | None = None


class DatabaseSettings(BaseModel):
    """Application database and cache locations."""

    database_path: Path | None = None
    cache_directory: Path | None = None


class WorkspaceSettings(BaseModel):
    """Workspace behaviour and user-interface preferences."""

    default_workspace: str = "Dashboard"
    restore_last_project: bool = True
    confirm_before_exit: bool = False


class ApplicationSettings(BaseModel):
    """Root VSCS application configuration model."""

    schema_version: int = 1
    theme: Theme = Theme.SYSTEM
    recent_projects: list[Path] = Field(default_factory=list)
    maximum_recent_projects: int = Field(default=10, ge=1, le=50)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    renderers: dict[str, RendererSettings] = Field(
        default_factory=lambda: {
            "comfyui": RendererSettings(),
            "pinokio": RendererSettings(),
        }
    )

    @field_validator("recent_projects")
    @classmethod
    def remove_duplicate_recent_projects(cls, projects: list[Path]) -> list[Path]:
        """Keep recent projects unique while preserving their order."""
        unique: list[Path] = []
        seen: set[str] = set()
        for project in projects:
            key = str(project.expanduser().resolve(strict=False)).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(project)
        return unique
