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
from vscs.domain.assets import AssetCategory, AssetCreate, AssetUpdate
from vscs.domain.caps import (
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceStatus,
)


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


def test_edit_can_attach_missing_master_and_seed_cap(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-902",
            name="Imported Tug",
            category=AssetCategory.SHIP,
            description="Legacy asset without CAP master.",
        )
    )
    master = project / "references" / "imported_master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")

    result = _service(context).set_or_revise_master(
        "CAP-SHP-902",
        Path("references/imported_master.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )

    assert result.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert assets.get("CAP-SHP-902").file_path == Path("references/imported_master.png")
    assert context.services.require(CAPService).get("CAP-SHP-902").asset_id == "CAP-SHP-902"
    context.shutdown()


def test_edit_reuses_existing_master_and_repairs_missing_asset_path(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    references_dir = project / "references"
    references_dir.mkdir(parents=True)
    (references_dir / "existing_master.png").write_bytes(b"master")
    service = _service(context)
    assets = context.services.require(AssetService)

    first = service.create(
        AssetCreate(
            asset_id="CAP-SHP-904",
            name="Existing Master Tug",
            category=AssetCategory.SHIP,
        ),
        Path("references/existing_master.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )
    assets.update("CAP-SHP-904", AssetUpdate(file_path=None))
    assert assets.get("CAP-SHP-904").file_path is None

    repaired = service.set_or_revise_master(
        "CAP-SHP-904",
        Path("references/existing_master.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )

    assert repaired.reference_record_id == first.reference_record_id
    assert repaired.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert assets.get("CAP-SHP-904").file_path == Path("references/existing_master.png")
    context.shutdown()


def test_edit_revises_master_and_archives_previous_reference(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    references_dir = project / "references"
    references_dir.mkdir(parents=True)
    (references_dir / "master_v1.png").write_bytes(b"master-v1")
    (references_dir / "master_v2.png").write_bytes(b"master-v2")
    service = _service(context)

    first = service.create(
        AssetCreate(
            asset_id="CAP-SHP-903",
            name="Revision Tug",
            category=AssetCategory.SHIP,
        ),
        Path("references/master_v1.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )
    second = service.set_or_revise_master(
        "CAP-SHP-903",
        Path("references/master_v2.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )

    references = context.services.require(CanonicalReferenceService)
    old_reference = references.get(first.reference_record_id)
    new_reference = references.get(second.reference_record_id)
    assert old_reference.status is CanonicalReferenceStatus.ARCHIVED
    assert new_reference.version == "1.1"
    assert second.lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert context.services.require(AssetService).get("CAP-SHP-903").file_path == Path(
        "references/master_v2.png"
    )
    context.shutdown()
