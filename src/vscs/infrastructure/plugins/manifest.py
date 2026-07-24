"""Typed plugin manifest validation."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class PluginManifestError(RuntimeError):
    """Raised when a plugin manifest is missing or invalid."""


class PluginManifest(BaseModel):
    """Metadata and loading instructions declared by a VSCS plugin."""

    id: str
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    author: str = ""
    description: str = ""
    minimum_vscs_version: str = "0.1.0"
    entry_point: str = "plugin.py:Plugin"
    capabilities: tuple[str, ...] = ()

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Require stable lowercase identifiers safe for configuration keys."""
        normalized = value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_.-]*", normalized):
            raise ValueError(
                "Plugin id must use lowercase letters, numbers, dots, dashes, or underscores"
            )
        return normalized

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, value: str) -> str:
        """Require a relative Python file and class name."""
        try:
            module_path, class_name = value.split(":", maxsplit=1)
        except ValueError as exc:
            raise ValueError("Entry point must use '<file.py>:<ClassName>'") from exc
        path = Path(module_path)
        if path.is_absolute() or ".." in path.parts or path.suffix != ".py":
            raise ValueError("Plugin entry-point file must be a relative .py path")
        if not class_name.isidentifier():
            raise ValueError("Plugin entry-point class must be a valid identifier")
        return value

    @field_validator("capabilities")
    @classmethod
    def normalize_capabilities(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        """Normalize and de-duplicate declared capability names."""
        normalized = tuple(value.strip().lower() for value in values if value.strip())
        return tuple(dict.fromkeys(normalized))

    @classmethod
    def load(cls, manifest_path: Path) -> PluginManifest:
        """Load and validate a YAML or JSON-compatible manifest."""
        try:
            raw_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw_data, dict):
                raise PluginManifestError("Plugin manifest must contain a mapping")
            return cls.model_validate(raw_data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise PluginManifestError(f"Invalid plugin manifest {manifest_path}: {exc}") from exc
