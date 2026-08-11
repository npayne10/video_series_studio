from __future__ import annotations

from PySide6.QtWidgets import QLabel, QScrollArea

from vscs.application.story import (
    CameraAngle,
    CameraMovement,
    CameraPlan,
    LensFamily,
    ScreenDirection,
    ShotPlan,
    ShotPlanStatus,
    ShotSize,
)
from vscs.presentation.widgets.governed_camera_planner import CameraPlanEditorDialog


class FakeCameraService:
    def available_camera_profiles(self):
        return ()


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Orbital arrival",
        narrative_purpose="Establish Xorix",
        production_objective="Show physically credible orbital scale",
        target_runtime_seconds=12,
        required_action="Ship crosses the frame in stable orbit",
        scene_contract_hash="scene",
        status=ShotPlanStatus.READY,
    )


def _plan() -> CameraPlan:
    return CameraPlan(
        camera_plan_id="EP-001-SCN-001-SHT-001-CAM",
        shot_id="EP-001-SCN-001-SHT-001",
        shot_size=ShotSize.WIDE,
        angle=CameraAngle.EYE_LEVEL,
        movement=CameraMovement.TRACK,
        lens_family=LensFamily.WIDE,
        focal_length_mm=35,
        camera_height_m=1.6,
        screen_direction=ScreenDirection.LEFT_TO_RIGHT,
        composition="Preserve spacecraft scale against the planetary horizon",
        focus_strategy="Maintain readable depth across spacecraft and horizon",
        movement_notes="Track smoothly at constant speed",
        continuity_notes="Preserve left-to-right travel",
        camera_constraints=("No impossible acceleration",),
    )


def test_camera_editor_is_resizable_scrollable_and_specialist_scoped(qtbot) -> None:
    dialog = CameraPlanEditorDialog(
        FakeCameraService(),  # type: ignore[arg-type]
        _shot(),
        _plan(),
    )
    qtbot.addWidget(dialog)

    scroll = dialog.findChild(QScrollArea)
    assert scroll is not None
    assert dialog.minimumWidth() <= 660
    assert dialog.minimumHeight() <= 520
    rendered = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Lighting" not in rendered
    assert "Environment" not in rendered


def test_camera_editor_round_trips_structured_camera_values(qtbot) -> None:
    dialog = CameraPlanEditorDialog(
        FakeCameraService(),  # type: ignore[arg-type]
        _shot(),
        _plan(),
    )
    qtbot.addWidget(dialog)

    values = dialog.values()

    assert values.shot_size is ShotSize.WIDE
    assert values.movement is CameraMovement.TRACK
    assert values.focal_length_mm == 35
    assert values.camera_height_m == 1.6
    assert values.screen_direction is ScreenDirection.LEFT_TO_RIGHT
    assert values.camera_constraints == ("No impossible acceleration",)
