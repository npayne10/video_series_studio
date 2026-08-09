"""Database migration coverage for Phase 19.1 structured CAP persistence."""

import sqlite3
from pathlib import Path

from sqlalchemy import select, text

from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.database import DatabaseManager, SchemaVersion


def test_schema_four_database_is_upgraded_without_replacing_legacy_cap_fields(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "database" / "project.db"
    database_path.parent.mkdir(parents=True)
    connection = sqlite3.connect(database_path)
    connection.executescript(
        """
        CREATE TABLE vscs_schema_version (
            id INTEGER PRIMARY KEY,
            version INTEGER NOT NULL,
            application_version VARCHAR(32) NOT NULL,
            updated_at DATETIME
        );
        INSERT INTO vscs_schema_version (id, version, application_version)
        VALUES (1, 4, '0.1.0');

        CREATE TABLE canonical_asset_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id VARCHAR(64) NOT NULL UNIQUE,
            title VARCHAR(200) NOT NULL,
            version VARCHAR(32) NOT NULL DEFAULT '1.0',
            status VARCHAR(32) NOT NULL,
            canonical_description TEXT NOT NULL,
            visual_identity TEXT NOT NULL DEFAULT '',
            production_notes TEXT NOT NULL DEFAULT '',
            reference_paths TEXT NOT NULL DEFAULT '',
            created_at DATETIME,
            updated_at DATETIME
        );
        INSERT INTO canonical_asset_profiles (
            asset_id, title, version, status, canonical_description,
            visual_identity, production_notes, reference_paths
        ) VALUES (
            'CAP-SHP-001', 'Legacy Ship', '1.0', 'approved',
            'Legacy description', 'Legacy visual identity',
            'Legacy production notes', ''
        );
        """
    )
    connection.commit()
    connection.close()

    database = DatabaseManager()
    database.open(tmp_path, ProjectMetadata(name="Legacy"))

    with database.session() as session:
        schema = session.scalar(select(SchemaVersion).where(SchemaVersion.id == 1))
        assert schema is not None
        assert schema.version == 5
        columns = {
            row[1]
            for row in session.execute(text("PRAGMA table_info(canonical_asset_profiles)"))
        }
        assert {
            "structured_schema_version",
            "facts_json",
            "functional_identity_json",
            "constraints_json",
            "semantic_tags_json",
            "production_classifications_json",
            "behaviour_references_json",
            "production_metadata_json",
        } <= columns
        row = session.execute(
            text(
                "SELECT canonical_description, visual_identity, production_notes, "
                "facts_json, functional_identity_json, constraints_json "
                "FROM canonical_asset_profiles WHERE asset_id = 'CAP-SHP-001'"
            )
        ).one()
        assert row[0] == "Legacy description"
        assert row[1] == "Legacy visual identity"
        assert row[2] == "Legacy production notes"
        assert row[3:] == ("[]", "[]", "[]")

    database.close()
