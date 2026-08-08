"""Integration coverage for Phase 18.2.11.2.6 category reference templates."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CanonicalReferenceView
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


def _prepare(tmp_path: Path) -> tuple[object, DerivedReferenceGenerationService]:
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
            asset_id="CAP-SHP-930",
            name="Template Test Ship",
            category=AssetCategory.SHIP,
            description="A production test ship.",
        ),
        Path("references/ship_master.png"),
        confirmed_chatgpt_master=True,
    )
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(OfflineDerivedReferencePreviewProvider())
    return context, DerivedReferenceGenerationService(references, library, registry)


def test_ship_coverage_reports_missing_required_views(tmp_path: Path) -> None:
    context, service = _prepare(tmp_path)

    coverage = service.coverage("CAP-SHP-930")

    assert coverage.present_views == (CanonicalReferenceView.MASTER,)
    assert set(coverage.missing_required) == {
        CanonicalReferenceView.FRONT,
        CanonicalReferenceView.REAR,
        CanonicalReferenceView.PORT,
        CanonicalReferenceView.STARBOARD,
        CanonicalReferenceView.TOP,
        CanonicalReferenceView.BOTTOM,
    }
    assert coverage.required_complete is False
    context.shutdown()  # type: ignore[attr-defined]


def test_generate_missing_required_fills_category_coverage(tmp_path: Path) -> None:
    context, service = _prepare(tmp_path)
    provider = OfflineDerivedReferencePreviewProvider()

    created = service.generate_missing_required(
        "CAP-SHP-930",
        provider_name=provider.name,
        seed=100,
    )

    assert len(created) == 6
    coverage = service.coverage("CAP-SHP-930")
    assert coverage.missing_required == ()
    assert coverage.required_complete is True
    assert CanonicalReferenceView.MASTER in coverage.present_views
    assert CanonicalReferenceView.TOP in coverage.present_views
    context.shutdown()  # type: ignore[attr-defined]
