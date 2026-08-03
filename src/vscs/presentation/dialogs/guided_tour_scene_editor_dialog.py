"""Scene Editor with a visible spotlight-driven onboarding tour."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.onboarding_welcome_scene_editor_dialog import (
    OnboardingWelcomeSceneEditorDialog,
)
from vscs.presentation.onboarding import GuidedTourOverlay, OnboardingState


class GuidedTourSceneEditorDialog(OnboardingWelcomeSceneEditorDialog):
    """Present the active onboarding sequence as an interactive interface tour."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        self._tour_suspended = False
        super().__init__(scene, parent, **kwargs)
        self.tour_overlay = GuidedTourOverlay(self)
        self.tour_overlay.previous_requested.connect(self.onboarding.previous)
        self.tour_overlay.next_requested.connect(self.onboarding.next)
        self.tour_overlay.skip_requested.connect(self._skip_active_tour)
        self.onboarding.state_changed.connect(self._onboarding_state_changed)

    def _start_onboarding(self) -> None:
        """Start the sequence and immediately display its first tour card."""
        if not self.beginner_mode.enabled:
            self.beginner_mode_checkbox.setChecked(True)
        super()._start_onboarding()
        self._show_active_tour_state()

    def _onboarding_state_changed(self, state: OnboardingState) -> None:
        if self._tour_suspended:
            return
        if not state.active:
            self.tour_overlay.hide_tour()
            self.workflow_navigator.clear_highlight()
            self.workflow_checklist.set_active_step(None)
            return
        QTimer.singleShot(0, self._show_active_tour_state)

    def _show_active_tour_state(self) -> None:
        state = self.onboarding.state
        if not state.active or self._tour_suspended:
            return
        step = state.current_step
        if step is None:
            return

        target = None
        if step.target_id is not None:
            if step.target_id == "validation":
                self.validation_panel.set_collapsed(False)
            self.workflow_navigator.navigate(step.target_id)
            target = self.workflow_navigator.target(step.target_id)
        elif step.topic_id is not None:
            self.show_live_topic(step.topic_id)

        self.tour_overlay.show_state(state, target)

    def _skip_active_tour(self) -> None:
        if self.onboarding.state.active:
            self.onboarding.skip()
        self.tour_overlay.hide_tour()

    def restart_onboarding(self) -> None:
        """Return to the welcome card before replaying the guided tour."""
        self._tour_suspended = True
        self.tour_overlay.hide_tour()
        try:
            super().restart_onboarding()
        finally:
            self._tour_suspended = False
