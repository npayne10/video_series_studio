"""Scene editor production timing, transition, and duration controls."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from vscs.application.ssie import Scene, SceneTransition
from vscs.presentation.dialogs.structured_scene_editor_dialog import (
    StructuredSceneEditorDialog,
)


class TransitionComboBox(QComboBox):
    """Expose strongly typed SceneTransition values over Qt's string variants."""

    def itemData(  # noqa: N802
        self,
        index: int,
        role: int = Qt.ItemDataRole.UserRole,
    ) -> object:
        value = super().itemData(index, role)
        if role == Qt.ItemDataRole.UserRole and isinstance(value, str):
            try:
                return SceneTransition(value)
            except ValueError:
                return value
        return value

    def currentData(  # noqa: N802
        self,
        role: int = Qt.ItemDataRole.UserRole,
    ) -> object:
        return self.itemData(self.currentIndex(), role)


class ProductionSceneEditorDialog(StructuredSceneEditorDialog):
    """Add controlled production metadata and live timing estimates."""

    TIME_OF_DAY_OPTIONS = (
        ("Unspecified", None),
        ("Dawn", "dawn"),
        ("Morning", "morning"),
        ("Midday", "midday"),
        ("Afternoon", "afternoon"),
        ("Dusk", "dusk"),
        ("Evening", "evening"),
        ("Night", "night"),
        ("Continuous", "continuous"),
    )
    DURATION_PRESETS = (
        ("Custom", None),
        ("Brief — 10 seconds", 10.0),
        ("Standard — 30 seconds", 30.0),
        ("Extended — 60 seconds", 60.0),
        ("Long — 90 seconds", 90.0),
        ("Sequence — 120 seconds", 120.0),
    )

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        *,
        frames_per_second: float = 24.0,
        **kwargs: object,
    ) -> None:
        self.frames_per_second = frames_per_second
        super().__init__(scene, parent, **kwargs)
        self._install_production_controls(scene)

    def scene(self) -> Scene:
        """Return the scene with controlled production metadata."""
        transition = self.transition_combo.currentData()
        if not isinstance(transition, SceneTransition):
            transition = SceneTransition(str(transition))
        return replace(
            super().scene(),
            time_of_day=self.time_of_day_combo.currentData(),
            transition_in=transition,
            estimated_duration_seconds=self.duration_spin.value(),
        )

    def _install_production_controls(self, scene: Scene | None) -> None:
        form = self._find_form_layout()
        if form is None:
            return

        self.time_of_day_combo = QComboBox(self)
        self.time_of_day_combo.setObjectName("sceneTimeOfDaySelector")
        self.time_of_day_combo.setToolTip(
            "Choose the story time or continuity relationship for this scene."
        )
        for label, value in self.TIME_OF_DAY_OPTIONS:
            self.time_of_day_combo.addItem(label, value)

        previous_time = scene.time_of_day if scene is not None else None
        time_index = self.time_of_day_combo.findData(previous_time)
        self.time_of_day_combo.setCurrentIndex(max(time_index, 0))
        form.replaceWidget(self.time_of_day_edit, self.time_of_day_combo)
        self.time_of_day_edit.hide()
        self.time_of_day_edit.deleteLater()

        previous_transition = (
            scene.transition_in if scene is not None else SceneTransition.CUT
        )
        old_transition_combo = self.transition_combo
        self.transition_combo = TransitionComboBox(self)
        self.transition_combo.setObjectName("sceneTransitionSelector")
        for transition in SceneTransition:
            self.transition_combo.addItem(
                transition.value.replace("_", " ").title(),
                transition.value,
            )
        transition_index = self.transition_combo.findData(previous_transition.value)
        self.transition_combo.setCurrentIndex(max(transition_index, 0))
        self.transition_combo.setToolTip(
            "Choose how the editor enters this scene from the preceding scene."
        )
        cut_index = self.transition_combo.findData(SceneTransition.CUT.value)
        self.transition_combo.setItemData(
            cut_index,
            "Immediate transition; the standard choice for most scene changes.",
            Qt.ItemDataRole.ToolTipRole,
        )
        form.replaceWidget(old_transition_combo, self.transition_combo)
        old_transition_combo.hide()
        old_transition_combo.deleteLater()

        self.duration_preset_combo = QComboBox(self)
        self.duration_preset_combo.setObjectName("sceneDurationPreset")
        for label, value in self.DURATION_PRESETS:
            self.duration_preset_combo.addItem(label, value)
        self.duration_preset_combo.setToolTip(
            "Apply a common duration or choose Custom for a manual estimate."
        )

        self.duration_spin.setSuffix(" s")
        self.duration_spin.setSingleStep(1.0)
        self.duration_spin.setToolTip(
            "Estimated total scene runtime. This drives frame and shot estimates."
        )

        self.production_estimate_label = QLabel(self)
        self.production_estimate_label.setObjectName("sceneProductionEstimate")
        self.production_estimate_label.setWordWrap(True)

        duration_row = self._row_for_widget(form, self.duration_spin)
        if duration_row >= 0:
            duration_layout = QHBoxLayout()
            duration_layout.setContentsMargins(0, 0, 0, 0)
            duration_layout.addWidget(self.duration_preset_combo)
            duration_layout.addWidget(self.duration_spin)
            field_item = form.itemAt(duration_row, QFormLayout.ItemRole.FieldRole)
            if field_item is not None:
                existing = field_item.widget()
                if existing is not None:
                    form.removeWidget(existing)
            form.setLayout(
                duration_row,
                QFormLayout.ItemRole.FieldRole,
                duration_layout,
            )
            form.insertRow(
                duration_row + 1,
                "Production estimate",
                self.production_estimate_label,
            )

        self.duration_preset_combo.currentIndexChanged.connect(
            self._apply_duration_preset
        )
        self.duration_spin.valueChanged.connect(self._duration_changed)
        self._select_matching_preset(self.duration_spin.value())
        self._update_production_estimate()

    def _apply_duration_preset(self) -> None:
        value = self.duration_preset_combo.currentData()
        if isinstance(value, int | float):
            self.duration_spin.setValue(float(value))

    def _duration_changed(self) -> None:
        self._select_matching_preset(self.duration_spin.value())
        self._update_production_estimate()

    def _select_matching_preset(self, duration: float) -> None:
        matching = 0
        for index in range(self.duration_preset_combo.count()):
            value = self.duration_preset_combo.itemData(index)
            if isinstance(value, int | float) and abs(float(value) - duration) < 0.001:
                matching = index
                break
        if self.duration_preset_combo.currentIndex() != matching:
            self.duration_preset_combo.blockSignals(True)
            self.duration_preset_combo.setCurrentIndex(matching)
            self.duration_preset_combo.blockSignals(False)

    def _update_production_estimate(self) -> None:
        duration = self.duration_spin.value()
        frames = round(duration * self.frames_per_second)
        estimated_shots = max(1, round(duration / 8.0))
        self.production_estimate_label.setText(
            f"Approximately {estimated_shots} shots and {frames:,} frames "
            f"at {self.frames_per_second:g} fps."
        )

    def _find_form_layout(self) -> QFormLayout | None:
        content_layout = self.scroll_content.layout()
        if content_layout is None:
            return None
        for index in range(content_layout.count()):
            item = content_layout.itemAt(index)
            layout = item.layout() if item is not None else None
            if isinstance(layout, QFormLayout):
                return layout
        return None

    @staticmethod
    def _row_for_widget(form: QFormLayout, widget: QWidget) -> int:
        for row in range(form.rowCount()):
            for role in (
                QFormLayout.ItemRole.FieldRole,
                QFormLayout.ItemRole.SpanningRole,
            ):
                item = form.itemAt(row, role)
                if item is not None and item.widget() is widget:
                    return row
        return -1
