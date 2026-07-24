"""Tests for project-scoped database lifecycle management."""

from pathlib import Path

import pytest
from sqlalchemy import select, text

from vscs.application.projects import ProjectService
from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import (
    DatabaseAlreadyOpenError,
    DatabaseManager,
    DatabaseNotOpenError,
    SchemaVersion,
)


def build_project_service(tmp_path: Path) -> tuple[ProjectService, DatabaseManager]:
    """Create isolated project and database services."""
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    database = DatabaseManager()
    return ProjectService(configuration, database), database


def test_open_initializes_database_and_schema(tmp_path: Path) -> None:
    """Opening a project database creates the framework schema record."""
    database = DatabaseManager()
    project = ProjectMetadata(name="Series")

    database_path = database.open(tmp_path, project)

    assert database_path == tmp_path / "database" / "project.db"
    assert database_path.is_file()
    assert database.is_open
    with database.session() as session:
        schema = session.scalar(select(SchemaVersion).where(SchemaVersion.id == 1))
        assert schema is not None
        assert schema.version == database.SCHEMA_VERSION


def test_project_lifecycle_opens_and_closes_database(tmp_path: Path) -> None:
    """Project lifecycle management owns the matching database connection."""
    projects, database = build_project_service(tmp_path)
    project_directory = tmp_path / "Integrated"

    projects.create(project_directory, name="Integrated")

    assert database.is_open
    assert database.database_path == project_directory / "database" / "project.db"

    projects.close()

    assert not database.is_open
    assert database.database_path is None


def test_session_commits_successful_transaction(tmp_path: Path) -> None:
    """The session context commits successful work."""
    database = DatabaseManager()
    database.open(tmp_path, ProjectMetadata(name="Transactions"))

    with database.session() as session:
        session.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)"))
        session.execute(text("INSERT INTO sample (value) VALUES ('saved')"))

    with database.session() as session:
        value = session.execute(text("SELECT value FROM sample")).scalar_one()

    assert value == "saved"


def test_session_rolls_back_failed_transaction(tmp_path: Path) -> None:
    """The session context rolls back work when an exception escapes."""
    database = DatabaseManager()
    database.open(tmp_path, ProjectMetadata(name="Rollback"))
    with database.session() as session:
        session.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)"))

    with pytest.raises(RuntimeError):
        with database.session() as session:
            session.execute(text("INSERT INTO sample (value) VALUES ('discarded')"))
            raise RuntimeError("stop")

    with database.session() as session:
        count = session.execute(text("SELECT COUNT(*) FROM sample")).scalar_one()

    assert count == 0


def test_integrity_check_and_backup(tmp_path: Path) -> None:
    """Healthy databases pass integrity checks and produce restorable backups."""
    database = DatabaseManager()
    database.open(tmp_path, ProjectMetadata(name="Backup"))

    backup_path = database.backup()

    assert database.check_integrity()
    assert backup_path.is_file()
    assert backup_path.parent.name == "backups"
    assert backup_path.stat().st_size > 0


def test_database_operations_require_open_database(tmp_path: Path) -> None:
    """Database-only operations fail clearly without an active project."""
    database = DatabaseManager()

    with pytest.raises(DatabaseNotOpenError):
        database.check_integrity()
    with pytest.raises(DatabaseNotOpenError):
        database.backup(tmp_path / "backup.db")


def test_second_database_requires_close(tmp_path: Path) -> None:
    """A manager cannot silently switch between project databases."""
    database = DatabaseManager()
    project = ProjectMetadata(name="First")
    database.open(tmp_path / "first", project)

    with pytest.raises(DatabaseAlreadyOpenError):
        database.open(tmp_path / "second", ProjectMetadata(name="Second"))
