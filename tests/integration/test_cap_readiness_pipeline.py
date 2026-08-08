"""Integration coverage for Phase 18.2.11.2.7 CAP readiness."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import (
    CanonicalReferenceService,
    CAPReadinessService,
    CAPService,
    ReferenceLibraryService,
)
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPStatus, CAPUpdate, ReadinessState
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


def _prepare(tmp_path: Path) -> tuple[object, CAPReadinessService, ReferenceLibraryService]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "references" / "ship_master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-SHP-940",
            name="Readiness Test Ship",
            category=AssetCategory.SHIP,
            description="A canonical readiness test ship.",
        ),
        Path("references/ship_master.png"),
        confirmed_chatgpt_master=True,
    )
    caps.update(
        "CAP-SHP-940",
        CAPUpdate(
            status=CAPStatus.APPROVED,
            visual_identity="Preserve hull geometry, markings, engines and materials.",
            production_notes="Use canonical references as production authority.",
        ),
    )
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(OfflineDerivedReferencePreviewProvider())
    generation = DerivedReferenceGenerationService(references, library, registry)
    generation.generate_missing_required(
        "CAP-SHP-940",
        provider_name=OfflineDerivedReferencePreviewProvider().name,
        seed=200,
    )
    return context, CAPReadinessService(caps, references, library), library


def test_candidate_required_views_do_not_satisfy_reference_readiness(tmp_path: Path) -> None:
    context, readiness, _library = _prepare(tmp_path)

    report = readiness.evaluate("CAP-SHP-940")

    assert report.identity.state is ReadinessState.READY
    assert report.references.state is ReadinessState.PARTIAL
    assert report.generation.state is ReadinessState.BLOCKED
    assert report.production.state is ReadinessState.BLOCKED
    context.shutdown()  # type: ignore[attr-defined]


def test_approved_required_views_unlock_generation_readiness(tmp_path: Path) -> None:
    context, readiness, library = _prepare(tmp_path)
    for entry in library.list_for_cap("CAP-SHP-940"):
        if entry.lifecycle.value == "candidate":
            library.approve(entry.reference_record_id, "Acceptance Tester")

    report = readiness.evaluate("CAP-SHP-940")

    assert report.references.state is ReadinessState.READY
    assert report.generation.state is ReadinessState.READY
    assert report.production.state is ReadinessState.BLOCKED
    assert any(
        gap.code == "production.functional_identity" for gap in report.production.gaps
    )
    assert any(gap.code == "production.constraints" for gap in report.production.gaps)
    context.shutdown()  # type: ignore[attr-defined]
