"""Scene-bound production Shot Planner workspace."""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from vscs.application.assets import (
    AssetError,
    AssetProjectNotOpenError,
    AssetService,
)
from vscs.application.shots import (
    ProductionShot,
    ShotPlanningError,
    ShotPlanningService,
    ShotPlanningStatus,
)
from vscs.application.ssie import (
    CameraMovement,
    LensFamily,
    LightingMood,
    ShotPurpose,
    ShotSize,
)
from vscs.domain.assets import AssetCategory


class ShotPlannerDialog(QDialog):
    """Create, edit, order and validate persistent shots for one scene."""

    def __init__(
        self,
        scene_id: str,
        shots: ShotPlanningService,
        assets: AssetService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.scene_id = scene_id
        self.shots = shots
        self.assets = assets
        self._current_shot_id: str | None = None
        self.setWindowTitle(f"Shot Planner — {scene_id}")
        self.resize(1180, 760)
        self.setMinimumSize(900, 620)

        self.shot_list = QListWidget(self)
        self.shot_list.setObjectName("shotPlannerList")
        self.shot_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.shot_list.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.add_button = QPushButton("New Shot", self)
        self.delete_button = QPushButton("Delete Shot", self)
        self.move_up_button = QPushButton("Move Up", self)
        self.move_down_button = QPushButton("Move Down", self)
        left_actions = QHBoxLayout()
        for button in (
            self.add_button,
            self.delete_button,
            self.move_up_button,
            self.move_down_button,
        ):
            left_actions.addWidget(button)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Scene shots", left))
        left_layout.addWidget(self.shot_list, 1)
        left_layout.addLayout(left_actions)

        self.shot_id_edit = QLineEdit(self)
        self.shot_id_edit.setReadOnly(True)
        self.title_edit = QLineEdit(self)
        self.description_edit = QPlainTextEdit(self)
        self.purpose_combo = self._enum_combo(ShotPurpose)
        self.size_combo = self._enum_combo(ShotSize)
        self.movement_combo = self._enum_combo(CameraMovement)
        self.lens_combo = self._enum_combo(LensFamily)
        self.camera_profile_combo = self._asset_combo(AssetCategory.CAMERA)
        self.lighting_profile_combo = self._asset_combo(AssetCategory.LIGHTING)
        self.lighting_mood_combo = self._enum_combo(LightingMood)
        self.duration_spin = QDoubleSpinBox(self)
        self.duration_spin.setRange(0.1, 3600.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setValue(5.0)
        self.continuity_combo = QComboBox(self)
        self.continuity_notes_edit = QPlainTextEdit(self)
        self.blocking_edit = QPlainTextEdit(self)
        self.blocking_edit.setPlaceholderText(
            "Describe positions, facing, movement paths and eyelines."
        )
        self.storyboard_edit = QLineEdit(self)
        self.storyboard_edit.setPlaceholderText(
            "Optional image path, asset ID or storyboard reference"
        )
        self.dialogue_edit = QPlainTextEdit(self)
        self.dialogue_edit.setPlaceholderText("One dialogue line per row")
        self.validation_label = QLabel(self)
        self.validation_label.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Shot ID", self.shot_id_edit)
        form.addRow("Title *", self.title_edit)
        form.addRow("Description *", self.description_edit)
        form.addRow("Purpose", self.purpose_combo)
        form.addRow("Shot size", self.size_combo)
        form.addRow("Camera movement", self.movement_combo)
        form.addRow("Lens family", self.lens_combo)
        form.addRow("Camera profile", self.camera_profile_combo)
        form.addRow("Lighting profile", self.lighting_profile_combo)
        form.addRow("Lighting mood", self.lighting_mood_combo)
        form.addRow("Duration (seconds) *", self.duration_spin)
        form.addRow("Continuity from", self.continuity_combo)
        form.addRow("Continuity notes", self.continuity_notes_edit)
        form.addRow("Actor blocking", self.blocking_edit)
        form.addRow("Storyboard reference", self.storyboard_edit)
        form.addRow("Dialogue allocation", self.dialogue_edit)
        form.addRow("Validation", self.validation_label)

        self.save_button = QPushButton("Save Shot", self)
        form_widget = QWidget(self)
        form_layout = QVBoxLayout(form_widget)
        form_layout.addLayout(form)
        form_layout.addWidget(self.save_button)
        form_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setObjectName("shotPlannerScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("shotPlannerSplitter")
        splitter.addWidget(left)
        splitter.addWidget(scroll)
        splitter.setSizes((360, 820))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close,
            self,
        )
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addWidget(buttons)

        self.add_button.clicked.connect(self._new_shot)
        self.delete_button.clicked.connect(self._delete_shot)
        self.move_up_button.clicked.connect(lambda: self._move_current(-1))
        self.move_down_button.clicked.connect(lambda: self._move_current(1))
        self.save_button.clicked.connect(self._save_current)
        self.shot_list.currentItemChanged.connect(self._load_selected)
        self.shot_list.model().rowsMoved.connect(self._persist_visual_order)
        self.title_edit.textChanged.connect(self._validate)
        self.description_edit.textChanged.connect(self._validate)
        self.duration_spin.valueChanged.connect(self._validate)
        self.refresh()

    @staticmethod
    def _enum_combo(enum_type: type[StrEnum]) -> QComboBox:
        combo = QComboBox()
        for value in enum_type:
            combo.addItem(value.value.replace("_", " ").title(), value)
        return combo

    def _asset_combo(self, category: AssetCategory) -> QComboBox:
        combo = QComboBox(self)
        combo.addItem("Use planner default", None)
        try:
            assets = self.assets.list(category=category)
        except (AssetProjectNotOpenError, AssetError):
            assets = ()
        ordered = sorted(
            assets,
            key=lambda item: (item.name.casefold(), item.asset_id),
        )
        for asset in ordered:
            combo.addItem(f"{asset.name} — {asset.asset_id}", asset.asset_id)
        return combo

    def refresh(self, select_shot_id: str | None = None) -> None:
        """Reload the current scene's shots and continuity choices."""
        current = select_shot_id or self._current_shot_id
        self.shot_list.clear()
        try:
            shots = self.shots.list_shots(self.scene_id)
        except ShotPlanningError as exc:
            QMessageBox.critical(self, "Shot Planner Error", str(exc))
            return
        for shot in shots:
            item = QListWidgetItem(
                f"{shot.sequence_number:03d} — {shot.title} "
                f"[{shot.status.label}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, shot.shot_id)
            self.shot_list.addItem(item)
        self._populate_continuity(shots)
        for index in range(self.shot_list.count()):
            item = self.shot_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == current:
                self.shot_list.setCurrentItem(item)
                return
        if self.shot_list.count():
            self.shot_list.setCurrentRow(0)
        else:
            self._new_shot()

    def _populate_continuity(
        self,
        shots: tuple[ProductionShot, ...],
    ) -> None:
        selected = self.continuity_combo.currentData()
        self.continuity_combo.clear()
        self.continuity_combo.addItem("No incoming shot", None)
        for shot in shots:
            if shot.shot_id != self._current_shot_id:
                self.continuity_combo.addItem(
                    f"{shot.sequence_number:03d} — {shot.title}",
                    shot.shot_id,
                )
        index = self.continuity_combo.findData(selected)
        if index >= 0:
            self.continuity_combo.setCurrentIndex(index)

    def _new_shot(self) -> None:
        sequence = self.shots.next_sequence_number(self.scene_id)
        self._current_shot_id = self.shots.generate_shot_id(
            self.scene_id,
            sequence,
        )
        self.shot_id_edit.setText(self._current_shot_id)
        self.title_edit.clear()
        self.description_edit.clear()
        self.duration_spin.setValue(5.0)
        self.continuity_notes_edit.clear()
        self.blocking_edit.clear()
        self.storyboard_edit.clear()
        self.dialogue_edit.clear()
        self._populate_continuity(self.shots.list_shots(self.scene_id))
        self._validate()
        self.title_edit.setFocus()

    def _load_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        shot_id = str(current.data(Qt.ItemDataRole.UserRole))
        shot = self.shots.shot(shot_id)
        if shot is None:
            return
        self._current_shot_id = shot.shot_id
        self.shot_id_edit.setText(shot.shot_id)
        self.title_edit.setText(shot.title)
        self.description_edit.setPlainText(shot.description)
        self._select_data(self.purpose_combo, shot.purpose)
        self._select_data(self.size_combo, shot.shot_size)
        self._select_data(self.movement_combo, shot.camera_movement)
        self._select_data(self.lens_combo, shot.lens_family)
        self._select_data(self.lighting_mood_combo, shot.lighting_mood)
        self._select_data(
            self.camera_profile_combo,
            shot.camera_profile_id,
        )
        self._select_data(
            self.lighting_profile_combo,
            shot.lighting_profile_id,
        )
        self.duration_spin.setValue(shot.estimated_duration_seconds)
        self._populate_continuity(self.shots.list_shots(self.scene_id))
        self._select_data(
            self.continuity_combo,
            shot.continuity_from_shot_id,
        )
        self.continuity_notes_edit.setPlainText(shot.continuity_notes)
        self.blocking_edit.setPlainText(shot.blocking_notes)
        self.storyboard_edit.setText(shot.storyboard_reference)
        self.dialogue_edit.setPlainText("\n".join(shot.dialogue_lines))
        self._validate()

    @staticmethod
    def _select_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(max(index, 0))

    def _shot_from_form(self) -> ProductionShot:
        shot_id = self._current_shot_id or self.shots.generate_shot_id(
            self.scene_id,
            self.shots.next_sequence_number(self.scene_id),
        )
        existing = self.shots.shot(shot_id)
        sequence = (
            existing.sequence_number
            if existing is not None
            else self.shots.next_sequence_number(self.scene_id)
        )
        shot = ProductionShot(
            shot_id=shot_id,
            scene_id=self.scene_id,
            sequence_number=sequence,
            title=self.title_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            purpose=self.purpose_combo.currentData(),
            shot_size=self.size_combo.currentData(),
            camera_movement=self.movement_combo.currentData(),
            lens_family=self.lens_combo.currentData(),
            camera_profile_id=self.camera_profile_combo.currentData(),
            lighting_profile_id=self.lighting_profile_combo.currentData(),
            lighting_mood=self.lighting_mood_combo.currentData(),
            estimated_duration_seconds=self.duration_spin.value(),
            continuity_from_shot_id=self.continuity_combo.currentData(),
            continuity_notes=(
                self.continuity_notes_edit.toPlainText().strip()
            ),
            blocking_notes=self.blocking_edit.toPlainText().strip(),
            storyboard_reference=self.storyboard_edit.text().strip(),
            dialogue_lines=tuple(
                line.strip()
                for line in self.dialogue_edit.toPlainText().splitlines()
                if line.strip()
            ),
        )
        status = (
            ShotPlanningStatus.READY
            if shot.ready
            else ShotPlanningStatus.DRAFT
        )
        return replace(shot, status=status)

    def _save_current(self) -> None:
        try:
            shot = self.shots.save_shot(self._shot_from_form())
        except (ShotPlanningError, ValueError) as exc:
            QMessageBox.warning(self, "Shot Validation", str(exc))
            return
        self.refresh(shot.shot_id)

    def _delete_shot(self) -> None:
        shot_id = self._current_shot_id
        if shot_id is None or self.shots.shot(shot_id) is None:
            return
        response = QMessageBox.question(
            self,
            "Delete Shot",
            "Delete the selected shot?",
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self.shots.delete_shot(shot_id)
        self._current_shot_id = None
        self.refresh()

    def _move_current(self, offset: int) -> None:
        row = self.shot_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.shot_list.count():
            return
        item = self.shot_list.takeItem(row)
        self.shot_list.insertItem(target, item)
        self.shot_list.setCurrentRow(target)
        self._persist_visual_order()

    def _persist_visual_order(self, *_args: object) -> None:
        ordered = tuple(
            str(
                self.shot_list.item(index).data(
                    Qt.ItemDataRole.UserRole
                )
            )
            for index in range(self.shot_list.count())
        )
        if ordered and all(
            self.shots.shot(shot_id) is not None for shot_id in ordered
        ):
            self.shots.reorder_scene(self.scene_id, ordered)
            self.refresh(self._current_shot_id)

    def _validate(self, *_args: object) -> None:
        issues = []
        if not self.title_edit.text().strip():
            issues.append("Title is required")
        if not self.description_edit.toPlainText().strip():
            issues.append("Description is required")
        if self.duration_spin.value() <= 0:
            issues.append("Duration must be greater than zero")
        self.save_button.setEnabled(not issues)
        self.validation_label.setText(
            "Ready to save" if not issues else " · ".join(issues)
        )
