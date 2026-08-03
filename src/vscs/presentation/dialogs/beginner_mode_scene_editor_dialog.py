"""Scene Editor with optional, persisted beginner workflow guidance."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QVBoxLayout, QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.adaptive_workspace_scene_editor_dialog import (
    AdaptiveWorkspaceSceneEditorDialog,
)
from vscs.presentation.workflow import BeginnerModeController


class BeginnerModeSceneEditorDialog(AdaptiveWorkspaceSceneEditorDialog):
    """Allow users to switch guided workflow assistance on or off."""

    BEGINNER_MODE_KEY = "scene_editor/beginner_mode_enabled"

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scene, parent, **kwargs)
        self.beginner_mode = BeginnerModeController(
            self._workflow_settings,
            self.BEGINNER_MODE_KEY,
            self,
        )
        self._install_beginner_mode_control()
        self.beginner_mode.enabled_changed.connect(self._apply_beginner_mode)
        self._apply_beginner_mode(self.beginner_mode.enabled)

    def _install_beginner_mode_control(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Scene Editor root layout must be a QVBoxLayout.")

        self.beginner_mode_checkbox = QCheckBox("Beginner Mode", self)
        self.beginner_mode_checkbox.setObjectName("sceneEditorBeginnerMode")
        self.beginner_mode_checkbox.setToolTip(
            "Show the guided scene-creation checklist and next-step recommendations."
        )
        self.beginner_mode_checkbox.setAccessibleName("Enable Beginner Mode")
        self.beginner_mode_checkbox.setChecked(self.beginner_mode.enabled)
        self.beginner_mode_checkbox.toggled.connect(self.beginner_mode.set_enabled)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)
        row.addWidget(self.beginner_mode_checkbox)

        workspace_index = root.indexOf(self.workspace_splitter)
        if workspace_index < 0:
            raise RuntimeError("Adaptive Scene Editor workspace is unavailable.")
        root.insertLayout(workspace_index, row)

    def _apply_beginner_mode(self, enabled: bool) -> None:
        """Show or hide guided workflow assistance without affecting core help."""
        self.workflow_panel.setVisible(enabled)
        self.workflow_checklist.setEnabled(enabled)
        if not enabled:
            self.workflow_navigator.clear_highlight()
            self.workflow_checklist.set_active_step(None)
        self.beginner_mode_checkbox.setChecked(enabled)
        self.workspace_splitter.updateGeometry()
