"""Load, validate, and persist VSCS application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import yaml
from pydantic import ValidationError

from vscs.infrastructure.configuration.models import ApplicationSettings


class ConfigurationError(RuntimeError):
    """Raised when application settings cannot be loaded or saved."""


class ConfigurationService:
    """Manage typed YAML-backed application settings."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or self.default_config_path()
        self.settings = ApplicationSettings()

    @staticmethod
    def default_config_path() -> Path:
        """Return a platform-appropriate per-user configuration path."""
        if os.name == "nt":
            root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        else:
            root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return root / "VSCS" / "settings.yaml"

    def load(self) -> ApplicationSettings:
        """Load settings from disk, creating defaults when no file exists."""
        if not self.config_path.exists():
            self.settings = ApplicationSettings()
            self.save()
            return self.settings

        try:
            raw_data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw_data, dict):
                raise ConfigurationError("The settings file must contain a YAML mapping.")
            self.settings = ApplicationSettings.model_validate(raw_data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise ConfigurationError(f"Unable to load settings: {exc}") from exc
        return self.settings

    def save(self) -> None:
        """Persist settings atomically to avoid partial configuration files."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = self.settings.model_dump(mode="json")
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.config_path.parent,
                prefix="settings-",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                yaml.safe_dump(data, temporary_file, sort_keys=False, allow_unicode=True)
                temporary_path = Path(temporary_file.name)
            temporary_path.replace(self.config_path)
        except OSError as exc:
            raise ConfigurationError(f"Unable to save settings: {exc}") from exc

    def reset(self) -> ApplicationSettings:
        """Restore default settings and persist them."""
        self.settings = ApplicationSettings()
        self.save()
        return self.settings

    def add_recent_project(self, project_path: Path) -> None:
        """Move a project to the front of the recent-project list."""
        normalized = project_path.expanduser().resolve(strict=False)
        existing = [
            path
            for path in self.settings.recent_projects
            if str(path.expanduser().resolve(strict=False)).casefold()
            != str(normalized).casefold()
        ]
        self.settings.recent_projects = [normalized, *existing][
            : self.settings.maximum_recent_projects
        ]
        self.save()

    def remove_recent_project(self, project_path: Path) -> None:
        """Remove a project from the recent-project list."""
        target = str(project_path.expanduser().resolve(strict=False)).casefold()
        self.settings.recent_projects = [
            path
            for path in self.settings.recent_projects
            if str(path.expanduser().resolve(strict=False)).casefold() != target
        ]
        self.save()

    def clear_recent_projects(self) -> None:
        """Remove all recent projects."""
        self.settings.recent_projects.clear()
        self.save()
