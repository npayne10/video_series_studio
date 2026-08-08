"""Integration coverage for the refactored CAP production-contract workspace."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import (
    CanonicalReferenceService,
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
from vscs.domain.caps import CanonicalReferenceView, CAPStatus, CAPUpdate
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


def test_cap_workspace_tracks_authoritative_projection_state(qtbot, tmp_path: Path) -> None:
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
            asset_id="CAP-LOC-991",
            name="Production UI Location",
            category=AssetCategory.LOCATION,
            description="A controlled location used to verify CAP production UI state.",
        ),
        Path("references/location_master.png"),
        confirmed_chatgpt_master=True,
    )

    window = context.create_main_window()
    qtbot.addWidget(window)
    manager = window.cap_manager
    assert manager.table.item(0, 7).text() == "BLOCKED"

    registry = DerivedReferenceGeneratorRegistry()
    provider = OfflineDerivedReferencePreviewProvider()
    registry.register(provider)
    generation = DerivedReferenceGenerationService(references, library, registry)
    created = generation.generate(
        "CAP-LOC-991",
        (CanonicalReferenceView.PRIMARY_THREE_QUARTER,),
        provider_name=provider.name,
        seed=991,
    )
    library.approve(created[0], "CAP UI Integration")
    caps.update(
        "CAP-LOC-991",
        CAPUpdate(
            status=CAPStatus.APPROVED,
            visual_identity="Stable canonical location identity.",
            production_notes="Preserve architecture, spatial layout and canonical materials.",
        ),
    )

    manager.refresh()
    assert manager.table.item(0, 5).text() == "2"
    assert manager.table.item(0, 7).text() == "READY"
    assert "1 production ready" in manager.summary_label.text()
    projection = manager.production_projection_service.require_ready("CAP-LOC-991")
    assert projection.production_ready is True

    context.shutdown()
