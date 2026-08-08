"""UI contract coverage for Phase 18.2.11.2.9 CAP UI Refactoring."""

from pathlib import Path

from PySide6.QtWidgets import QLabel

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import (
    CanonicalReferenceService,
    CAPService,
    ReferenceLibraryService,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.presentation.widgets.cap_manager import CAPEditorDialog
from vscs.presentation.widgets.cap_ui_refactoring import ProductionProjectionDialog


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
    master = project / "references" / "ship_master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-SHP-990",
            name="UI Projection Ship",
            category=AssetCategory.SHIP,
            description="A canonical ship used to verify the production-contract UI.",
        ),
        Path("references/ship_master.png"),
        confirmed_chatgpt_master=True,
    )
    return context, caps, references


def test_cap_workspace_surfaces_projection_status_without_recalculating(
    qtbot,
    tmp_path: Path,
) -> None:
    context, _caps, _references = _prepare(tmp_path)
    window = context.create_main_window()
    qtbot.addWidget(window)
    manager = window.cap_manager

    assert manager.table.columnCount() == 8
    assert tuple(
        manager.table.horizontalHeaderItem(column).text()
        for column in range(manager.table.columnCount())
    ) == (
        "Asset ID",
        "CAP Title",
        "Category",
        "Version",
        "Status",
        "Published References",
        "Readiness",
        "Production",
    )
    assert manager.table.rowCount() == 1
    assert manager.table.item(0, 0).text() == "CAP-SHP-990"
    assert manager.table.item(0, 2).text() == "ship"
    assert manager.table.item(0, 5).text() == "1"
    assert manager.table.item(0, 7).text() == "BLOCKED"
    assert manager.production_projection_button.text() == "Production Projection"
    assert "1 CAP(s)" in manager.summary_label.text()

    context.shutdown()


def test_refactored_refresh_remains_installed_for_search_and_refresh_button(
    qtbot,
    tmp_path: Path,
) -> None:
    context, _caps, _references = _prepare(tmp_path)
    window = context.create_main_window()
    qtbot.addWidget(window)
    manager = window.cap_manager

    manager.search_input.setText("UI Projection Ship")
    assert manager.table.columnCount() == 8
    assert manager.table.rowCount() == 1
    assert manager.table.item(0, 0).text() == "CAP-SHP-990"

    manager.refresh_button.click()
    assert manager.table.columnCount() == 8
    assert manager.table.item(0, 7).text() == "BLOCKED"

    context.shutdown()


def test_cap_editor_explains_governed_reference_ownership(qtbot, tmp_path: Path) -> None:
    context, caps, references = _prepare(tmp_path)
    window = context.create_main_window()
    qtbot.addWidget(window)

    dialog = CAPEditorDialog(caps, references, caps.get("CAP-SHP-990"))
    qtbot.addWidget(dialog)

    guidance = dialog.findChild(QLabel, "capProductionContractGuidance")
    assert guidance is not None
    assert "ChatGPT MASTER" in guidance.text()
    assert "Generate Production References" in guidance.text()
    assert dialog.add_reference_button.text() == "Import External Reference…"

    context.shutdown()


def test_projection_inspector_uses_authoritative_projection(qtbot, tmp_path: Path) -> None:
    context, _caps, _references = _prepare(tmp_path)
    window = context.create_main_window()
    qtbot.addWidget(window)
    projection = window.cap_manager.production_projection_service.project("CAP-SHP-990")

    dialog = ProductionProjectionDialog(projection)
    qtbot.addWidget(dialog)

    assert dialog.objectName() == "productionProjectionDialog"
    assert dialog.references.rowCount() == len(projection.references) == 1
    assert dialog.references.item(0, 2).text() == "Master"
    assert dialog.references.item(0, 3).text() == "Locked"

    context.shutdown()
