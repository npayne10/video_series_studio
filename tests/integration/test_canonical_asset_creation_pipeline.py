"""Integration coverage for Phase 18.2.11.2.4 canonical Asset creation."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetNotFoundError, AssetService
from vscs.application.assets.canonical_creation import (
    CanonicalAssetCreationError,
    CanonicalAssetCreationService,
)
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CanonicalReferenceFamily, CanonicalReferenceLifecycle


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _service(context) -> CanonicalAssetCreationService:
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    return CanonicalAssetCreationService(
        assets,
        caps,
        references,
        ReferenceLibraryService(references),
    )


def test_asset_creation_seeds_draft_cap_and_locked_master(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "references" / "tug_master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")

    result = _service(context).create(
        AssetCreate(
            asset_id="CAP-SHP-900",
            name="Test Tug",
            category=AssetCategory.SHIP,
            description="Canonical test tug.",
        ),
        Path("references/tug_master.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )

    assert result.asset.file_path == Path("references/tug_master.png")
    assert (
        context.services.require(CAPService).get("CAP-SHP-900").canonical_description
        == "Canonical test tug."
    )
    entry = ReferenceLibraryService(context.services.require(CanonicalReferenceService)).get(
        result.reference_record_id
    )
    assert entry.family is CanonicalReferenceFamily.MASTER
    assert entry.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert entry.approved_by == "Neill"
    assert entry.parent_reference_id is None
    context.shutdown()


def test_asset_creation_requires_explicit_master_confirmation(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "master.png"
    master.write_bytes(b"master")

    with pytest.raises(CanonicalAssetCreationError, match="Confirm"):
        _service(context).create(
            AssetCreate(
                asset_id="CAP-SHP-901",
                name="Unconfirmed Tug",
                category=AssetCategory.SHIP,
            ),
            Path("master.png"),
            confirmed_chatgpt_master=False,
        )

    with pytest.raises(AssetNotFoundError):
        context.services.require(AssetService).get("CAP-SHP-901")
    context.shutdown()
