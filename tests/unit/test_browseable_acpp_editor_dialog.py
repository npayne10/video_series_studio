"""Tests for project-asset browsing in the ACPP Editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from vscs.application.acpp import ACPPEditorService, AssetBindingRole
from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.ssie import Scene
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.presentation.dialogs.browseable_acpp_editor_dialog import (
    BrowseableACPPEditorDialog,
)
import vscs.presentation.dialogs.browseable_acpp_editor_dialog as dialog_module


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


def _prepare(tmp_path: Path) -> tuple[object, ProductionShot]:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(
        tmp_path / "Demo",
        name="Demo",
    )
    context.services.require(AssetService).create(
        AssetCreate(
            asset_id="SHP-IRON-HORIZON",
            name="Iron Horizon",
            category=AssetCategory.SHIP,
        )
    )
    scene = Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="EXT. XORIX ORBIT - DAY",
        location_asset_id="LOC-XORIX-ORBIT",
        summary="The Iron Horizon arrives above Xorix.",
    )
    context.services.require(StoryService).save_scene(scene)
    shot = ProductionShot(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Arrival",
        description="The Iron Horizon emerges above the planet.",
    )
    context.services.require(ShotPlanningService).save_shot(shot)
    return context, shot


def test_acpp_browse_button_adds_selected_project_asset(
    qtbot: object,
    qapp: QApplication,
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    context, shot = _prepare(tmp_path)

    class FakePicker:
        DialogCode = QDialog.DialogCode

        def __init__(self, *_args: object) -> None:
            self.selected_asset_id = "SHP-IRON-HORIZON"

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(  # type: ignore[attr-defined]
        dialog_module,
        "AssetPickerDialog",
        FakePicker,
    )
    dialog = BrowseableACPPEditorDialog(
        shot,
        context.services.require(ACPPEditorService),
        context.services.require(AssetService),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    initial = dialog.asset_list.count()
    role_index = dialog.asset_role_combo.findData(AssetBindingRole.VEHICLE.value)
    dialog.asset_role_combo.setCurrentIndex(role_index)
    dialog.browse_asset_button.click()
    qapp.processEvents()

    assert dialog.asset_list.count() == initial + 1
    assert (
        dialog.asset_list.item(dialog.asset_list.count() - 1).text()
        == "vehicle: SHP-IRON-HORIZON"
    )
    assert dialog.asset_id_edit.text() == ""

    context.shutdown()
