"""Scene Editor with a live beginner workflow checklist."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.validation_explanations_scene_editor_dialog import (
    ValidationExplanationsSceneEditorDialog,
)
from vscs.presentation.workflow import (
    SCENE_WORKFLOW_STEPS,
    WorkflowProgressChecklist,
    WorkflowStepState,
)


class BeginnerWorkflowSceneEditorDialog(ValidationExplanationsSceneEditorDialog):
    """Show live scene-creation progress and the next recommended task."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scene, parent, **kwargs)
        self._install_workflow_checklist()
        self._connect_workflow_signals()
        self._update_workflow_progress()

    def _install_workflow_checklist(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Scene Editor root layout must be a QVBoxLayout.")
        self.workflow_checklist = WorkflowProgressChecklist(self)
        self.workflow_checklist.step_requested.connect(self._activate_workflow_step)
        editor_index = root.indexOf(self.editor_splitter)
        if editor_index < 0:
            raise RuntimeError("Scene Editor documentation splitter is unavailable.")
        root.insertWidget(editor_index, self.workflow_checklist)

    def _connect_workflow_signals(self) -> None:
        self.production_type_combo.currentIndexChanged.connect(self._update_workflow_progress)
        self.episode_id_edit.textChanged.connect(self._update_workflow_progress)
        self.scene_name_edit.textChanged.connect(self._update_workflow_progress)
        self.heading_edit.textChanged.connect(self._update_workflow_progress)
        self.location_combo.currentIndexChanged.connect(self._update_workflow_progress)
        self.location_combo.editTextChanged.connect(self._update_workflow_progress)
        self.summary_edit.textChanged.connect(self._update_workflow_progress)
        self.participant_list.itemChanged.connect(self._update_workflow_progress)
        self.asset_list.itemChanged.connect(self._update_workflow_progress)
        self.dialogue_editor.dialogue_list.model().rowsInserted.connect(
            self._update_workflow_progress
        )
        self.dialogue_editor.dialogue_list.model().rowsRemoved.connect(
            self._update_workflow_progress
        )
        self.time_of_day_combo.currentIndexChanged.connect(self._update_workflow_progress)
        self.transition_combo.currentIndexChanged.connect(self._update_workflow_progress)
        self.duration_spin.valueChanged.connect(self._update_workflow_progress)

    def _workflow_states(self) -> tuple[WorkflowStepState, ...]:
        participants_selected = bool(self.selected_participant_ids())
        assets_selected = bool(self.selected_required_asset_ids())
        dialogue_present = bool(self.dialogue_editor.dialogue_lines())
        has_participant_catalog = bool(self._participant_assets)
        has_required_asset_catalog = bool(self._required_assets)
        ready_to_save = self.save_button.isEnabled()
        blocking_issues = any(
            issue.severity.value == "error" for issue in self.validation_explanations
        )
        completed = {
            "production_type": self.production_type_combo.currentIndex() >= 0,
            "container_id": bool(self.episode_id_edit.text().strip()),
            "scene_identity": bool(
                self.scene_name_edit.text().strip() and self.heading_edit.text().strip()
            ),
            "location": bool(self.selected_location_id()),
            "summary": bool(self.summary_edit.toPlainText().strip()),
            "participants": (participants_selected or not has_participant_catalog or ready_to_save),
            "required_assets": (assets_selected or not has_required_asset_catalog or ready_to_save),
            "dialogue": dialogue_present or not participants_selected or ready_to_save,
            "production": bool(
                self.time_of_day_combo.currentText()
                and self.transition_combo.currentIndex() >= 0
                and self.duration_spin.value() > 0
            ),
            "validation": not blocking_issues,
        }
        return tuple(
            WorkflowStepState(step=step, completed=completed[step.step_id])
            for step in SCENE_WORKFLOW_STEPS
        )

    def _update_workflow_progress(self, *_args: object) -> None:
        if not hasattr(self, "workflow_checklist"):
            return
        self.workflow_checklist.update_states(self._workflow_states())

    def _activate_workflow_step(self, step_id: str) -> None:
        targets = {
            "production_type": self.production_type_combo,
            "container_id": self.episode_id_edit,
            "scene_identity": self.scene_name_edit,
            "location": self.location_combo,
            "summary": self.summary_edit,
            "participants": self.participant_search,
            "required_assets": self.asset_search,
            "dialogue": self.dialogue_editor.speaker_combo,
            "production": self.time_of_day_combo,
            "validation": self.validation_label,
        }
        topics = {step.step_id: step.topic_id for step in SCENE_WORKFLOW_STEPS}
        target = targets.get(step_id)
        if target is None:
            return
        if target is not self.validation_label:
            target.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.scroll_area.ensureWidgetVisible(target, 16, 16)
        topic_id = topics.get(step_id)
        if topic_id is not None:
            self.show_live_topic(topic_id)

    def _validate(self) -> None:
        super()._validate()
        self._update_workflow_progress()
