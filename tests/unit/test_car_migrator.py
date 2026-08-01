"""Tests for the CAR v2 repository migrator."""

import json
from pathlib import Path

from vscs.application.car import CarRepositoryMigrator


def create_asset(root: Path, category: str, folder_name: str) -> Path:
    """Create a representative legacy asset directory."""
    asset = root / category / folder_name
    (asset / "approved").mkdir(parents=True)
    (asset / "approved" / "legacy.png").write_bytes(b"legacy-image")
    (asset / "manifest.json").write_text(
        json.dumps(
            {
                "asset_id": folder_name.split("_", maxsplit=1)[0],
                "name": folder_name.split("_", maxsplit=1)[1].replace("_", " "),
            }
        ),
        encoding="utf-8",
    )
    return asset


def test_dry_run_reports_changes_without_writing(tmp_path: Path) -> None:
    """Dry-run mode plans the CAR structure and leaves the repository untouched."""
    asset = create_asset(tmp_path, "ships", "CAP-SHP-002_Iron_Horizon")

    report = CarRepositoryMigrator(tmp_path).migrate()

    assert report.applied is False
    assert report.assets_scanned == 1
    assert report.directories_created == 6
    assert report.files_created == 5
    assert not (asset / "canon").exists()
    assert (asset / "approved" / "legacy.png").exists()


def test_apply_creates_structure_and_preserves_existing_media(tmp_path: Path) -> None:
    """Apply mode creates only missing CAR files and never moves legacy media."""
    asset = create_asset(tmp_path, "characters", "CAP-CHR-001_Commander_James_Spence")

    report = CarRepositoryMigrator(tmp_path).migrate(apply=True)

    assert report.applied is True
    assert (asset / "canon").is_dir()
    assert (asset / "metadata" / "cap.json").is_file()
    assert (asset / "prompts").is_dir()
    assert (asset / "thumbnails").is_dir()
    assert (asset / "approved" / "legacy.png").exists()

    cap = json.loads((asset / "metadata" / "cap.json").read_text(encoding="utf-8"))
    assert cap["asset_id"] == "CAP-CHR-001"
    assert cap["name"] == "Commander James Spence"
    assert cap["category"] == "characters"
    assert cap["status"] == "migration_pending"


def test_existing_metadata_is_not_overwritten(tmp_path: Path) -> None:
    """Existing CAR metadata remains authoritative during repeated migrations."""
    asset = create_asset(tmp_path, "props", "CAP-PRP-009_Coffee_Mug")
    metadata = asset / "metadata"
    metadata.mkdir()
    existing = metadata / "knowledge.json"
    existing.write_text('{"design_rules": ["keep handle"]}', encoding="utf-8")

    CarRepositoryMigrator(tmp_path).migrate(apply=True)

    assert existing.read_text(encoding="utf-8") == '{"design_rules": ["keep handle"]}'


def test_missing_manifest_uses_folder_identity_and_warns(tmp_path: Path) -> None:
    """Folders remain migratable when a legacy manifest is missing."""
    asset = tmp_path / "ships" / "CAP-SHP-004_Guild_Cargo_Shuttle"
    asset.mkdir(parents=True)

    report = CarRepositoryMigrator(tmp_path).migrate(apply=True)

    cap = json.loads((asset / "metadata" / "cap.json").read_text(encoding="utf-8"))
    assert cap["asset_id"] == "CAP-SHP-004"
    assert cap["name"] == "Guild Cargo Shuttle"
    expected_manifest = Path("ships") / "CAP-SHP-004_Guild_Cargo_Shuttle" / "manifest.json"
    assert report.warnings == [f"Missing manifest: {expected_manifest}"]


def test_report_can_be_written(tmp_path: Path) -> None:
    """A machine-readable migration report can be persisted for review."""
    create_asset(tmp_path, "ships", "CAP-SHP-001_Mauritania")
    migrator = CarRepositoryMigrator(tmp_path)
    report = migrator.migrate()

    output = migrator.write_report(report, tmp_path / "reports" / "migration.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["assets_scanned"] == 1
    assert payload["applied"] is False
    assert payload["actions"]
