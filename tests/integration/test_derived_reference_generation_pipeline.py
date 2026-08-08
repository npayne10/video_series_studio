"""Integration coverage for Phase 18.2.11.2.5 derived reference generation."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import (
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
)
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider


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


def _prepare(tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "references" / "tug_master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master-image")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    creation = CanonicalAssetCreationService(assets, caps, references, library)
    creation.create(
        AssetCreate(
            asset_id="CAP-SHP-904",
            name="Derived Tug",
            category=AssetCategory.SHIP,
            description="A canonical Guild towing ship.",
        ),
        Path("references/tug_master.png"),
        confirmed_chatgpt_master=True,
        actor="Neill",
    )
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(OfflineDerivedReferencePreviewProvider())
    service = DerivedReferenceGenerationService(references, library, registry)
    return context, project, references, library, service


def test_selected_views_become_master_linked_candidates(tmp_path: Path) -> None:
    context, project, references, library, service = _prepare(tmp_path)
    provider = OfflineDerivedReferencePreviewProvider()

    created = service.generate(
        "CAP-SHP-904",
        (CanonicalReferenceView.FRONT, CanonicalReferenceView.TOP),
        provider_name=provider.name,
        actor="Neill",
    )

    assert len(created) == 2
    entries = library.list_for_cap("CAP-SHP-904")
    master = next(entry for entry in entries if entry.family is CanonicalReferenceFamily.MASTER)
    derived = [entry for entry in entries if entry.origin is CanonicalReferenceOrigin.VSCS_DERIVED]
    assert {entry.view for entry in derived} == {
        CanonicalReferenceView.FRONT,
        CanonicalReferenceView.TOP,
    }
    assert all(entry.parent_reference_id == master.reference_id for entry in derived)
    assert all(entry.lifecycle is CanonicalReferenceLifecycle.CANDIDATE for entry in derived)
    for reference_id in created:
        reference = references.get(reference_id)
        assert (project / reference.file_path).exists()
    context.shutdown()


def test_duplicate_active_view_is_rejected(tmp_path: Path) -> None:
    context, _project, _references, _library, service = _prepare(tmp_path)
    provider = OfflineDerivedReferencePreviewProvider()
    service.generate(
        "CAP-SHP-904",
        (CanonicalReferenceView.REAR,),
        provider_name=provider.name,
    )

    with pytest.raises(DerivedReferenceGenerationError, match="already exist"):
        service.generate(
            "CAP-SHP-904",
            (CanonicalReferenceView.REAR,),
            provider_name=provider.name,
        )
    context.shutdown()
