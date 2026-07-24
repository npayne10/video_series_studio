"""Tests for project-scoped asset management."""

from pathlib import Path

import pytest

from vscs.application.assets import (
    AssetAlreadyExistsError,
    AssetProjectNotOpenError,
    AssetRepository,
    AssetService,
    InvalidAssetPathError,
)
from vscs.application.projects import ProjectService
from vscs.domain.assets import AssetCategory, AssetCreate, AssetStatus, AssetUpdate
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import DatabaseManager


def build_asset_service(tmp_path: Path) -> tuple[AssetService, ProjectService]:
    """Create an isolated project and asset service."""
    configuration = ConfigurationService(tmp_path / "config" / "settings.yaml")
    configuration.load()
    database = DatabaseManager()
    projects = ProjectService(configuration, database)
    repository = AssetRepository(database)
    return AssetService(projects, repository), projects


def test_asset_operations_require_open_project(tmp_path: Path) -> None:
    """Asset records are always scoped to an active project database."""
    assets, _ = build_asset_service(tmp_path)

    with pytest.raises(AssetProjectNotOpenError):
        assets.list()


def test_create_get_update_and_delete_asset(tmp_path: Path) -> None:
    """The service supports the complete asset record lifecycle."""
    assets, projects = build_asset_service(tmp_path)
    projects.create(tmp_path / "Example", name="Example")

    created = assets.create(
        AssetCreate(
            asset_id="cap-chr-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            status=AssetStatus.REVIEW,
            file_path=Path("assets/characters/james.png"),
            tags=("human", "command"),
        )
    )

    assert created.asset_id == "CAP-CHR-001"
    assert assets.get("cap-chr-001").name == "Commander James Spence"
    assert assets.count() == 1

    updated = assets.update(
        "CAP-CHR-001",
        AssetUpdate(status=AssetStatus.APPROVED, tags=("human", "command", "hero")),
    )

    assert updated.status is AssetStatus.APPROVED
    assert updated.tags == ("human", "command", "hero")

    assets.delete("CAP-CHR-001")
    assert assets.count() == 0


def test_duplicate_asset_id_is_rejected(tmp_path: Path) -> None:
    """Canonical asset identifiers are unique inside a project."""
    assets, projects = build_asset_service(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    asset = AssetCreate(
        asset_id="CAP-SHP-001",
        name="Mauritania",
        category=AssetCategory.SHIP,
    )
    assets.create(asset)

    with pytest.raises(AssetAlreadyExistsError):
        assets.create(asset)


def test_search_and_category_filters(tmp_path: Path) -> None:
    """Text and category filters narrow the asset registry."""
    assets, projects = build_asset_service(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    assets.create(
        AssetCreate(
            asset_id="CAP-CHR-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            tags=("command",),
        )
    )
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-001",
            name="Mauritania",
            category=AssetCategory.SHIP,
            description="Exploration carrier",
        )
    )

    assert [asset.asset_id for asset in assets.list(query="carrier")] == ["CAP-SHP-001"]
    assert [asset.asset_id for asset in assets.list(category=AssetCategory.CHARACTER)] == [
        "CAP-CHR-001"
    ]


def test_asset_file_must_remain_inside_project(tmp_path: Path) -> None:
    """Asset media cannot reference arbitrary files outside the project."""
    assets, projects = build_asset_service(tmp_path)
    projects.create(tmp_path / "Example", name="Example")

    with pytest.raises(InvalidAssetPathError):
        assets.create(
            AssetCreate(
                asset_id="CAP-REF-001",
                name="External Reference",
                category=AssetCategory.REFERENCE,
                file_path=tmp_path.parent / "outside.png",
            )
        )
