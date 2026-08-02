"""Dialog for creating and editing structured SSIE scenes."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.application.ssie import Scene, SceneTransition


class SceneEditorDialog(QDialog):
    """Collect clear, validated scene data suitable for the SSIE planner."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        *,
        default_episode_id: str = "EP-001",
        suggested_sequence: int = 1,
        scene_id_factory: Callable[[str, int], str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._editing = scene is not None
        self._scene_id_factory = scene_id_factory or self._default_scene_id
        self.setWindowTitle("Edit Scene" if self._editing else "New Scene")
        self.resize(680, 700)

        intro = QLabel(
            "Create the story-level scene information used by SSIE. "
            "Fields marked * are required."
        )
        intro.setWordWrap(True)

        self.scene_id_edit = QLineEdit()
        self.scene_id_edit.setReadOnly(True)
        self.scene_id_edit.setToolTip(
            "Internal VSCS identity. It is generated automatically and cannot be renamed."
        )
        self.scene_name_edit = QLineEdit()
        self.scene_name_edit.setPlaceholderText("Example: Emergence at Xorix")
        self.scene_name_edit.setToolTip(
            "A short human-readable name shown in the Story Browser."
        )
        self.episode_id_edit = QLineEdit(default_episode_id)
        self.episode_id_edit.setPlaceholderText("EP-001")
        self.episode_id_edit.setToolTip(
            "Episode identity containing this scene, for example EP-001."
        )
        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(1, 9999)
        self.sequence_spin.setValue(suggested_sequence)
        self.sequence_spin.setToolTip("The scene's order within the episode.")
        self.heading_edit = QLineEdit()
        self.heading_edit.setPlaceholderText("INT. MAURITANIA BRIDGE - NIGHT")
        self.heading_edit.setToolTip(
            "Screenplay-style heading describing interior/exterior, location and time."
        )
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Select a location in Phase 16.2a.2")
        self.location_edit.setToolTip("Canonical location asset ID used by this scene.")
        self.summary_edit = QPlainTextEdit()
        self.summary_edit.setPlaceholderText(
            "Describe what changes in this scene and why it matters."
        )
        self.summary_edit.setToolTip(
            "A concise narrative summary used by SSIE to infer scene purpose and shots."
        )
        self.participants_edit = QPlainTextEdit()
        self.dialogue_edit = QPlainTextEdit()
        self.assets_edit = QPlainTextEdit()
        self.time_of_day_edit = QLineEdit()
        self.transition_combo = QComboBox()
        for transition in SceneTransition:
            self.transition_combo.addItem(
                transition.value.replace("_", " ").title(),
                transition,
            )
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 36000.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setValue(30.0)

        self.validation_label = QLabel()
        self.validation_label.setObjectName("sceneValidationMessage")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("color: #b00020;")

        form = QFormLayout()
        form.addRow("Scene ID", self.scene_id_edit)
        form.addRow("Scene name *", self.scene_name_edit)
        form.addRow("Episode ID *", self.episode_id_edit)
        form.addRow("Sequence *", self.sequence_spin)
        form.addRow("Heading *", self.heading_edit)
        form.addRow("Location asset ID *", self.location_edit)
        form.addRow("Summary *", self.summary_edit)
        form.addRow("Participants (one per line)", self.participants_edit)
        form.addRow("Dialogue (one line per utterance)", self.dialogue_edit)
        form.addRow("Required assets (one per line)", self.assets_edit)
        form.addRow("Time of day", self.time_of_day_edit)
        form.addRow("Transition", self.transition_combo)
        form.addRow("Estimated duration (seconds)", self.duration_spin)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Save Scene")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.buttons)

        self.scene_name_edit.textChanged.connect(self._validate)
        self.episode_id_edit.textChanged.connect(self._identity_changed)
        self.sequence_spin.valueChanged.connect(self._identity_changed)
        self.heading_edit.textChanged.connect(self._validate)
        self.location_edit.textChanged.connect(self._validate)
        self.summary_edit.textChanged.connect(self._validate)

        if scene is not None:
            self._load(scene)
        else:
            self._refresh_generated_id()
        self._validate()
        self.scene_name_edit.setFocus(Qt.FocusReason.OtherFocusReason)

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
            scene_name=self.scene_name_edit.text().strip(),
        )

    def _load(self, scene: Scene) -> None:
        self.scene_id_edit.setText(scene.scene_id)
        self.scene_name_edit.setText(scene.scene_name or scene.heading)
        self.episode_id_edit.setText(scene.episode_id)
        self.sequence_spin.setValue(scene.sequence_number)
        self.heading_edit.setText(scene.heading)
        self.location_edit.setText(scene.location_asset_id)
        self.summary_edit.setPlainText(scene.summary)
        self.participants_edit.setPlainText("\n".join(scene.participant_asset_ids))
        self.dialogue_edit.setPlainText("\n".join(scene.dialogue))
        self.assets_edit.setPlainText("\n".join(scene.required_asset_ids))
        self.time_of_day_edit.setText(scene.time_of_day or "")
        self.transition_combo.setCurrentIndex(
            self.transition_combo.findData(scene.transition_in)
        )
        self.duration_spin.setValue(scene.estimated_duration_seconds or 30.0)

    def _identity_changed(self) -> None:
        if not self._editing:
            self._refresh_generated_id()
        self._validate()

    def _refresh_generated_id(self) -> None:
        self.scene_id_edit.setText(
            self._scene_id_factory(
                self.episode_id_edit.text().strip(),
                self.sequence_spin.value(),
            )
        )

    def _validate(self) -> None:
        missing: list[str] = []
        if not self.scene_name_edit.text().strip():
            missing.append("scene name")
        if not self.episode_id_edit.text().strip():
            missing.append("episode ID")
        if not self.heading_edit.text().strip():
            missing.append("heading")
        if not self.location_edit.text().strip():
            missing.append("location")
        if not self.summary_edit.toPlainText().strip():
            missing.append("summary")
        valid = not missing and bool(self.scene_id_edit.text().strip())
        self.save_button.setEnabled(valid)
        self.validation_label.setText(
            "Complete the required fields: " + ", ".join(missing) + "."
            if missing
            else ""
        )

    @staticmethod
    def _default_scene_id(episode_id: str, sequence_number: int) -> str:
        episode = episode_id.strip().upper() or "EP-001"
        return f"{episode}-SCN-{sequence_number:03d}"

    @staticmethod
    def _lines(value: str) -> tuple[str, ...]:
        return tuple(line.strip() for line in value.splitlines() if line.strip())
