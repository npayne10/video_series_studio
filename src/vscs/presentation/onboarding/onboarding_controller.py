"""Reusable onboarding progress, navigation, and persistence controller."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, QSettings, Signal

from .onboarding_steps import OnboardingSequence, OnboardingStep


class OnboardingOutcome(StrEnum):
    """Persisted terminal result of an onboarding guide."""

    COMPLETED = "completed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class OnboardingState:
    """Immutable snapshot of one guide's current progress."""

    guide_id: str
    active: bool
    current_index: int
    total_steps: int
    current_step: OnboardingStep | None
    can_go_previous: bool
    can_go_next: bool
    is_final_step: bool
    progress_percent: int
    outcome: OnboardingOutcome | None = None


class OnboardingController(QObject):
    """Manage one onboarding sequence without depending on a specific UI."""

    state_changed = Signal(object)
    guide_started = Signal(str)
    guide_completed = Signal(str)
    guide_skipped = Signal(str)

    def __init__(
        self,
        sequence: OnboardingSequence,
        settings: QSettings,
        parent: QObject | None = None,
        *,
        settings_prefix: str = "onboarding",
    ) -> None:
        super().__init__(parent)
        self.sequence = sequence
        self._settings = settings
        self._settings_prefix = settings_prefix.rstrip("/")
        self._active = False
        self._current_index = 0
        self._outcome = self._stored_outcome()

    @property
    def state(self) -> OnboardingState:
        """Return the current immutable progress snapshot."""
        step = self.sequence.step(self._current_index) if self._active else None
        total = self.sequence.total_steps
        progress = round(((self._current_index + 1) / total) * 100) if self._active else 0
        return OnboardingState(
            guide_id=self.sequence.guide_id,
            active=self._active,
            current_index=self._current_index,
            total_steps=total,
            current_step=step,
            can_go_previous=self._active and self._current_index > 0,
            can_go_next=self._active and self._current_index < total - 1,
            is_final_step=self._active and self._current_index == total - 1,
            progress_percent=progress,
            outcome=self._outcome,
        )

    @property
    def should_start_automatically(self) -> bool:
        """Return whether the guide has not been completed or skipped for this version."""
        return self._outcome is None

    def start(self, *, force: bool = False) -> bool:
        """Start at the first step and return whether the guide became active."""
        if not force and not self.should_start_automatically:
            return False
        self._active = True
        self._current_index = 0
        self.guide_started.emit(self.sequence.guide_id)
        self._emit_state()
        return True

    def next(self) -> bool:
        """Advance one step, or finish when already on the final step."""
        if not self._active:
            return False
        if self._current_index >= self.sequence.total_steps - 1:
            return self.finish()
        self._current_index += 1
        self._emit_state()
        return True

    def previous(self) -> bool:
        """Move to the previous step when possible."""
        if not self._active or self._current_index <= 0:
            return False
        self._current_index -= 1
        self._emit_state()
        return True

    def go_to(self, index: int) -> bool:
        """Move directly to a valid step index."""
        if not self._active or index < 0 or index >= self.sequence.total_steps:
            return False
        if index == self._current_index:
            return True
        self._current_index = index
        self._emit_state()
        return True

    def skip(self) -> bool:
        """Stop the guide and persist that the user skipped it."""
        if not self._active:
            return False
        self._active = False
        self._outcome = OnboardingOutcome.SKIPPED
        self._persist_outcome(self._outcome)
        self.guide_skipped.emit(self.sequence.guide_id)
        self._emit_state()
        return True

    def finish(self) -> bool:
        """Complete the guide and persist successful completion."""
        if not self._active:
            return False
        self._active = False
        self._outcome = OnboardingOutcome.COMPLETED
        self._persist_outcome(self._outcome)
        self.guide_completed.emit(self.sequence.guide_id)
        self._emit_state()
        return True

    def restart(self) -> None:
        """Clear any prior outcome and start the guide from the beginning."""
        self._clear_persisted_outcome()
        self._outcome = None
        self.start(force=True)

    def reset(self) -> None:
        """Clear persisted progress without starting the guide."""
        self._active = False
        self._current_index = 0
        self._outcome = None
        self._clear_persisted_outcome()
        self._emit_state()

    def _settings_key(self, name: str) -> str:
        return f"{self._settings_prefix}/{self.sequence.guide_id}/v{self.sequence.version}/{name}"

    def _stored_outcome(self) -> OnboardingOutcome | None:
        raw = self._settings.value(self._settings_key("outcome"), "", type=str)
        try:
            return OnboardingOutcome(raw) if raw else None
        except ValueError:
            return None

    def _persist_outcome(self, outcome: OnboardingOutcome) -> None:
        self._settings.setValue(self._settings_key("outcome"), outcome.value)
        self._settings.sync()

    def _clear_persisted_outcome(self) -> None:
        self._settings.remove(self._settings_key("outcome"))
        self._settings.sync()

    def _emit_state(self) -> None:
        self.state_changed.emit(self.state)
