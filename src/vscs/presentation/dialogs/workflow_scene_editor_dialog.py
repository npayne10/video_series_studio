"""Final scene-editor workflow and layout refinements."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.production_scene_editor_dialog import (
    ProductionSceneEditorDialog,
)


class WorkflowSceneEditorDialog(ProductionSceneEditorDialog):
    """Present a fast, self-explanatory scene creation and editing workflow."""

    GEOMETRY_KEY = "scene_editor/geometry"

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        *,
        settings: QSettings | None = None,
        **kwargs: object,
    ) -> None:
        self._workflow_settings = settings or QSettings(
            "VSCS",
            "VideoSeriesStudio",
        )
        super().__init__(scene, parent, **kwargs)
        self._install_workflow_ui(scene)
        self._restore_geometry()

    def _install_workflow_ui(self, scene: Scene | None) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return

        self.summary_frame = QFrame(self)
        self.summary_frame.setObjectName("sceneWorkflowSummary")
        self.summary_frame.setFrameShape(QFrame.Shape.StyledPanel)
        summary_layout = QVBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(12, 8, 12, 8)
        summary_layout.setSpacing(2)

        self.summary_title = QLabel("Scene summary", self.summary_frame)
        self.summary_title.setStyleSheet("font-weight: 600;")
        self.summary_label = QLabel(self.summary_frame)
        self.summary_label.setObjectName("sceneWorkflowSummaryText")
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        summary_layout.addWidget(self.summary_title)
        summary_layout.addWidget(self.summary_label)

        root.insertWidget(1, self.summary_frame)

        self.save_button.setText("Save Changes" if scene is not None else "Create Scene")
        self.save_button.setDefault(True)
        self.save_button.setAutoDefault(True)
        self.save_button.setToolTip("Save this scene and return to the Story Browser.")
        self.save_button.setAccessibleName(self.save_button.text())

        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setText("Cancel")
            cancel_button.setToolTip("Close without saving changes.")
            cancel_button.setAccessibleName("Cancel scene editing")

        self.save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        self.save_shortcut.activated.connect(self._save_from_shortcut)
        self.confirm_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.confirm_shortcut.activated.connect(self._save_from_shortcut)

        self._connect_summary_signals()
        self._update_workflow_summary()

    def _connect_summary_signals(self) -> None:
        self.scene_name_edit.textChanged.connect(self._update_workflow_summary)
        self.episode_id_edit.textChanged.connect(self._update_workflow_summary)
        self.sequence_spin.valueChanged.connect(self._update_workflow_summary)
        self.location_combo.currentIndexChanged.connect(self._update_workflow_summary)
        self.participant_list.itemChanged.connect(self._update_workflow_summary)
        self.asset_list.itemChanged.connect(self._update_workflow_summary)
        self.time_of_day_combo.currentIndexChanged.connect(self._update_workflow_summary)
        self.transition_combo.currentIndexChanged.connect(self._update_workflow_summary)
        self.duration_spin.valueChanged.connect(self._update_workflow_summary)

    def _update_workflow_summary(self) -> None:
        scene_name = self.scene_name_edit.text().strip() or "Untitled scene"
        episode = self.episode_id_edit.text().strip() or "No episode"
        sequence = self.sequence_spin.value()
        location = self.selected_location_id() or "No location selected"
        participants = len(self.selected_participant_ids())
        assets = len(self.selected_required_asset_ids())
        duration = self.duration_spin.value()
        time_of_day = self.time_of_day_combo.currentText()
        transition = self.transition_combo.currentText()

        self.summary_label.setText(
            f"{episode} · Scene {sequence:03d} · {scene_name}\n"
            f"{location} · {time_of_day} · {transition}\n"
            f"{participants} participants · {assets} required assets · "
            f"{duration:g} seconds"
        )

    def _save_from_shortcut(self) -> None:
        if self.save_button.isEnabled():
            self.accept()
            return
        self._focus_first_invalid_field()

    def _focus_first_invalid_field(self) -> None:
        candidates = (
            (self.scene_name_edit.text().strip(), self.scene_name_edit),
            (self.episode_id_edit.text().strip(), self.episode_id_edit),
            (self.heading_edit.text().strip(), self.heading_edit),
            (self.selected_location_id(), self.location_combo),
            (self.summary_edit.toPlainText().strip(), self.summary_edit),
        )
        for value, widget in candidates:
            if value:
                continue
            widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self.scroll_area.ensureWidgetVisible(widget, 16, 16)
            return

    def _restore_geometry(self) -> None:
        geometry = self._workflow_settings.value(self.GEOMETRY_KEY)
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)

    def _save_geometry(self) -> None:
        self._workflow_settings.setValue(self.GEOMETRY_KEY, self.saveGeometry())
        self._workflow_settings.sync()

    def done(self, result: int) -> None:
        """Persist the user's preferred editor size before closing."""
        self._save_geometry()
        super().done(result)
