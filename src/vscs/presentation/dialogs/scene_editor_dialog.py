"""Dialog for creating and editing structured SSIE scenes."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from vscs.application.ssie import Scene, SceneTransition


class SceneEditorDialog(QDialog):
    """Collect structured scene data suitable for the SSIE planner."""

    def __init__(self, scene: Scene | None = None, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setWindowTitle("Edit Scene" if scene is not None else "New Scene")
        self.resize(640, 620)

        self.scene_id_edit = QLineEdit()
        self.episode_id_edit = QLineEdit("EP-001")
        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(1, 9999)
        self.heading_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.summary_edit = QPlainTextEdit()
        self.participants_edit = QPlainTextEdit()
        self.dialogue_edit = QPlainTextEdit()
        self.assets_edit = QPlainTextEdit()
        self.time_of_day_edit = QLineEdit()
        self.transition_combo = QComboBox()
        for transition in SceneTransition:
            self.transition_combo.addItem(transition.value.replace("_", " ").title(), transition)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 36000.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setValue(30.0)

        form = QFormLayout()
        form.addRow("Scene ID", self.scene_id_edit)
        form.addRow("Episode ID", self.episode_id_edit)
        form.addRow("Sequence", self.sequence_spin)
        form.addRow("Heading", self.heading_edit)
        form.addRow("Location asset ID", self.location_edit)
        form.addRow("Summary", self.summary_edit)
        form.addRow("Participants (one per line)", self.participants_edit)
        form.addRow("Dialogue (one line per utterance)", self.dialogue_edit)
        form.addRow("Required assets (one per line)", self.assets_edit)
        form.addRow("Time of day", self.time_of_day_edit)
        form.addRow("Transition", self.transition_combo)
        form.addRow("Estimated duration (seconds)", self.duration_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if scene is not None:
            self._load(scene)

    def scene(self) -> Scene:
        """Return the structured scene represented by the form."""
        return Scene(
            scene_id=self.scene_id_edit.text().strip(),
            episode_id=self.episode_id_edit.text().strip(),
            sequence_number=self.sequence_spin.value(),
            heading=self.heading_edit.text().strip(),
            location_asset_id=self.location_edit.text().strip(),
            summary=self.summary_edit.toPlainText().strip(),
            participant_asset_ids=self._lines(self.participants_edit.toPlainText()),
            dialogue=self._lines(self.dialogue_edit.toPlainText()),
            required_asset_ids=self._lines(self.assets_edit.toPlainText()),
            time_of_day=self.time_of_day_edit.text().strip() or None,
            transition_in=self.transition_combo.currentData(),
            estimated_duration_seconds=self.duration_spin.value(),
        )

    def _load(self, scene: Scene) -> None:
        self.scene_id_edit.setText(scene.scene_id)
        self.episode_id_edit.setText(scene.episode_id)
        self.sequence_spin.setValue(scene.sequence_number)
        self.heading_edit.setText(scene.heading)
        self.location_edit.setText(scene.location_asset_id)
        self.summary_edit.setPlainText(scene.summary)
        self.participants_edit.setPlainText("\n".join(scene.participant_asset_ids))
        self.dialogue_edit.setPlainText("\n".join(scene.dialogue))
        self.assets_edit.setPlainText("\n".join(scene.required_asset_ids))
        self.time_of_day_edit.setText(scene.time_of_day or "")
        self.transition_combo.setCurrentIndex(self.transition_combo.findData(scene.transition_in))
        self.duration_spin.setValue(scene.estimated_duration_seconds or 30.0)

    @staticmethod
    def _lines(value: str) -> tuple[str, ...]:
        return tuple(line.strip() for line in value.splitlines() if line.strip())
