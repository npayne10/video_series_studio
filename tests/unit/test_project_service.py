"""Tests for VSCS project lifecycle management."""

from pathlib import Path

import pytest

from vscs.application.projects import (
    InvalidProjectError,
    ProjectAlreadyOpenError,
    ProjectExistsError,
    ProjectNotOpenError,
    ProjectService,
)
from vscs.infrastructure.configuration import ConfigurationService


def build_project_service(tmp_path: Path) -> ProjectService:
    """Create a project service with isolated persistent settings."""
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    return ProjectService(configuration)


def test_create_project_builds_standard_structure(tmp_path: Path) -> None:
    """Creating a project establishes every required production directory."""
    service = build_project_service(tmp_path)
    project_directory = tmp_path / "Xorix"

    project = service.create(
        project_directory,
        name="Xorix",
        description="Streaming series production",
        author="S.S. Drake",
    )

    assert service.is_project_open
    assert project.name == "Xorix"
    assert (project_directory / "project.vscs").is_file()
    for relative_path in service.REQUIRED_DIRECTORIES:
        assert (project_directory / relative_path).is_dir()


def test_save_and_reopen_project_metadata(tmp_path: Path) -> None:
    """Project metadata persists and can be reopened in a new service."""
    project_directory = tmp_path / "Series"
    service = build_project_service(tmp_path)
    project = service.create(project_directory, name="Series")
    project.description = "Updated project description"
    project.production.width = 3840
    project.production.height = 2160
    service.save()
    service.close()

    reopened_service = build_project_service(tmp_path)
    reopened = reopened_service.open(project_directory)

    assert reopened.name == "Series"
    assert reopened.description == "Updated project description"
    assert reopened.production.width == 3840
    assert reopened.production.height == 2160


def test_create_records_recent_project(tmp_path: Path) -> None:
    """Created projects are added to persistent recent-project settings."""
    service = build_project_service(tmp_path)
    project_directory = tmp_path / "Remembered"

    service.create(project_directory, name="Remembered")

    assert service.configuration.settings.recent_projects[0] == project_directory


def test_non_empty_project_directory_is_rejected(tmp_path: Path) -> None:
    """Project creation never overwrites an existing non-empty directory."""
    service = build_project_service(tmp_path)
    project_directory = tmp_path / "Existing"
    project_directory.mkdir()
    (project_directory / "keep.txt").write_text("important", encoding="utf-8")

    with pytest.raises(ProjectExistsError):
        service.create(project_directory, name="Existing")


def test_second_project_requires_current_project_to_close(tmp_path: Path) -> None:
    """Only one project may be active in an application session."""
    service = build_project_service(tmp_path)
    service.create(tmp_path / "First", name="First")

    with pytest.raises(ProjectAlreadyOpenError):
        service.create(tmp_path / "Second", name="Second")


def test_save_and_close_require_open_project(tmp_path: Path) -> None:
    """Lifecycle operations fail clearly when no project is active."""
    service = build_project_service(tmp_path)

    with pytest.raises(ProjectNotOpenError):
        service.save()
    with pytest.raises(ProjectNotOpenError):
        service.close()


def test_invalid_project_file_is_rejected(tmp_path: Path) -> None:
    """Malformed metadata is reported as an invalid project."""
    service = build_project_service(tmp_path)
    project_file = tmp_path / "project.vscs"
    project_file.write_text("name: []", encoding="utf-8")

    with pytest.raises(InvalidProjectError):
        service.open(project_file)
