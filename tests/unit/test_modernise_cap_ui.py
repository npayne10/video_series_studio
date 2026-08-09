"""UI coverage for the Phase 19.1 legacy CAP migration assistant."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.caps import CAPService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate


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


def test_workspace_exposes_modernise_cap_for_legacy_profile(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)

    assets.create(
        AssetCreate(
            asset_id="CAP-LOC-781",
            name="Legacy Migration Location",
            category=AssetCategory.LOCATION,
            description="Legacy CAP migration acceptance asset.",
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-LOC-781",
            title="Legacy Migration Location",
            canonical_description="A legacy transit hall with two entrances.",
            visual_identity="Grey stone with brushed metal trim.",
            production_notes="Preserve both entrances and the central aisle.",
        )
    )

    window = context.create_main_window()
    qtbot.addWidget(window)
    manager = window.cap_manager
    manager.refresh()

    assert manager.modernise_cap_button.text() == "Modernise CAP…"
    assert manager.modernise_cap_button.objectName() == "moderniseCAPButton"
    assert manager.structured_knowledge_service.needs_migration("CAP-LOC-781")

    manager.table.selectRow(0)
    assert manager.modernise_cap_button.isEnabled()

    context.shutdown()
