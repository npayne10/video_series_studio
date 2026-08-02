"""Interactive structured story browser and SSIE planning workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.projects import ProjectNotOpenError
from vscs.application.ssie import Scene, ScenePlan, ShotPlan
from vscs.application.story import StoryService, StoryServiceError
from vscs.presentation.dialogs.scene_editor_dialog import SceneEditorDialog


class StoryBrowserWidget(QWidget):
    """Browse structured scenes and inspect generated SSIE shot plans."""

    def __init__(self, stories: StoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.stories = stories
        self.setObjectName("storyBrowser")

        self.new_button = QPushButton("New Scene")
        self.edit_button = QPushButton("Edit Scene")
        self.delete_button = QPushButton("Delete Scene")
        self.plan_button = QPushButton("Generate SSIE Plan")
        self.refresh_button = QPushButton("Refresh")

        toolbar = QHBoxLayout()
        for button in (
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.plan_button,
            self.refresh_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)

        self.tree = QTreeWidget()
        self.tree.setObjectName("storyTree")
        self.tree.setHeaderLabels(("Story Item", "Purpose", "Duration"))
        self.tree.setAlternatingRowColors(True)

        self.details = QTextBrowser()
        self.details.setObjectName("storyDetails")
        self.details.setOpenExternalLinks(False)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.details)
        splitter.setSizes((520, 780))

        self.empty_label = QLabel("Open or create a project to manage structured scenes.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.empty_label)
        self.empty_label.hide()

        self.new_button.clicked.connect(self._new_scene)
        self.edit_button.clicked.connect(self._edit_scene)
        self.delete_button.clicked.connect(self._delete_scene)
        self.plan_button.clicked.connect(self._plan_scene)
        self.refresh_button.clicked.connect(self.refresh)
        self.tree.currentItemChanged.connect(self._show_item)
        self.refresh()

    def refresh(self) -> None:
        """Reload project scenes and preserve generated plans where possible."""
        selected_id = self._selected_scene_id()
        self.tree.clear()
        self.details.clear()
        try:
            scenes = self.stories.list_scenes()
        except ProjectNotOpenError:
            self._set_enabled(False)
            self.empty_label.show()
            return
        except StoryServiceError as exc:
            QMessageBox.critical(self, "Story Error", str(exc))
            return

        self._set_enabled(True)
        self.empty_label.setVisible(not scenes)
        self.empty_label.setText(
            "No scenes yet. Use New Scene to add structured story material."
        )
        for scene in scenes:
            display_name = scene.scene_name or scene.heading
            scene_item = QTreeWidgetItem(
                (
                    f"{scene.sequence_number:03d} — {display_name}",
                    "Scene",
                    self._duration(scene.estimated_duration_seconds),
                )
            )
            scene_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("scene", scene.scene_id),
            )
            self.tree.addTopLevelItem(scene_item)
            plan = self.stories.plan(scene.scene_id)
            if plan is not None:
                self._append_plan(scene_item, plan)
            if scene.scene_id == selected_id:
                self.tree.setCurrentItem(scene_item)
        self.tree.expandAll()
        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _append_plan(self, parent: QTreeWidgetItem, plan: ScenePlan) -> None:
        for shot in plan.shots:
            item = QTreeWidgetItem(
                (
                    f"{shot.sequence_number:03d} — {shot.description}",
                    shot.purpose.value.replace("_", " ").title(),
                    self._duration(shot.estimated_duration_seconds),
                )
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("shot", plan.scene.scene_id, shot.shot_id),
            )
            parent.addChild(item)

    def _new_scene(self) -> None:
        episode_id = self.stories.default_episode_id()
        sequence = self.stories.next_sequence_number(episode_id)
        dialog = SceneEditorDialog(
            parent=self,
            default_episode_id=episode_id,
            suggested_sequence=sequence,
            scene_id_factory=self.stories.generate_scene_id,
        )
        if dialog.exec() != SceneEditorDialog.DialogCode.Accepted:
            return
        self._save(dialog.scene())

    def _edit_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if scene_id is None:
            return
        scene = self.stories.scene(scene_id)
        if scene is None:
            return
        dialog = SceneEditorDialog(scene, self)
        if dialog.exec() != SceneEditorDialog.DialogCode.Accepted:
            return
        self._save(dialog.scene())

    def _save(self, scene: Scene) -> None:
        try:
            self.stories.save_scene(scene)
        except (ProjectNotOpenError, StoryServiceError, ValueError) as exc:
            QMessageBox.critical(self, "Story Error", str(exc))
            return
        self.refresh()

    def _delete_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if scene_id is None:
            return
        response = QMessageBox.question(
            self,
            "Delete Scene",
            f"Delete scene {scene_id}?",
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            self.stories.delete_scene(scene_id)
        except (ProjectNotOpenError, StoryServiceError) as exc:
            QMessageBox.critical(self, "Story Error", str(exc))
            return
        self.refresh()

    def _plan_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if scene_id is None:
            return
        try:
            plan = self.stories.plan_scene(scene_id)
        except (StoryServiceError, ValueError) as exc:
            QMessageBox.critical(self, "SSIE Planning Error", str(exc))
            return
        self.refresh()
        self._show_plan(plan)

    def _show_item(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            self.details.clear()
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "scene":
            scene = self.stories.scene(data[1])
            if scene is not None:
                participants = ", ".join(scene.participant_asset_ids) or "None"
                display_name = scene.scene_name or scene.heading
                self.details.setHtml(
                    f"<h2>{display_name}</h2>"
                    f"<p><b>ID:</b> {scene.scene_id}</p>"
                    f"<p><b>Episode:</b> {scene.episode_id}</p>"
                    f"<p><b>Heading:</b> {scene.heading}</p>"
                    f"<p><b>Location:</b> {scene.location_asset_id}</p>"
                    f"<p><b>Summary:</b> {scene.summary}</p>"
                    f"<p><b>Participants:</b> {participants}</p>"
                )
        elif data[0] == "shot":
            plan = self.stories.plan(data[1])
            if plan is not None:
                shot = next(
                    (item for item in plan.shots if item.shot_id == data[2]),
                    None,
                )
                if shot is not None:
                    self._show_shot(shot)

    def _show_plan(self, plan: ScenePlan) -> None:
        display_name = plan.scene.scene_name or plan.scene.heading
        self.details.setHtml(
            f"<h2>{display_name}</h2>"
            f"<p><b>Objective:</b> {plan.objective}</p>"
            f"<p><b>Emotional intent:</b> {plan.emotional_intent}</p>"
            f"<p><b>Shots:</b> {len(plan.shots)}</p>"
        )

    def _show_shot(self, shot: ShotPlan) -> None:
        camera = shot.camera_plan
        lighting = shot.lighting_plan
        blocking = shot.blocking_plan
        continuity = shot.continuity_plan
        continuity_state = (
            continuity.location_state if continuity else "Not planned"
        )
        self.details.setHtml(
            f"<h2>{shot.shot_id}</h2>"
            f"<p><b>Purpose:</b> {shot.purpose.value}</p>"
            f"<p><b>Description:</b> {shot.description}</p>"
            f"<h3>Camera</h3>"
            f"<p>{camera.shot_size.value if camera else 'Not planned'}; "
            f"{camera.movement.value if camera else ''}; "
            f"{camera.composition if camera else ''}</p>"
            f"<h3>Lighting</h3>"
            f"<p>{lighting.mood.value if lighting else 'Not planned'}; "
            f"{lighting.key_direction if lighting else ''}</p>"
            f"<h3>Blocking</h3>"
            f"<p>{blocking.pattern.value if blocking else 'Not planned'}; "
            f"{blocking.screen_direction if blocking else ''}</p>"
            f"<h3>Continuity</h3><p>{continuity_state}</p>"
        )

    def _selected_scene_id(self) -> str | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return None
        return data[1]

    def _set_enabled(self, active: bool) -> None:
        self.new_button.setEnabled(active)
        for button in (self.edit_button, self.delete_button, self.plan_button):
            button.setEnabled(active and self.tree.currentItem() is not None)

    @staticmethod
    def _duration(value: float | None) -> str:
        return "—" if value is None else f"{value:.2f}s"
