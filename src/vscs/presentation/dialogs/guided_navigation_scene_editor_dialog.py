"""Scene Editor with guided workflow navigation and VKF integration."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.beginner_workflow_scene_editor_dialog import (
    BeginnerWorkflowSceneEditorDialog,
)
from vscs.presentation.workflow import SCENE_WORKFLOW_STEPS, WorkflowNavigator


class GuidedNavigationSceneEditorDialog(BeginnerWorkflowSceneEditorDialog):
    """Navigate workflow steps to their exact controls with live guidance."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scene, parent, **kwargs)
        self.workflow_navigator = WorkflowNavigator(
            self.scroll_area,
            self.show_live_topic,
            self,
        )
        self.workflow_navigator.configure(
            self._workflow_targets(),
            {step.step_id: step.topic_id for step in SCENE_WORKFLOW_STEPS},
        )
        self.workflow_navigator.navigation_started.connect(self.workflow_checklist.set_active_step)

    def _workflow_targets(self) -> dict[str, QWidget]:
        """Return exact focus targets for every Scene Editor workflow step."""
        return {
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

    def _activate_workflow_step(self, step_id: str) -> None:
        """Route checklist activation through the reusable navigator."""
        self.workflow_navigator.navigate(step_id)
