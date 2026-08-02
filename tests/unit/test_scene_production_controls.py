"""Tests for Phase 16.2a.6 scene production controls."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from vscs.application.ssie import Scene, SceneTransition
from vscs.presentation.dialogs.production_scene_editor_dialog import (
    ProductionSceneEditorDialog,
)


def test_time_of_day_uses_controlled_values(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    values = [
        dialog.time_of_day_combo.itemData(index)
        for index in range(dialog.time_of_day_combo.count())
    ]

    assert None in values
    assert "dawn" in values
    assert "night" in values
    assert "continuous" in values


def test_duration_presets_update_runtime_and_estimates(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionSceneEditorDialog(frames_per_second=24.0)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    preset_index = dialog.duration_preset_combo.findData(60.0)
    assert preset_index >= 0
    dialog.duration_preset_combo.setCurrentIndex(preset_index)

    assert dialog.duration_spin.value() == 60.0
    assert "8 shots" in dialog.production_estimate_label.text()
    assert "1,440 frames" in dialog.production_estimate_label.text()
    assert "24 fps" in dialog.production_estimate_label.text()


def test_manual_duration_selects_custom_and_updates_frame_count(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionSceneEditorDialog(frames_per_second=25.0)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.duration_spin.setValue(42.0)

    assert dialog.duration_preset_combo.currentData() is None
    assert "1,050 frames" in dialog.production_estimate_label.text()
    assert "25 fps" in dialog.production_estimate_label.text()


def test_scene_round_trips_production_metadata(
    qtbot: object,
    qapp: QApplication,
) -> None:
    scene = Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="EXT. XORIX SPACEPORT - DUSK",
        location_asset_id="LOC-XORIX-SPACEPORT",
        summary="The delegation arrives at the Xorix spaceport.",
        time_of_day="dusk",
        transition_in=SceneTransition.DISSOLVE,
        estimated_duration_seconds=90.0,
        scene_name="Arrival at Xorix",
    )
    dialog = ProductionSceneEditorDialog(scene)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    result = dialog.scene()

    assert result.time_of_day == "dusk"
    assert result.transition_in is SceneTransition.DISSOLVE
    assert result.estimated_duration_seconds == 90.0
    assert dialog.duration_preset_combo.currentData() == 90.0


def test_transition_selector_contains_all_supported_transitions(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    values = {
        dialog.transition_combo.itemData(index)
        for index in range(dialog.transition_combo.count())
    }

    assert values == set(SceneTransition)
