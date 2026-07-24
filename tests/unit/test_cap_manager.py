"""Tests for project-scoped Canonical Asset Profiles."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import (
    CAPAlreadyExistsError,
    CAPAssetNotFoundError,
    CAPRepository,
    CAPService,
    InvalidCAPReferencePathError,
)
from vscs.application.projects import ProjectService
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate, CAPStatus, CAPUpdate
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import DatabaseManager


def build_services(tmp_path: Path) -> tuple[CAPService, AssetService, ProjectService]:
    configuration = ConfigurationService(tmp_path / "config" / "settings.yaml")
    configuration.load()
    database = DatabaseManager()
    projects = ProjectService(configuration, database)
    assets = AssetService(projects, AssetRepository(database))
    caps = CAPService(assets, CAPRepository(database))
    return caps, assets, projects


def register_asset(assets: AssetService) -> None:
    assets.create(
        AssetCreate(
            asset_id="CAP-CHR-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
        )
    )


def test_cap_requires_registered_asset(tmp_path: Path) -> None:
    caps, _, projects = build_services(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    with pytest.raises(CAPAssetNotFoundError):
        caps.create(
            CAPCreate(
                asset_id="CAP-CHR-404",
                title="Missing Character",
                canonical_description="A profile without a registered asset.",
            )
        )


def test_create_get_update_and_delete_cap(tmp_path: Path) -> None:
    caps, assets, projects = build_services(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    register_asset(assets)
    created = caps.create(
        CAPCreate(
            asset_id="cap-chr-001",
            title="Commander James Spence",
            status=CAPStatus.REVIEW,
            canonical_description="A disciplined Guild commander.",
            visual_identity="Grey-blue eyes and a restrained command presence.",
            reference_paths=(Path("references/james.png"),),
        )
    )
    assert created.asset_id == "CAP-CHR-001"
    assert caps.get("cap-chr-001").title == "Commander James Spence"
    updated = caps.update(
        "CAP-CHR-001", CAPUpdate(status=CAPStatus.APPROVED, version="1.1")
    )
    assert updated.status is CAPStatus.APPROVED
    assert updated.version == "1.1"
    caps.delete("CAP-CHR-001")
    assert caps.list() == ()


def test_duplicate_cap_is_rejected(tmp_path: Path) -> None:
    caps, assets, projects = build_services(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    register_asset(assets)
    profile = CAPCreate(
        asset_id="CAP-CHR-001",
        title="Commander James Spence",
        canonical_description="Canonical character definition.",
    )
    caps.create(profile)
    with pytest.raises(CAPAlreadyExistsError):
        caps.create(profile)


def test_search_status_and_available_assets(tmp_path: Path) -> None:
    caps, assets, projects = build_services(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    register_asset(assets)
    assert caps.available_assets() == (("CAP-CHR-001", "Commander James Spence"),)
    caps.create(
        CAPCreate(
            asset_id="CAP-CHR-001",
            title="Commander James Spence",
            status=CAPStatus.APPROVED,
            canonical_description="Guild commander aboard the Iron Horizon.",
        )
    )
    assert caps.available_assets() == ()
    assert [profile.asset_id for profile in caps.list(query="Iron Horizon")] == [
        "CAP-CHR-001"
    ]
    assert len(caps.list(status=CAPStatus.APPROVED)) == 1


def test_reference_files_must_remain_inside_project(tmp_path: Path) -> None:
    caps, assets, projects = build_services(tmp_path)
    projects.create(tmp_path / "Example", name="Example")
    register_asset(assets)
    with pytest.raises(InvalidCAPReferencePathError):
        caps.create(
            CAPCreate(
                asset_id="CAP-CHR-001",
                title="Commander James Spence",
                canonical_description="Canonical character definition.",
                reference_paths=(tmp_path.parent / "outside.png",),
            )
        )
