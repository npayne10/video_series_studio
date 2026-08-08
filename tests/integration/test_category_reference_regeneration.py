"""Rejected category references may be regenerated without counting as active coverage."""

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


def test_rejected_required_view_can_be_generated_again(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "master.png"
    master.write_bytes(b"master")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-SHP-932",
            name="Regeneration Test Ship",
            category=AssetCategory.SHIP,
        ),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )
    provider = OfflineDerivedReferencePreviewProvider()
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(provider)
    service = DerivedReferenceGenerationService(references, library, registry)

    first = service.generate(
        "CAP-SHP-932",
        (CanonicalReferenceView.FRONT,),
        provider_name=provider.name,
    )[0]
    library.reject(first, actor="Reviewer", note="Identity drift")

    coverage = service.coverage("CAP-SHP-932")
    assert CanonicalReferenceView.FRONT in coverage.missing_required

    second = service.generate(
        "CAP-SHP-932",
        (CanonicalReferenceView.FRONT,),
        provider_name=provider.name,
        seed=10,
    )[0]

    assert second != first
    assert CanonicalReferenceView.FRONT not in service.coverage("CAP-SHP-932").missing_required
    context.shutdown()
