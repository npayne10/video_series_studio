"""UI contract tests for Phase 19.1 structured CAP editing."""

from pathlib import Path

from PySide6.QtWidgets import QTableWidgetItem

from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate
from vscs.presentation.widgets.cap_manager import CAPEditorDialog


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


def test_cap_editor_exposes_structured_production_knowledge(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-779",
            name="Editor Ship",
            category=AssetCategory.SHIP,
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-SHP-779",
            title="Editor Ship",
            canonical_description="Canonical ship.",
        )
    )
    window = context.create_main_window()
    qtbot.addWidget(window)
    dialog = CAPEditorDialog(
        caps,
        references,
        caps.get("CAP-SHP-779"),
        window.cap_manager,
    )
    qtbot.addWidget(dialog)

    assert dialog.structured_tabs.objectName() == "capStructuredKnowledgeTabs"
    assert dialog.structured_tabs.count() == 4
    assert dialog.propose_structured_button.isEnabled()

    dialog.facts_table.insertRow(0)
    for column, value in enumerate(("class", "Survey Vessel", "", "approved")):
        dialog.facts_table.setItem(0, column, QTableWidgetItem(value))
    dialog.capabilities_table.insertRow(0)
    for column, value in enumerate(("Orbital flight", "Operates in orbit", "approved")):
        dialog.capabilities_table.setItem(0, column, QTableWidgetItem(value))
    dialog.constraints_table.insertRow(0)
    for column, value in enumerate(("required", "Preserve hull", "Continuity", "approved")):
        dialog.constraints_table.setItem(0, column, QTableWidgetItem(value))

    update = dialog.update_value()
    assert update.facts is not None and update.facts[0].value == "Survey Vessel"
    assert update.functional_identity is not None
    assert update.functional_identity[0].capability == "Orbital flight"
    assert update.constraints is not None and update.constraints[0].rule == "Preserve hull"
    context.shutdown()
