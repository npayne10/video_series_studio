"""Scene Editor with generic production-container identity support."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from vscs.application.ssie import Scene
from vscs.application.story import (
    ProductionContainerType,
    infer_container_type,
    normalize_container_id,
)
from vscs.presentation.dialogs.live_documentation_scene_editor_dialog import (
    LiveDocumentationSceneEditorDialog,
)


class ProductionContainerSceneEditorDialog(LiveDocumentationSceneEditorDialog):
    """Allow scenes to belong to episodes, trailers and other productions."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scene, parent, **kwargs)
        self._install_container_controls(scene)

    @property
    def container_type(self) -> ProductionContainerType:
        """Return the selected production-container type."""
        value = self.production_type_combo.currentData()
        if isinstance(value, ProductionContainerType):
            return value
        return ProductionContainerType(str(value))

    @property
    def container_id(self) -> str:
        """Return the normalized production-container identity."""
        return normalize_container_id(
            self.episode_id_edit.text(),
            self.container_type,
        )

    def _install_container_controls(self, scene: Scene | None) -> None:
        form = self._find_form_layout()
        if form is None:
            raise RuntimeError("Scene Editor form layout is unavailable.")

        current_id = scene.episode_id if scene is not None else self.episode_id_edit.text()
        current_type = infer_container_type(current_id)

        self.production_type_combo = QComboBox(self)
        self.production_type_combo.setObjectName("sceneProductionContainerType")
        self.production_type_combo.setToolTip("Choose the kind of production that owns this scene.")
        for container_type in ProductionContainerType:
            self.production_type_combo.addItem(
                container_type.label,
                container_type.value,
            )
        type_index = self.production_type_combo.findData(current_type.value)
        self.production_type_combo.setCurrentIndex(max(type_index, 0))

        container_row = self._row_for_widget(form, self.episode_id_edit)
        if container_row < 0:
            raise RuntimeError("Scene Editor container ID row is unavailable.")
        label = form.labelForField(self.episode_id_edit)
        if isinstance(label, QLabel):
            label.setText("Container ID *")
        form.insertRow(container_row, "Production type *", self.production_type_combo)

        self.episode_id_edit.setObjectName("sceneProductionContainerId")
        self.episode_id_edit.setPlaceholderText(current_type.default_id)
        self.episode_id_edit.setToolTip(
            "Canonical identity of the episode, trailer, teaser, promo, test or special."
        )

        self.knowledge_provider.install(
            self.production_type_combo,
            "scene.production_type",
        )
        self.knowledge_provider.install(
            self.episode_id_edit,
            "scene.container_id",
        )
        self._bind_live_topic(self.production_type_combo, "scene.production_type")
        self._bind_live_topic(self.episode_id_edit, "scene.container_id")

        self.production_type_combo.currentIndexChanged.connect(self._production_type_changed)
        self.episode_id_edit.editingFinished.connect(self._normalize_container_field)

        if self._editing:
            self.production_type_combo.setEnabled(False)
            self.episode_id_edit.setReadOnly(True)
            self.sequence_spin.setEnabled(False)
            locked = (
                "Production identity is locked after creation because downstream SSIE, "
                "ACPP, continuity and render records use the generated Scene ID."
            )
            self.production_type_combo.setToolTip(locked)
            self.episode_id_edit.setToolTip(locked)
            self.sequence_spin.setToolTip(locked)

        self._update_workflow_summary()

    def _production_type_changed(self, _index: int = -1) -> None:
        if self._editing:
            return
        old_type = infer_container_type(self.episode_id_edit.text())
        new_type = self.container_type
        current = self.episode_id_edit.text().strip().upper()
        if not current or current == old_type.default_id:
            self.episode_id_edit.setText(new_type.default_id)
        else:
            self.episode_id_edit.setPlaceholderText(new_type.default_id)
        self._refresh_generated_id()
        self._update_workflow_summary()
        self.show_live_topic("scene.production_type")

    def _normalize_container_field(self) -> None:
        if self._editing:
            return
        self.episode_id_edit.setText(self.container_id)
        self._refresh_generated_id()

    def _update_workflow_summary(self) -> None:
        if not hasattr(self, "production_type_combo"):
            super()._update_workflow_summary()
            return
        scene_name = self.scene_name_edit.text().strip() or "Untitled scene"
        sequence = self.sequence_spin.value()
        location = self.selected_location_id() or "No location selected"
        participants = len(self.selected_participant_ids())
        assets = len(self.selected_required_asset_ids())
        duration = self.duration_spin.value()
        time_of_day = self.time_of_day_combo.currentText()
        transition = self.transition_combo.currentText()
        self.summary_label.setText(
            f"{self.container_type.label} · {self.container_id} · "
            f"Scene {sequence:03d} · {scene_name}\n"
            f"{location} · {time_of_day} · {transition}\n"
            f"{participants} participants · {assets} required assets · "
            f"{duration:g} seconds"
        )
