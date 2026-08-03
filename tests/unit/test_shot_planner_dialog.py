"""Tests for the Phase 17.2 Shot Planner interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService, ShotPlanningStatus
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.presentation.dialogs.shot_planner_dialog import ShotPlannerDialog


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


def test_shot_planner_creates_ready_shot(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    service = ShotPlanningService(projects)
    dialog = ShotPlannerDialog(
        "EP-001-SCN-001",
        service,
        context.services.require(AssetService),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    assert not dialog.save_button.isEnabled()
    assert dialog.shot_id_edit.text() == "EP-001-SCN-001-SHT-001"
    dialog.title_edit.setText("Bridge establishing")
    dialog.description_edit.setPlainText(
        "A wide view establishes the Mauritania bridge and active crew."
    )
    dialog.duration_spin.setValue(8.0)
    assert dialog.save_button.isEnabled()
    dialog.save_button.click()

    shot = service.list_shots("EP-001-SCN-001")[0]
    assert shot.title == "Bridge establishing"
    assert shot.status is ShotPlanningStatus.READY
    assert shot.estimated_duration_seconds == 8.0
    context.shutdown()


def test_shot_planner_lists_camera_and_lighting_profiles(
    qtbot: object,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate(
            asset_id="CAM-STATIC",
            name="Static Camera",
            category=AssetCategory.CAMERA,
        )
    )
    assets.create(
        AssetCreate(
            asset_id="LGT-BRIDGE",
            name="Bridge Operational",
            category=AssetCategory.LIGHTING,
        )
    )
    dialog = ShotPlannerDialog(
        "EP-001-SCN-001",
        ShotPlanningService(projects),
        assets,
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.camera_profile_combo.findData("CAM-STATIC") >= 0
    assert dialog.lighting_profile_combo.findData("LGT-BRIDGE") >= 0
    context.shutdown()


def test_shot_planner_allocates_continuity_between_shots(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    service = ShotPlanningService(projects)
    dialog = ShotPlannerDialog(
        "EP-001-SCN-001",
        service,
        context.services.require(AssetService),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    dialog.title_edit.setText("Master")
    dialog.description_edit.setPlainText("Master coverage of the bridge.")
    dialog.save_button.click()
    first = service.list_shots()[0]

    dialog.add_button.click()
    dialog.title_edit.setText("James reaction")
    dialog.description_edit.setPlainText("James reacts to the signal.")
    index = dialog.continuity_combo.findData(first.shot_id)
    assert index >= 0
    dialog.continuity_combo.setCurrentIndex(index)
    dialog.continuity_notes_edit.setPlainText("Maintain James's screen-left eyeline.")
    dialog.save_button.click()

    second = service.list_shots()[1]
    assert second.continuity_from_shot_id == first.shot_id
    assert "screen-left" in second.continuity_notes
    context.shutdown()
