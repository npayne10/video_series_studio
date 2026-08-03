"""Tests for Phase 16.2a.8.5.4.2 Scene Editor welcome experience."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vscs.presentation.dialogs.onboarding_welcome_scene_editor_dialog import (
    OnboardingWelcomeSceneEditorDialog,
)
from vscs.presentation.onboarding import OnboardingOutcome


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "welcome.ini"), QSettings.Format.IniFormat)


def _show(
    dialog: OnboardingWelcomeSceneEditorDialog,
    qapp: QApplication,
) -> None:
    dialog.show()
    qapp.processEvents()
    qapp.processEvents()


def test_first_run_shows_welcome_overlay(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = OnboardingWelcomeSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    _show(dialog, qapp)

    assert dialog.welcome_overlay.isVisible()
    assert dialog.welcome_overlay.start_button.hasFocus()
    assert "Welcome to the VSCS Scene Editor" in dialog.welcome_overlay.accessibleName()
    assert dialog.onboarding.should_start_automatically


def test_start_guide_activates_sequence_and_hands_off_to_beginner_mode(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = OnboardingWelcomeSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()

    assert not dialog.welcome_overlay.isVisible()
    assert dialog.onboarding.state.active
    assert dialog.onboarding.state.current_index == 0
    assert not dialog.workflow_panel.collapsed
    assert dialog.workflow_panel.isVisible()


def test_skip_persists_and_prevents_future_automatic_welcome(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    first = OnboardingWelcomeSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    _show(first, qapp)

    first.welcome_overlay.skip_button.click()
    qapp.processEvents()

    assert first.onboarding.state.outcome is OnboardingOutcome.SKIPPED
    assert not first.welcome_overlay.isVisible()

    second = OnboardingWelcomeSceneEditorDialog(settings=settings)
    qtbot.addWidget(second)  # type: ignore[attr-defined]
    _show(second, qapp)

    assert not second.welcome_overlay.isVisible()
    assert not second.onboarding.should_start_automatically


def test_completed_guide_does_not_show_automatically(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    first = OnboardingWelcomeSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    first.onboarding.start(force=True)
    first.onboarding.finish()

    second = OnboardingWelcomeSceneEditorDialog(settings=settings)
    qtbot.addWidget(second)  # type: ignore[attr-defined]
    _show(second, qapp)

    assert not second.welcome_overlay.isVisible()
    assert second.onboarding.state.outcome is OnboardingOutcome.COMPLETED


def test_restart_action_replays_welcome_after_skip(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    dialog = OnboardingWelcomeSceneEditorDialog(settings=settings)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)
    dialog.welcome_overlay.skip_button.click()

    dialog.restart_tour_button.click()
    qapp.processEvents()

    assert dialog.welcome_overlay.isVisible()
    assert dialog.onboarding.state.active
    assert dialog.onboarding.state.outcome is None
    assert dialog.onboarding.state.current_index == 0


def test_expert_mode_suppresses_automatic_welcome_but_keeps_restart(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    settings.setValue(OnboardingWelcomeSceneEditorDialog.BEGINNER_MODE_KEY, False)
    dialog = OnboardingWelcomeSceneEditorDialog(settings=settings)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    _show(dialog, qapp)

    assert not dialog.welcome_overlay.isVisible()
    assert dialog.restart_tour_button.isVisible()
    dialog.restart_tour_button.click()
    qapp.processEvents()
    assert dialog.welcome_overlay.isVisible()


def test_overlay_tracks_dialog_size(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = OnboardingWelcomeSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    dialog.resize(960, 680)
    qapp.processEvents()

    assert dialog.welcome_overlay.geometry() == dialog.rect()
