"""Integration coverage for Phase 18.2.11.2.8 Production Projection API."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import (
    CanonicalReferenceService,
    CAPService,
    ProductionProjectionBlockedError,
    ProductionProjectionService,
    ReferenceLibraryService,
)
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import (
    CanonicalReferenceLifecycle,
    CanonicalReferenceView,
    CAPStatus,
    CAPUpdate,
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


def _prepare_location(
    tmp_path: Path,
) -> tuple[object, ProductionProjectionService, ReferenceLibraryService]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "references" / "location_master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-LOC-980",
            name="Projection Test Location",
            category=AssetCategory.LOCATION,
            description="A production projection test location.",
        ),
        Path("references/location_master.png"),
        confirmed_chatgpt_master=True,
    )
    return context, context.services.require(ProductionProjectionService), library


def _generation_service(
    references: CanonicalReferenceService,
    library: ReferenceLibraryService,
) -> tuple[DerivedReferenceGenerationService, OfflineDerivedReferencePreviewProvider]:
    registry = DerivedReferenceGeneratorRegistry()
    provider = OfflineDerivedReferencePreviewProvider()
    registry.register(provider)
    return DerivedReferenceGenerationService(references, library, registry), provider


def test_projection_publishes_only_approved_or_locked_references(tmp_path: Path) -> None:
    context, service, library = _prepare_location(tmp_path)
    references = context.services.require(CanonicalReferenceService)  # type: ignore[attr-defined]
    generation, provider = _generation_service(references, library)

    created = generation.generate(
        "CAP-LOC-980",
        (CanonicalReferenceView.AERIAL,),
        provider_name=provider.name,
        seed=100,
    )
    projection = service.project("CAP-LOC-980")

    assert {reference.view for reference in projection.references} == {
        CanonicalReferenceView.MASTER
    }

    library.approve(created[0], "Projection Test")
    projection = service.project("CAP-LOC-980")
    assert {reference.view for reference in projection.references} == {
        CanonicalReferenceView.MASTER,
        CanonicalReferenceView.AERIAL,
    }
    assert all(
        reference.lifecycle
        in {CanonicalReferenceLifecycle.APPROVED, CanonicalReferenceLifecycle.LOCKED}
        for reference in projection.references
    )
    context.shutdown()  # type: ignore[attr-defined]


def test_require_ready_enforces_authoritative_production_gate(tmp_path: Path) -> None:
    context, service, library = _prepare_location(tmp_path)
    caps = context.services.require(CAPService)  # type: ignore[attr-defined]
    references = context.services.require(CanonicalReferenceService)  # type: ignore[attr-defined]

    with pytest.raises(ProductionProjectionBlockedError) as exc_info:
        service.require_ready("CAP-LOC-980")
    assert exc_info.value.projection.production_ready is False

    generation, provider = _generation_service(references, library)
    required = generation.generate(
        "CAP-LOC-980",
        (CanonicalReferenceView.PRIMARY_THREE_QUARTER,),
        provider_name=provider.name,
        seed=200,
    )
    library.approve(required[0], "Projection Test")
    caps.update(
        "CAP-LOC-980",
        CAPUpdate(
            status=CAPStatus.APPROVED,
            visual_identity="Stable location visual identity.",
            production_notes="Preserve the canonical architecture and layout.",
        ),
    )
    ready = service.require_ready("CAP-LOC-980")

    assert ready.production_ready is True
    assert ready.identity.asset_id == "CAP-LOC-980"
    assert ready.source_cap_version == "1.0"
    assert ready.checksum() == service.checksum("CAP-LOC-980")
    context.shutdown()  # type: ignore[attr-defined]
