"""Tests for Phase 16.2a.8.5.4.3 guided Scene Editor tour."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vscs.presentation.dialogs.guided_tour_scene_editor_dialog import (
    GuidedTourSceneEditorDialog,
)
from vscs.presentation.onboarding import OnboardingOutcome


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "guided-tour.ini"), QSettings.Format.IniFormat)


def _start_tour(
    dialog: GuidedTourSceneEditorDialog,
    qapp: QApplication,
) -> None:
    dialog.show()
    qapp.processEvents()
    assert dialog.welcome_overlay.isVisible()
    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()


def test_start_guide_opens_visible_first_tour_step(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedTourSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    _start_tour(dialog, qapp)

    assert dialog.onboarding.state.active
    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.progress_label.text() == "Step 1 of 11"
    assert dialog.tour_overlay.title_label.text() == "Welcome to the Scene Editor"
    assert not dialog.tour_overlay.previous_button.isEnabled()
    assert dialog.tour_overlay.next_button.text() == "Next"


def test_next_and_previous_route_spotlight_and_live_documentation(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedTourSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_tour(dialog, qapp)

    dialog.tour_overlay.next_button.click()
    qapp.processEvents()

    assert dialog.onboarding.state.current_index == 1
    assert dialog.tour_overlay.title_label.text() == "Choose the production type"
    assert not dialog.tour_overlay.spotlight_rect.isNull()
    assert dialog.documentation_panel.topic_id == "scene.production_type"
    assert dialog.workflow_checklist.active_step_id == "production_type"
    assert dialog.tour_overlay.previous_button.isEnabled()

    dialog.tour_overlay.previous_button.click()
    qapp.processEvents()

    assert dialog.onboarding.state.current_index == 0
    assert dialog.tour_overlay.title_label.text() == "Welcome to the Scene Editor"


def test_tour_navigation_targets_scene_controls_in_sequence(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedTourSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_tour(dialog, qapp)

    dialog.onboarding.go_to(4)
    qapp.processEvents()

    assert dialog.tour_overlay.title_label.text() == "Choose the primary location"
    assert dialog.documentation_panel.topic_id == "scene.location"
    assert dialog.workflow_navigator.target("location") is dialog.location_combo
    assert dialog.location_combo.property("workflowGuidedTarget") is True


def test_skip_hides_tour_and_persists_outcome(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    dialog = GuidedTourSceneEditorDialog(settings=settings)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_tour(dialog, qapp)

    dialog.tour_overlay.skip_button.click()
    qapp.processEvents()

    assert not dialog.tour_overlay.isVisible()
    assert dialog.onboarding.state.outcome is OnboardingOutcome.SKIPPED

    restored = GuidedTourSceneEditorDialog(settings=settings)
    qtbot.addWidget(restored)  # type: ignore[attr-defined]
    restored.show()
    qapp.processEvents()
    assert not restored.welcome_overlay.isVisible()


def test_final_step_uses_finish_and_persists_completion(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    dialog = GuidedTourSceneEditorDialog(settings=settings)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_tour(dialog, qapp)

    dialog.onboarding.go_to(dialog.onboarding.sequence.total_steps - 1)
    qapp.processEvents()

    assert dialog.tour_overlay.next_button.text() == "Finish"
    dialog.tour_overlay.next_button.click()
    qapp.processEvents()

    assert not dialog.tour_overlay.isVisible()
    assert dialog.onboarding.state.outcome is OnboardingOutcome.COMPLETED
    assert dialog.workflow_checklist.active_step_id is None


def test_restart_returns_to_welcome_before_replaying_tour(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedTourSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_tour(dialog, qapp)
    dialog.tour_overlay.skip_button.click()

    dialog.restart_tour_button.click()
    qapp.processEvents()

    assert dialog.welcome_overlay.isVisible()
    assert not dialog.tour_overlay.isVisible()
    assert dialog.onboarding.state.active

    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.tour_overlay.isVisible()
    assert dialog.onboarding.state.current_index == 0
