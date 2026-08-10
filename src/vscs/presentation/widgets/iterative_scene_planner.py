"""Corrected Scene Planner UI for iterative Episode/Scene planning."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton, QTableWidgetItem, QVBoxLayout, QWidget

from vscs.application.story import (
    EpisodePlan,
    EpisodePlanStatus,
    GovernedShotPlanningService,
    ScenePlanningError,
    ScenePlanningService,
    ScenePlanStatus,
)

from .governed_shot_planner import GovernedShotPlannerDialog
from .scene_planner import ScenePlanEditorDialog, ScenePlannerDialog


class IterativeScenePlannerDialog(ScenePlannerDialog):
    """Scene Planner that permits Draft Episode iteration and shows legacy references."""

    def __init__(
        self,
        service: ScenePlanningService,
        episode: EpisodePlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(service, episode, parent)
        self.shot_service: GovernedShotPlanningService | None = getattr(
            service,
            "shot_planning_service",
            None,
        )
        self.shots_button = QPushButton("Shot Planner…", self)
        self.shots_button.setObjectName("governedShotPlannerButton")
        self.shots_button.setToolTip(
            "Plan authoritative shots for the selected production-ready Scene Plan"
        )
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(4, self.shots_button)
        self.shots_button.clicked.connect(self._open_shots)
        self._update_actions()

    def refresh(self) -> None:
        """Reload governed Scene Plans plus inactive legacy scene references."""
        super().refresh()
        episode = self.service.episodes.plan(self.episode_id)
        if episode is None:
            return

        if episode.status is EpisodePlanStatus.READY:
            self.upstream_label.setText(
                "Upstream Episode: Ready — Scene Plans may be edited while Draft and may be promoted to Ready for Shot Planning."
            )
        else:
            self.upstream_label.setText(
                "Upstream Episode: Draft — Scene creation/editing is enabled for iterative planning. "
                "Scenes cannot be promoted to Ready until the Episode itself is Ready."
            )

        for legacy in self.service.legacy_scenes(self.episode_id):
            row = self.table.rowCount()
            self.table.insertRow(row)
            runtime = (
                self._runtime_label(round(legacy.estimated_duration_seconds))
                if legacy.estimated_duration_seconds is not None
                else "—"
            )
            values = (
                legacy.scene_id,
                legacy.scene_name or legacy.heading,
                runtime,
                "Legacy / Inactive",
                legacy.location_asset_id or "—",
                legacy.summary,
                "Reference only — migrate before authoritative planning",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, ("legacy", legacy.scene_id))
                self.table.setItem(row, column, item)
        self._update_actions()

    def _update_actions(self) -> None:
        episode = self.service.episodes.plan(self.episode_id)
        scene = self._selected()
        draft = scene is not None and scene.status is ScenePlanStatus.DRAFT
        ready = scene is not None and scene.status is ScenePlanStatus.READY
        current = scene is not None and self.service.is_upstream_current(scene)
        episode_ready = episode is not None and episode.status is EpisodePlanStatus.READY

        self.new_button.setEnabled(episode is not None)
        self.edit_button.setEnabled(draft)
        self.delete_button.setEnabled(draft)
        self.ready_button.setEnabled(episode_ready and draft and current)
        self.draft_button.setEnabled(ready)
        if hasattr(self, "shots_button"):
            self.shots_button.setEnabled(
                self.shot_service is not None
                and scene is not None
                and self.service.is_production_ready(scene)
            )

    def _new(self) -> None:
        episode = self.service.episodes.plan(self.episode_id)
        if episode is None:
            return
        dialog = ScenePlanEditorDialog(episode, episode.production_constraints, parent=self)
        dialog.sequence_spin.setValue(self.service.next_sequence_number(self.episode_id))
        remaining = self.service.remaining_runtime_seconds(self.episode_id)
        dialog.runtime_spin.setMaximum(max(1, remaining))
        dialog.runtime_spin.setValue(min(60, max(1, remaining)))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.create(
                episode_id=self.episode_id,
                sequence_number=values.sequence_number,
                title=values.title,
                story_scope=values.story_scope,
                production_objective=values.production_objective,
                target_runtime_seconds=values.target_runtime_seconds,
                setting_requirement=values.setting_requirement,
                required_events=values.required_events,
                continuity_in=values.continuity_in,
                continuity_out=values.continuity_out,
                scene_constraints=values.scene_constraints,
            )
        except ScenePlanningError as exc:
            QMessageBox.warning(self, "Scene Planner", str(exc))
            return
        self.refresh()

    def _edit(self) -> None:
        scene = self._selected()
        episode = self.service.episodes.plan(self.episode_id)
        if scene is None or episode is None or scene.status is not ScenePlanStatus.DRAFT:
            return
        dialog = ScenePlanEditorDialog(
            episode,
            episode.production_constraints,
            scene,
            self,
        )
        remaining = (
            self.service.remaining_runtime_seconds(self.episode_id) + scene.target_runtime_seconds
        )
        dialog.runtime_spin.setMaximum(max(1, remaining))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.update(
                scene.scene_id,
                title=values.title,
                story_scope=values.story_scope,
                production_objective=values.production_objective,
                target_runtime_seconds=values.target_runtime_seconds,
                setting_requirement=values.setting_requirement,
                required_events=values.required_events,
                continuity_in=values.continuity_in,
                continuity_out=values.continuity_out,
                scene_constraints=values.scene_constraints,
            )
        except ScenePlanningError as exc:
            QMessageBox.warning(self, "Scene Planner", str(exc))
            return
        self.refresh()

    def _open_shots(self) -> None:
        scene = self._selected()
        if (
            scene is None
            or self.shot_service is None
            or not self.service.is_production_ready(scene)
        ):
            return
        GovernedShotPlannerDialog(self.shot_service, scene, self).exec()
        self.refresh()
