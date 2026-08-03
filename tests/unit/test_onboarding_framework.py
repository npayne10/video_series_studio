"""Tests for Phase 16.2a.8.5.4.1 reusable onboarding framework."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from vscs.presentation.onboarding import (
    OnboardingController,
    OnboardingOutcome,
    OnboardingSequence,
    OnboardingStep,
)


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "onboarding.ini"), QSettings.Format.IniFormat)


def _sequence(*, version: int = 1) -> OnboardingSequence:
    return OnboardingSequence(
        guide_id="scene-editor",
        title="Scene Editor Tour",
        version=version,
        steps=(
            OnboardingStep(
                "welcome",
                "Welcome",
                "Learn how to create a production scene.",
            ),
            OnboardingStep(
                "identity",
                "Scene identity",
                "Choose a production container and identify the scene.",
                topic_id="scene.production_type",
                target_id="production_type",
            ),
            OnboardingStep(
                "save",
                "Save the scene",
                "Resolve validation issues and save the scene.",
                topic_id="scene.summary",
                target_id="validation",
            ),
        ),
    )


def test_step_and_sequence_validate_required_identity() -> None:
    with pytest.raises(ValueError, match="step ID"):
        OnboardingStep("", "Title", "Description")
    with pytest.raises(ValueError, match="at least one step"):
        OnboardingSequence("guide", "Guide", ())
    with pytest.raises(ValueError, match="unique"):
        OnboardingSequence(
            "guide",
            "Guide",
            (
                OnboardingStep("same", "One", "First"),
                OnboardingStep("same", "Two", "Second"),
            ),
        )


def test_sequence_exposes_ordered_steps_and_bounds() -> None:
    sequence = _sequence()

    assert sequence.total_steps == 3
    assert sequence.step(1).step_id == "identity"
    with pytest.raises(IndexError, match="out of range"):
        sequence.step(3)


def test_controller_starts_with_first_step_and_progress(tmp_path: Path) -> None:
    controller = OnboardingController(_sequence(), _settings(tmp_path))

    assert controller.should_start_automatically
    assert controller.start()

    state = controller.state
    assert state.active
    assert state.current_index == 0
    assert state.current_step is not None
    assert state.current_step.step_id == "welcome"
    assert not state.can_go_previous
    assert state.can_go_next
    assert state.progress_percent == 33


def test_previous_next_and_direct_navigation_respect_boundaries(tmp_path: Path) -> None:
    controller = OnboardingController(_sequence(), _settings(tmp_path))
    controller.start()

    assert not controller.previous()
    assert controller.next()
    assert controller.state.current_index == 1
    assert controller.state.can_go_previous
    assert controller.go_to(2)
    assert controller.state.is_final_step
    assert not controller.go_to(99)
    assert controller.previous()
    assert controller.state.current_index == 1


def test_next_from_final_step_finishes_and_persists(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    controller = OnboardingController(_sequence(), settings)
    controller.start()
    controller.go_to(2)

    assert controller.next()
    assert not controller.state.active
    assert controller.state.outcome is OnboardingOutcome.COMPLETED
    assert not controller.should_start_automatically

    restored = OnboardingController(_sequence(), settings)
    assert restored.state.outcome is OnboardingOutcome.COMPLETED
    assert not restored.should_start_automatically
    assert not restored.start()


def test_skip_persists_and_prevents_automatic_restart(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    controller = OnboardingController(_sequence(), settings)
    controller.start()

    assert controller.skip()
    assert controller.state.outcome is OnboardingOutcome.SKIPPED

    restored = OnboardingController(_sequence(), settings)
    assert restored.state.outcome is OnboardingOutcome.SKIPPED
    assert not restored.start()


def test_restart_clears_terminal_outcome_and_starts_first_step(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    controller = OnboardingController(_sequence(), settings)
    controller.start()
    controller.skip()

    controller.restart()

    assert controller.state.active
    assert controller.state.current_index == 0
    assert controller.state.outcome is None
    assert controller.should_start_automatically


def test_reset_clears_persistence_without_starting(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    controller = OnboardingController(_sequence(), settings)
    controller.start()
    controller.finish()

    controller.reset()

    assert not controller.state.active
    assert controller.state.outcome is None
    assert controller.should_start_automatically
    restored = OnboardingController(_sequence(), settings)
    assert restored.should_start_automatically


def test_completion_is_versioned_per_guide(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first_version = OnboardingController(_sequence(version=1), settings)
    first_version.start()
    first_version.finish()

    second_version = OnboardingController(_sequence(version=2), settings)

    assert second_version.should_start_automatically
    assert second_version.state.outcome is None


def test_controller_emits_navigation_and_terminal_signals(
    qtbot: object,
    tmp_path: Path,
) -> None:
    controller = OnboardingController(_sequence(), _settings(tmp_path))

    with qtbot.waitSignal(  # type: ignore[attr-defined]
        controller.guide_started,
        timeout=500,
    ):
        controller.start()
    with qtbot.waitSignal(  # type: ignore[attr-defined]
        controller.state_changed,
        timeout=500,
    ):
        controller.next()
    with qtbot.waitSignal(  # type: ignore[attr-defined]
        controller.guide_skipped,
        timeout=500,
    ):
        controller.skip()

    controller.restart()
    with qtbot.waitSignal(  # type: ignore[attr-defined]
        controller.guide_completed,
        timeout=500,
    ):
        controller.finish()


def test_inactive_controller_rejects_navigation_and_terminal_actions(
    tmp_path: Path,
) -> None:
    controller = OnboardingController(_sequence(), _settings(tmp_path))

    assert not controller.next()
    assert not controller.previous()
    assert not controller.go_to(1)
    assert not controller.skip()
    assert not controller.finish()
