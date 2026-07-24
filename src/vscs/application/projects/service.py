"""Project creation, persistence, and lifecycle management."""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.logging import LoggingService


class ProjectError(RuntimeError):
    """Base exception for project lifecycle failures."""


class ProjectAlreadyOpenError(ProjectError):
    """Raised when an operation requires the current project to be closed."""


class ProjectNotOpenError(ProjectError):
    """Raised when an operation requires an active project."""


class ProjectExistsError(ProjectError):
    """Raised when project creation would overwrite an existing project."""


class InvalidProjectError(ProjectError):
    """Raised when a project file is missing, invalid, or unsupported."""


class ProjectService:
    """Manage the single active VSCS project for the application."""

    PROJECT_FILE_NAME = "project.vscs"
    REQUIRED_DIRECTORIES = (
        "config",
        "database",
        "assets/characters",
        "assets/locations",
        "assets/props",
        "assets/ships",
        "assets/audio",
        "assets/reference",
        "story",
        "production",
        "renders/preview",
        "renders/production",
        "renders/master",
        "exports",
        "cache",
        "logs",
        "temp",
    )

    def __init__(self, configuration: ConfigurationService) -> None:
        self.configuration = configuration
        self.current_project: ProjectMetadata | None = None
        self.project_directory: Path | None = None
        self._logger = LoggingService.get_logger("projects")

    @property
    def is_project_open(self) -> bool:
        """Return whether a project is currently active."""
        return self.current_project is not None

    @property
    def project_file(self) -> Path | None:
        """Return the active project's metadata file path."""
        if self.project_directory is None:
            return None
        return self.project_directory / self.PROJECT_FILE_NAME

    def create(
        self,
        directory: Path,
        *,
        name: str,
        description: str = "",
        author: str = "",
    ) -> ProjectMetadata:
        """Create and open a new project directory."""
        self._require_closed()
        project_directory = directory.expanduser().resolve(strict=False)
        if project_directory.exists() and any(project_directory.iterdir()):
            raise ProjectExistsError(f"Project directory is not empty: {project_directory}")

        created_directory = not project_directory.exists()
        try:
            project_directory.mkdir(parents=True, exist_ok=True)
            for relative_path in self.REQUIRED_DIRECTORIES:
                (project_directory / relative_path).mkdir(parents=True, exist_ok=True)

            project = ProjectMetadata(name=name, description=description, author=author)
            self.current_project = project
            self.project_directory = project_directory
            self.save()
        except (OSError, ValidationError, ProjectError) as exc:
            self.current_project = None
            self.project_directory = None
            if created_directory:
                shutil.rmtree(project_directory, ignore_errors=True)
            if isinstance(exc, ProjectError):
                raise
            raise ProjectError(f"Unable to create project: {exc}") from exc

        self._remember_project(project_directory)
        self._logger.info("Project created: %s", project_directory)
        return project

    def open(self, path: Path) -> ProjectMetadata:
        """Load and activate an existing VSCS project."""
        self._require_closed()
        project_file = self._resolve_project_file(path)
        try:
            raw_data = yaml.safe_load(project_file.read_text(encoding="utf-8")) or {}
            project = ProjectMetadata.model_validate(raw_data)
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise InvalidProjectError(f"Unable to open project {project_file}: {exc}") from exc

        self.current_project = project
        self.project_directory = project_file.parent
        self._remember_project(project_file.parent)
        self._logger.info("Project opened: %s", project_file.parent)
        return project

    def save(self) -> None:
        """Persist the active project using an atomic file replacement."""
        project, project_file = self._require_open()
        project.modified_at = datetime.now(UTC)
        temporary_file = project_file.with_suffix(project_file.suffix + ".tmp")
        try:
            payload = project.model_dump(mode="json")
            temporary_file.write_text(
                yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            temporary_file.replace(project_file)
        except (OSError, yaml.YAMLError) as exc:
            temporary_file.unlink(missing_ok=True)
            raise ProjectError(f"Unable to save project {project_file}: {exc}") from exc
        self._logger.info("Project saved: %s", project_file)

    def close(self) -> None:
        """Close the active project and clear in-memory project state."""
        project, project_file = self._require_open()
        self._logger.info("Project closed: %s (%s)", project_file, project.name)
        self.current_project = None
        self.project_directory = None

    def _resolve_project_file(self, path: Path) -> Path:
        resolved = path.expanduser().resolve(strict=False)
        project_file = resolved / self.PROJECT_FILE_NAME if resolved.is_dir() else resolved
        if not project_file.is_file():
            raise InvalidProjectError(f"VSCS project file not found: {project_file}")
        return project_file

    def _remember_project(self, project_directory: Path) -> None:
        self.configuration.add_recent_project(project_directory)
        self.configuration.save()

    def _require_closed(self) -> None:
        if self.is_project_open:
            raise ProjectAlreadyOpenError("Close the current project before continuing")

    def _require_open(self) -> tuple[ProjectMetadata, Path]:
        if self.current_project is None or self.project_file is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.current_project, self.project_file
