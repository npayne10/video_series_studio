"""Scene Editor onboarding that guides users through creating a valid first scene."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.guided_tour_scene_editor_dialog import (
    GuidedTourSceneEditorDialog,
)
from vscs.presentation.dialogs.validation_explanations_scene_editor_dialog import (
    ValidationSeverity,
)


class GuidedFirstSceneEditorDialog(GuidedTourSceneEditorDialog):
    """Require essential first-scene actions while keeping optional steps gentle."""

    _ACTION_HINTS = {
        "production_type": "Confirm the production type, then continue.",
        "container_id": "Enter a valid container ID using letters, numbers and hyphens.",
        "scene_identity": (
            "Enter a short scene name and a screenplay heading before continuing."
        ),
        "location": "Select one canonical Location or Environment asset.",
        "validation": (
            "Complete the remaining required fields shown by Validation before continuing."
        ),
        "save": "Create the valid scene to finish this guided workflow.",
    }
    _REQUIRED_STEPS = frozenset(_ACTION_HINTS)

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        self._guided_action_active = False
        self._guided_step_id: str | None = None
        super().__init__(scene, parent, **kwargs)
        self.tour_overlay.next_requested.disconnect(self.onboarding.next)
        self.tour_overlay.next_requested.connect(self._advance_guided_first_scene)
        self.tour_overlay.try_requested.connect(self._begin_guided_action)
        self.onboarding.state_changed.connect(self._reset_action_for_step)
        self._connect_guided_action_signals()

    def _connect_guided_action_signals(self) -> None:
        self.production_type_combo.currentIndexChanged.connect(
            self._refresh_guided_action
        )
        self.episode_id_edit.textChanged.connect(self._refresh_guided_action)
        self.scene_name_edit.textChanged.connect(self._refresh_guided_action)
        self.heading_edit.textChanged.connect(self._refresh_guided_action)
        self.location_combo.currentIndexChanged.connect(self._refresh_guided_action)
        self.location_combo.currentTextChanged.connect(self._refresh_guided_action)
        self.summary_edit.textChanged.connect(self._refresh_guided_action)
        self.participant_list.itemChanged.connect(self._refresh_guided_action)
        self.asset_list.itemChanged.connect(self._refresh_guided_action)
        self.dialogue_editor.dialogue_list.model().rowsInserted.connect(
            self._refresh_guided_action
        )
        self.dialogue_editor.dialogue_list.model().rowsRemoved.connect(
            self._refresh_guided_action
        )
        self.duration_spin.valueChanged.connect(self._refresh_guided_action)

    def _show_active_tour_state(self) -> None:
        state = self.onboarding.state
        if not state.active or self._tour_suspended:
            return
        step = state.current_step
        if step is None:
            return

        ready = self._step_ready(step.step_id)
        if self._guided_action_active and not ready:
            self._route_action_target(step.step_id)
            return
        if self._guided_action_active and ready:
            self._guided_action_active = False

        super()._show_active_tour_state()
        required = step.step_id in self._REQUIRED_STEPS
        hint = self._step_hint(step.step_id, ready)
        self.tour_overlay.configure_action(
            required=required,
            ready=ready,
            hint=hint,
        )
        if state.is_final_step:
            self.tour_overlay.next_button.setText("Create Scene")

    def _step_ready(self, step_id: str) -> bool:
        if step_id == "production_type":
            return self.production_type_combo.currentIndex() >= 0
        if step_id == "container_id":
            container_id = self.episode_id_edit.text().strip().upper()
            return bool(container_id) and bool(
                self._CONTAINER_PATTERN.fullmatch(container_id)
            )
        if step_id == "scene_identity":
            return bool(
                self.scene_name_edit.text().strip()
                and self.heading_edit.text().strip()
            )
        if step_id == "location":
            return bool(self.selected_location_id())
        if step_id in {"validation", "save"}:
            return not any(
                issue.severity is ValidationSeverity.ERROR
                for issue in self.validation_explanations
            )
        return True

    def _step_hint(self, step_id: str, ready: bool) -> str:
        if step_id in {"participants", "required_assets", "dialogue"}:
            return "This step is optional for a scene that does not need it."
        if step_id == "production":
            return "The defaults are valid; adjust them when the story requires it."
        if ready and step_id in self._REQUIRED_STEPS:
            return "Completed. Select Next to continue."
        return self._ACTION_HINTS.get(step_id, "")

    def _begin_guided_action(self) -> None:
        state = self.onboarding.state
        step = state.current_step
        if step is None or self._step_ready(step.step_id):
            return
        self._guided_action_active = True
        self.tour_overlay.hide_tour()
        self._route_action_target(step.step_id)

    def _route_action_target(self, step_id: str) -> None:
        target = self._action_target(step_id)
        if target is None:
            return
        target.setFocus(Qt.FocusReason.OtherFocusReason)
        self.scroll_area.ensureWidgetVisible(target, 20, 20)
        topic = self._action_topic(step_id)
        if topic:
            self.show_live_topic(topic)

    def _action_target(self, step_id: str) -> QWidget | None:
        if step_id == "scene_identity":
            if not self.scene_name_edit.text().strip():
                return self.scene_name_edit
            return self.heading_edit
        if step_id in {"validation", "save"}:
            blocking = next(
                (
                    issue
                    for issue in self.validation_explanations
                    if issue.severity is ValidationSeverity.ERROR
                ),
                None,
            )
            return blocking.widget if blocking is not None else self.save_button
        target_id = {
            "production_type": "production_type",
            "container_id": "container_id",
            "location": "location",
        }.get(step_id)
        return self.workflow_navigator.target(target_id) if target_id else None

    def _action_topic(self, step_id: str) -> str | None:
        if step_id == "scene_identity":
            return (
                "scene.name"
                if not self.scene_name_edit.text().strip()
                else "scene.heading"
            )
        if step_id in {"validation", "save"}:
            blocking = next(
                (
                    issue
                    for issue in self.validation_explanations
                    if issue.severity is ValidationSeverity.ERROR
                ),
                None,
            )
            return blocking.topic_id if blocking is not None else "scene.summary"
        return {
            "production_type": "scene.production_type",
            "container_id": "scene.container_id",
            "location": "scene.location",
        }.get(step_id)

    def _refresh_guided_action(self, *_args: object) -> None:
        if not self.onboarding.state.active:
            return
        if self._guided_action_active and self.onboarding.state.current_step is not None:
            step_id = self.onboarding.state.current_step.step_id
            if self._step_ready(step_id):
                self._guided_action_active = False
                QTimer.singleShot(0, self._show_active_tour_state)
            return
        if self.tour_overlay.isVisible():
            QTimer.singleShot(0, self._show_active_tour_state)

    def _reset_action_for_step(self, state: object) -> None:
        del state
        current = self.onboarding.state.current_step
        step_id = current.step_id if current is not None else None
        if step_id != self._guided_step_id:
            self._guided_action_active = False
            self._guided_step_id = step_id

    def _advance_guided_first_scene(self) -> None:
        state = self.onboarding.state
        step = state.current_step
        if step is None or not state.active:
            return
        if not self._step_ready(step.step_id):
            self.tour_overlay.configure_action(
                required=True,
                ready=False,
                hint=self._step_hint(step.step_id, False),
            )
            return
        if state.is_final_step:
            self.onboarding.finish()
            self.tour_overlay.hide_tour()
            self.accept()
            return
        self.onboarding.next()
