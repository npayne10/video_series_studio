"""Schema migration coverage for Phase 19.2.2 Behaviour Profile persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import text

from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.database import DatabaseManager


def test_schema_five_project_upgrades_to_six_and_preserves_existing_data(tmp_path: Path) -> None:
    database_path = tmp_path / "database" / "project.db"
    database_path.parent.mkdir(parents=True)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE vscs_schema_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL,
                application_version VARCHAR(32) NOT NULL,
                updated_at DATETIME
            )
            """
        )
        connection.execute(
            "INSERT INTO vscs_schema_version (id, version, application_version) VALUES (1, 5, '0.1.0')"
        )
        connection.execute("CREATE TABLE legacy_phase_19_1_marker (value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO legacy_phase_19_1_marker (value) VALUES ('phase-19.1-data')"
        )
        connection.commit()
    finally:
        connection.close()

    database = DatabaseManager()
    try:
        database.open(tmp_path, ProjectMetadata(name="Schema Migration"))
        with database.session() as session:
            schema_version = session.execute(
                text("SELECT version FROM vscs_schema_version WHERE id = 1")
            ).scalar_one()
            tables = {
                row[0]
                for row in session.execute(
                    text("SELECT name FROM sqlite_master WHERE type = 'table'")
                )
            }
            marker = session.execute(
                text("SELECT value FROM legacy_phase_19_1_marker")
            ).scalar_one()

        assert schema_version == 6
        assert "behaviour_profiles" in tables
        assert marker == "phase-19.1-data"
    finally:
        database.close()
