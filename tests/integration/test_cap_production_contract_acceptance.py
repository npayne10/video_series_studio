"""End-to-end acceptance for the Phase 18.2.11.2 CAP Production Contract sequence."""

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
from vscs.application.caps.reference_templates import CategoryReferenceTemplateService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import (
    CanonicalReferenceLifecycle,
    CanonicalReferenceView,
    CAPStatus,
    CAPUpdate,
    ReadinessState,
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


def _services(tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    projection = context.services.require(ProductionProjectionService)
    library = projection.library
    readiness = projection.readiness

    registry = DerivedReferenceGeneratorRegistry()
    provider = OfflineDerivedReferencePreviewProvider()
    registry.register(provider)
    generation = DerivedReferenceGenerationService(references, library, registry)
    templates = CategoryReferenceTemplateService(references, library)
    return (
        context,
        project,
        assets,
        caps,
        references,
        library,
        readiness,
        projection,
        generation,
        templates,
        provider,
    )


def _create_asset_with_master(
    project: Path,
    assets: AssetService,
    caps: CAPService,
    references: CanonicalReferenceService,
    library: ReferenceLibraryService,
    *,
    asset_id: str,
    name: str,
    category: AssetCategory,
) -> None:
    relative_master = Path("references") / f"{asset_id.lower()}_master.png"
    master = project / relative_master
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_bytes(b"master")
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id=asset_id,
            name=name,
            category=category,
            description=f"Canonical acceptance asset: {name}.",
        ),
        relative_master,
        confirmed_chatgpt_master=True,
        actor="Phase 18.2.11.2.10 Acceptance",
    )


def test_location_contract_reaches_production_ready_end_to_end(qtbot, tmp_path: Path) -> None:
    (
        context,
        project,
        assets,
        caps,
        references,
        library,
        readiness,
        projection_service,
        generation,
        templates,
        provider,
    ) = _services(tmp_path)
    _create_asset_with_master(
        project,
        assets,
        caps,
        references,
        library,
        asset_id="CAP-LOC-991",
        name="Acceptance Location",
        category=AssetCategory.LOCATION,
    )

    initial = projection_service.project("CAP-LOC-991")
    initial_checksum = initial.checksum()
    assert initial.production_ready is False
    assert {reference.view for reference in initial.references} == {CanonicalReferenceView.MASTER}
    assert templates.coverage("CAP-LOC-991").missing_required == (
        CanonicalReferenceView.PRIMARY_THREE_QUARTER,
    )

    created_ids = generation.generate_missing_required(
        "CAP-LOC-991",
        provider_name=provider.name,
        seed=180211210,
    )
    assert len(created_ids) == 1
    candidate_projection = projection_service.project("CAP-LOC-991")
    assert len(candidate_projection.references) == 1

    library.approve(
        created_ids[0],
        "Phase 18.2.11.2.10 Acceptance",
        note="Required category view accepted for integration test",
    )
    caps.update(
        "CAP-LOC-991",
        CAPUpdate(
            status=CAPStatus.APPROVED,
            visual_identity="Stable canonical location identity.",
            production_notes="Preserve architecture, scale, layout and material identity.",
        ),
    )

    report = readiness.evaluate("CAP-LOC-991")
    assert report.identity.state is ReadinessState.READY
    assert report.references.state is ReadinessState.READY
    assert report.generation.state is ReadinessState.READY
    assert report.production.state is ReadinessState.READY
    assert report.production_ready is True

    published = projection_service.require_ready("CAP-LOC-991")
    assert published.production_ready is True
    assert published.checksum() != initial_checksum
    assert {reference.view for reference in published.references} == {
        CanonicalReferenceView.MASTER,
        CanonicalReferenceView.PRIMARY_THREE_QUARTER,
    }
    assert all(
        reference.lifecycle
        in {CanonicalReferenceLifecycle.APPROVED, CanonicalReferenceLifecycle.LOCKED}
        for reference in published.references
    )

    window = context.create_main_window()
    qtbot.addWidget(window)
    manager = window.cap_manager
    manager.refresh()
    assert manager.table.columnCount() == 8
    assert manager.table.item(0, 0).text() == "CAP-LOC-991"
    assert manager.table.item(0, 5).text() == "2"
    assert manager.table.item(0, 7).text() == "READY"
    assert manager.production_projection_service is projection_service
    assert manager.readiness_service is readiness

    context.shutdown()


def test_ship_contract_remains_explicitly_blocked_without_structured_persistence(
    tmp_path: Path,
) -> None:
    (
        context,
        project,
        assets,
        caps,
        references,
        library,
        readiness,
        projection_service,
        generation,
        _templates,
        provider,
    ) = _services(tmp_path)
    _create_asset_with_master(
        project,
        assets,
        caps,
        references,
        library,
        asset_id="CAP-SHP-991",
        name="Acceptance Ship",
        category=AssetCategory.SHIP,
    )

    created_ids = generation.generate_missing_required(
        "CAP-SHP-991",
        provider_name=provider.name,
        seed=180211220,
    )
    assert created_ids
    for reference_id in created_ids:
        library.approve(reference_id, "Phase 18.2.11.2.10 Acceptance")

    caps.update(
        "CAP-SHP-991",
        CAPUpdate(
            status=CAPStatus.APPROVED,
            visual_identity="Stable canonical spacecraft identity.",
            production_notes="Preserve hull geometry, proportions and markings.",
        ),
    )

    report = readiness.evaluate("CAP-SHP-991")
    assert report.references.state is ReadinessState.READY
    assert report.generation.state is ReadinessState.READY
    assert report.production.state is ReadinessState.BLOCKED
    blocker_codes = {gap.code for gap in report.blocking_gaps}
    assert "production.functional_identity" in blocker_codes
    assert "production.constraints" in blocker_codes

    diagnostic = projection_service.project("CAP-SHP-991")
    assert diagnostic.production_ready is False
    assert len(diagnostic.references) == 7
    with pytest.raises(ProductionProjectionBlockedError) as exc_info:
        projection_service.require_ready("CAP-SHP-991")
    assert exc_info.value.projection.checksum() == diagnostic.checksum()

    context.shutdown()


def test_projection_checksum_changes_when_canonical_contract_changes(tmp_path: Path) -> None:
    (
        context,
        project,
        assets,
        caps,
        references,
        library,
        _readiness,
        projection_service,
        _generation,
        _templates,
        _provider,
    ) = _services(tmp_path)
    _create_asset_with_master(
        project,
        assets,
        caps,
        references,
        library,
        asset_id="CAP-AUD-991",
        name="Acceptance Audio",
        category=AssetCategory.AUDIO,
    )

    before = projection_service.checksum("CAP-AUD-991")
    caps.update(
        "CAP-AUD-991",
        CAPUpdate(
            production_notes="Canonical audio production guidance changed.",
        ),
    )
    after = projection_service.checksum("CAP-AUD-991")

    assert before != after
    context.shutdown()
