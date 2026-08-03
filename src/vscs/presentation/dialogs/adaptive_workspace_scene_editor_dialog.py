"""Scene Editor with resizable, collapsible and persistent workspace panels."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.guided_navigation_scene_editor_dialog import (
    GuidedNavigationSceneEditorDialog,
)
from vscs.presentation.workflow import CollapsibleWorkspacePanel


class AdaptiveWorkspaceSceneEditorDialog(GuidedNavigationSceneEditorDialog):
    """Prioritise the editing canvas while keeping guidance available on demand."""

    MAIN_SPLITTER_KEY = "scene_editor/adaptive/main_splitter"
    SUPPORT_SPLITTER_KEY = "scene_editor/adaptive/support_splitter"
    DOCUMENTATION_SPLITTER_KEY = "scene_editor/adaptive/documentation_splitter"
    WORKFLOW_COLLAPSED_KEY = "scene_editor/adaptive/workflow_collapsed"
    SUMMARY_COLLAPSED_KEY = "scene_editor/adaptive/summary_collapsed"
    VALIDATION_COLLAPSED_KEY = "scene_editor/adaptive/validation_collapsed"

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scene, parent, **kwargs)
        self._install_adaptive_workspace()
        self._restore_adaptive_workspace()
        self.setMinimumSize(760, 620)
        if self.width() < 1100 or self.height() < 760:
            self.resize(max(self.width(), 1100), max(self.height(), 760))

    def _install_adaptive_workspace(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Scene Editor root layout must be a QVBoxLayout.")

        workspace_widgets = (
            self.workflow_checklist,
            self.editor_splitter,
            self.summary_frame,
            self.validation_label,
        )
        indices = tuple(root.indexOf(widget) for widget in workspace_widgets)
        valid_indices = tuple(index for index in indices if index >= 0)
        if len(valid_indices) != len(workspace_widgets):
            raise RuntimeError("Scene Editor workspace widgets are incomplete.")
        insert_index = min(valid_indices)
        for widget in workspace_widgets:
            root.removeWidget(widget)

        self.workflow_panel = CollapsibleWorkspacePanel(
            "Scene creation progress",
            self.workflow_checklist,
            self,
            collapsed=True,
        )
        self.summary_panel = CollapsibleWorkspacePanel(
            "Scene summary",
            self.summary_frame,
            self,
            collapsed=True,
        )
        self.validation_panel = CollapsibleWorkspacePanel(
            "Validation",
            self.validation_label,
            self,
            collapsed=not bool(self.validation_explanations),
        )

        self.support_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.support_splitter.setObjectName("sceneEditorSupportSplitter")
        self.support_splitter.addWidget(self.summary_panel)
        self.support_splitter.addWidget(self.validation_panel)
        self.support_splitter.setCollapsible(0, True)
        self.support_splitter.setCollapsible(1, True)
        self.support_splitter.setSizes([55, 140])

        self.workspace_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.workspace_splitter.setObjectName("sceneEditorAdaptiveWorkspaceSplitter")
        self.workspace_splitter.addWidget(self.workflow_panel)
        self.workspace_splitter.addWidget(self.editor_splitter)
        self.workspace_splitter.addWidget(self.support_splitter)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setStretchFactor(2, 0)
        self.workspace_splitter.setCollapsible(0, True)
        self.workspace_splitter.setCollapsible(1, False)
        self.workspace_splitter.setCollapsible(2, True)
        self.workspace_splitter.setSizes([45, 650, 150])

        root.insertWidget(insert_index, self.workspace_splitter, 1)
        self._update_validation_panel_title()

    def _restore_adaptive_workspace(self) -> None:
        settings = self._workflow_settings
        self._restore_splitter(self.workspace_splitter, self.MAIN_SPLITTER_KEY)
        self._restore_splitter(self.support_splitter, self.SUPPORT_SPLITTER_KEY)
        self._restore_splitter(self.editor_splitter, self.DOCUMENTATION_SPLITTER_KEY)

        if settings.contains(self.WORKFLOW_COLLAPSED_KEY):
            self.workflow_panel.set_collapsed(
                settings.value(self.WORKFLOW_COLLAPSED_KEY, True, type=bool)
            )
        if settings.contains(self.SUMMARY_COLLAPSED_KEY):
            self.summary_panel.set_collapsed(
                settings.value(self.SUMMARY_COLLAPSED_KEY, True, type=bool)
            )
        if settings.contains(self.VALIDATION_COLLAPSED_KEY):
            self.validation_panel.set_collapsed(
                settings.value(self.VALIDATION_COLLAPSED_KEY, False, type=bool)
            )

    def _restore_splitter(self, splitter: QSplitter, key: str) -> None:
        state = self._workflow_settings.value(key)
        if isinstance(state, QByteArray) and not state.isEmpty():
            splitter.restoreState(state)

    def _save_adaptive_workspace(self) -> None:
        settings = self._workflow_settings
        settings.setValue(self.MAIN_SPLITTER_KEY, self.workspace_splitter.saveState())
        settings.setValue(self.SUPPORT_SPLITTER_KEY, self.support_splitter.saveState())
        settings.setValue(
            self.DOCUMENTATION_SPLITTER_KEY,
            self.editor_splitter.saveState(),
        )
        settings.setValue(self.WORKFLOW_COLLAPSED_KEY, self.workflow_panel.collapsed)
        settings.setValue(self.SUMMARY_COLLAPSED_KEY, self.summary_panel.collapsed)
        settings.setValue(self.VALIDATION_COLLAPSED_KEY, self.validation_panel.collapsed)
        settings.sync()

    def _validate(self) -> None:
        super()._validate()
        if hasattr(self, "validation_panel"):
            self._update_validation_panel_title()

    def _update_validation_panel_title(self) -> None:
        errors = sum(
            issue.severity.value == "error" for issue in self.validation_explanations
        )
        warnings = len(self.validation_explanations) - errors
        if errors:
            title = f"Validation · {errors} blocking issue{'s' if errors != 1 else ''}"
        elif warnings:
            title = f"Validation · {warnings} warning{'s' if warnings != 1 else ''}"
        else:
            title = "Validation · Ready to save"
        self.validation_panel.set_title(title)

    def done(self, result: int) -> None:
        """Persist the adaptive workspace before the dialog closes."""
        self._save_adaptive_workspace()
        super().done(result)
