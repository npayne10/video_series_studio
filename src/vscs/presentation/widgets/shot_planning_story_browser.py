"""Story Browser v2 integration for persistent production-shot planning."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTreeWidgetItem, QWidget

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectNotOpenError
from vscs.application.shots import (
    ProductionShot,
    ShotPlanningError,
    ShotPlanningService,
)
from vscs.application.story import StoryService
from vscs.presentation.dialogs.shot_planner_dialog import ShotPlannerDialog

from .story_browser_v2 import StoryBrowserV2Widget


class ShotPlanningStoryBrowserWidget(StoryBrowserV2Widget):
    """Expose persistent Shot Planner actions inside the production hierarchy."""

    SHOT_KIND = "production_shot"

    def __init__(
        self,
        stories: StoryService,
        assets: AssetService,
        shot_plans: ShotPlanningService,
        parent: QWidget | None = None,
    ) -> None:
        self.shot_plans = shot_plans
        self._shot_planner_ready = False
        super().__init__(stories, assets, parent)
        self.shot_planner_button = QPushButton("Shot Planner", self)
        self.shot_planner_button.setObjectName("openShotPlanner")
        self.shot_planner_button.setToolTip(
            "Open the production Shot Planner for the selected scene."
        )
        toolbar_item = self.layout().itemAt(2)
        toolbar = toolbar_item.layout() if toolbar_item is not None else None
        if not isinstance(toolbar, QHBoxLayout):
            raise RuntimeError("Story Browser toolbar is unavailable.")
        toolbar.insertWidget(4, self.shot_planner_button)
        self.shot_planner_button.clicked.connect(self._open_shot_planner)
        self._shot_planner_ready = True
        self.refresh()

    def refresh(self) -> None:
        """Refresh Story Browser v2 and append persistent production shots."""
        super().refresh()
        if not self._shot_planner_ready:
            return
        try:
            shots = self.shot_plans.list_shots()
        except (ProjectNotOpenError, ShotPlanningError):
            self.shot_planner_button.setEnabled(False)
            return
        by_scene: dict[str, list[ProductionShot]] = {}
        for shot in shots:
            by_scene.setdefault(shot.scene_id, []).append(shot)
        for item in self._walk_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data or str(data[0]) != "scene":
                continue
            scene_id = str(data[2])
            existing: dict[str, QTreeWidgetItem] = {}
            for index in range(item.childCount()):
                child = item.child(index)
                child_data = child.data(0, Qt.ItemDataRole.UserRole)
                if child_data:
                    existing[str(child_data[1])] = child
            for shot in by_scene.get(scene_id, []):
                placeholder = existing.get(shot.shot_id)
                if placeholder is not None:
                    item.removeChild(placeholder)
                item.addChild(self._production_shot_item(shot))
        shot_count = sum(
            1
            for item in self._walk_items()
            if (
                data := item.data(0, Qt.ItemDataRole.UserRole)
            )
            and str(data[0]) in {"shot", self.SHOT_KIND}
        )
        self.dashboard_labels["shots"].setText(str(shot_count))
        self._update_shot_action_state()

    def _production_shot_item(self, shot: ProductionShot) -> QTreeWidgetItem:
        asset_count = len(
            {*shot.subject_asset_ids, *shot.required_asset_ids}
        )
        item = QTreeWidgetItem(
            (
                f"{shot.sequence_number:03d} — {shot.title}",
                "Production Shot",
                shot.status.label,
                self._duration(shot.estimated_duration_seconds),
                str(asset_count) if asset_count else "—",
            )
        )
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            (self.SHOT_KIND, shot.shot_id, shot.scene_id, shot.shot_id),
        )
        return item

    def _walk_items(self) -> tuple[QTreeWidgetItem, ...]:
        root = self.tree.invisibleRootItem()
        stack = [root.child(index) for index in range(root.childCount())]
        result: list[QTreeWidgetItem] = []
        while stack:
            item = stack.pop()
            result.append(item)
            stack.extend(item.child(index) for index in range(item.childCount()))
        return tuple(result)

    def _selected_scene_id(self) -> str | None:
        item = self.tree.currentItem()
        if item is not None:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and str(data[0]) == self.SHOT_KIND:
                return str(data[2])
        return super()._selected_scene_id()

    def _show_item(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        if current is not None:
            data = current.data(0, Qt.ItemDataRole.UserRole)
            if data and str(data[0]) == self.SHOT_KIND:
                shot = self.shot_plans.shot(str(data[1]))
                if shot is not None:
                    self._show_production_shot(shot)
                    self._update_shot_action_state()
                    return
        super()._show_item(current, previous)
        if self._shot_planner_ready:
            self._update_shot_action_state()

    def _show_production_shot(self, shot: ProductionShot) -> None:
        camera_profile = shot.camera_profile_id or "Planner default"
        lighting_profile = shot.lighting_profile_id or "Planner default"
        continuity = shot.continuity_from_shot_id or "Opening shot"
        storyboard = shot.storyboard_reference or "Not assigned"
        purpose = shot.purpose.value.replace("_", " ").title()
        self.details.setHtml(
            f"<h2>{shot.title}</h2>"
            f"<p><b>ID:</b> {shot.shot_id}</p>"
            f"<p><b>Status:</b> {shot.status.label}</p>"
            f"<p><b>Purpose:</b> {purpose}</p>"
            f"<p><b>Description:</b> {shot.description}</p>"
            f"<h3>Camera</h3><p>{shot.shot_size.value}; "
            f"{shot.camera_movement.value}; {shot.lens_family.value}; "
            f"{camera_profile}</p>"
            f"<h3>Lighting</h3><p>{shot.lighting_mood.value}; "
            f"{lighting_profile}</p>"
            f"<h3>Continuity</h3><p>From: {continuity}<br>"
            f"{shot.continuity_notes or 'No additional notes'}</p>"
            f"<h3>Storyboard</h3><p>{storyboard}</p>"
            f"<p><b>Duration:</b> {shot.estimated_duration_seconds:.2f}s</p>"
        )

    def _open_shot_planner(self) -> None:
        scene_id = self._selected_scene_id()
        if scene_id is None:
            return
        dialog = ShotPlannerDialog(scene_id, self.shot_plans, self.assets, self)
        dialog.exec()
        self.refresh()
        self._select_scene(scene_id)

    def _select_scene(self, scene_id: str) -> None:
        for item in self._walk_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and str(data[0]) == "scene" and str(data[2]) == scene_id:
                self.tree.setCurrentItem(item)
                return

    def _update_action_state(self, *_args: object) -> None:
        super()._update_action_state()
        if self._shot_planner_ready:
            self._update_shot_action_state()

    def _update_shot_action_state(self) -> None:
        self.shot_planner_button.setEnabled(
            self._selected_scene_id() is not None
        )
