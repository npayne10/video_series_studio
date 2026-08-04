"""Tests for the Phase 17.3 ACPP Editor interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.acpp import ACPPEditorService
from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.ssie import Scene
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.dialogs.acpp_editor_dialog import ACPPEditorDialog


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
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
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
        estimated_duration_seconds=10.0,
    )
    context.services.require(ShotPlanningService).save_shot(shot)
    return context, shot


def test_acpp_editor_prefills_tabs_and_saves(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context, shot = _prepare(tmp_path)
    service = context.services.require(ACPPEditorService)
    dialog = ACPPEditorDialog(shot, service)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    assert dialog.tabs.count() == 5
    assert dialog.shot_id_edit.text() == shot.shot_id
    assert dialog.visual_edit.toPlainText() == shot.description
    assert dialog.width_spin.value() == 1920
    assert dialog.height_spin.value() == 800
    assert dialog.save_button.isEnabled()

    dialog.status_combo.setCurrentText("ready")
    dialog.negative_edit.setPlainText("no fantasy glow\nno unstable geometry")
    dialog.save_button.click()

    stored = service.package_for_shot(shot.shot_id)
    assert stored is not None
    assert stored.metadata["editor_status"] == "ready"
    assert stored.prompt.negative_constraints == (
        "no fantasy glow",
        "no unstable geometry",
    )
    context.shutdown()


def test_acpp_editor_adds_and_removes_asset_binding(
    qtbot: object,
    tmp_path: Path,
) -> None:
    context, shot = _prepare(tmp_path)
    dialog = ACPPEditorDialog(
        shot,
        context.services.require(ACPPEditorService),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    initial = dialog.asset_list.count()
    dialog.asset_id_edit.setText("SHP-IRON-HORIZON")
    dialog.add_asset_button.click()
    assert dialog.asset_list.count() == initial + 1
    dialog.asset_list.setCurrentRow(dialog.asset_list.count() - 1)
    dialog.remove_asset_button.click()
    assert dialog.asset_list.count() == initial
    context.shutdown()
