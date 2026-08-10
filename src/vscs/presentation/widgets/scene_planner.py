"""Scene Planner UI for Phase 19.3.2."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.story import (
    EpisodePlan,
    EpisodePlanStatus,
    ScenePlan,
    ScenePlanningError,
    ScenePlanningService,
    ScenePlanStatus,
)


@dataclass(frozen=True, slots=True)
class ScenePlanEditorValues:
    """Strongly typed values returned by the Scene Plan editor."""

    sequence_number: int
    title: str
    story_scope: str
    production_objective: str
    target_runtime_seconds: int
    setting_requirement: str
    required_events: tuple[str, ...]
    continuity_in: str
    continuity_out: str
    scene_constraints: tuple[str, ...]


class ScenePlanEditorDialog(QDialog):
    """Create or edit one production-focused scene plan."""

    def __init__(
        self,
        episode: EpisodePlan,
        inherited_constraints: tuple[str, ...],
        plan: ScenePlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.episode = episode
        self.plan = plan
        self.setObjectName("scenePlanEditorDialog")
        self.setWindowTitle("Edit Scene Plan" if plan else "New Scene Plan")
        self.setMinimumSize(620, 440)
        self.resize(800, 700)

        root = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setObjectName("scenePlanScrollArea")
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        form = QFormLayout(content)

        self.sequence_spin = QSpinBox(content)
        self.sequence_spin.setObjectName("sceneSequence")
        self.sequence_spin.setRange(1, 999)
        self.sequence_spin.setValue(plan.sequence_number if plan else 1)
        self.sequence_spin.setEnabled(plan is None)

        self.title_edit = QLineEdit(plan.title if plan else "", content)
        self.title_edit.setObjectName("scenePlanTitle")
        self.scope_edit = QPlainTextEdit(plan.story_scope if plan else "", content)
        self.scope_edit.setObjectName("sceneStoryScope")
        self.objective_edit = QPlainTextEdit(plan.production_objective if plan else "", content)
        self.objective_edit.setObjectName("sceneProductionObjective")

        self.runtime_spin = QSpinBox(content)
        self.runtime_spin.setObjectName("sceneTargetRuntime")
        self.runtime_spin.setRange(1, max(1, episode.target_runtime_seconds))
        self.runtime_spin.setSuffix(" sec")
        self.runtime_spin.setValue(plan.target_runtime_seconds if plan else 60)

        self.setting_edit = QLineEdit(plan.setting_requirement if plan else "", content)
        self.setting_edit.setObjectName("sceneSettingRequirement")

        events = "\n".join(plan.required_events) if plan else ""
        self.events_edit = QPlainTextEdit(events, content)
        self.events_edit.setObjectName("sceneRequiredEvents")

        self.continuity_in_edit = QPlainTextEdit(plan.continuity_in if plan else "", content)
        self.continuity_in_edit.setObjectName("sceneContinuityIn")
        self.continuity_out_edit = QPlainTextEdit(plan.continuity_out if plan else "", content)
        self.continuity_out_edit.setObjectName("sceneContinuityOut")

        constraints = "\n".join(plan.scene_constraints) if plan else ""
        self.constraints_edit = QPlainTextEdit(constraints, content)
        self.constraints_edit.setObjectName("sceneProductionConstraints")

        inherited = QPlainTextEdit("\n".join(inherited_constraints), content)
        inherited.setObjectName("sceneInheritedEpisodeConstraints")
        inherited.setReadOnly(True)
        inherited.setPlaceholderText("No Episode-level constraints")

        form.addRow("Episode", QLabel(f"{episode.episode_id} — {episode.title}", content))
        form.addRow("Scene number", self.sequence_spin)
        form.addRow("Title *", self.title_edit)
        form.addRow("Story scope *", self.scope_edit)
        form.addRow("Production objective *", self.objective_edit)
        form.addRow("Target runtime", self.runtime_spin)
        form.addRow("Setting requirement *", self.setting_edit)
        form.addRow("Required story events *", self.events_edit)
        form.addRow("Continuity into scene", self.continuity_in_edit)
        form.addRow("Continuity out of scene", self.continuity_out_edit)
        form.addRow("Inherited Episode constraints", inherited)
        form.addRow("Scene-specific constraints", self.constraints_edit)

        guidance = QLabel(
            "Enter one required event or scene-specific constraint per line. "
            "Do not plan assets, camera, lighting, environment parameters, shots, prompts, or render settings here; "
            "those are resolved by later production planners.",
            content,
        )
        guidance.setWordWrap(True)
        form.addRow("", guidance)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        required = (
            (self.title_edit.text(), "Scene title"),
            (self.scope_edit.toPlainText(), "Story scope"),
            (self.objective_edit.toPlainText(), "Production objective"),
            (self.setting_edit.text(), "Setting requirement"),
            (self.events_edit.toPlainText(), "At least one required story event"),
        )
        for value, label in required:
            if not value.strip():
                QMessageBox.warning(self, "Scene Planner", f"{label} is required.")
                return
        self.accept()

    def values(self) -> ScenePlanEditorValues:
        """Return normalized editor values."""
        events = tuple(
            line.strip() for line in self.events_edit.toPlainText().splitlines() if line.strip()
        )
        constraints = tuple(
            line.strip()
            for line in self.constraints_edit.toPlainText().splitlines()
            if line.strip()
        )
        return ScenePlanEditorValues(
            sequence_number=self.sequence_spin.value(),
            title=self.title_edit.text().strip(),
            story_scope=self.scope_edit.toPlainText().strip(),
            production_objective=self.objective_edit.toPlainText().strip(),
            target_runtime_seconds=self.runtime_spin.value(),
            setting_requirement=self.setting_edit.text().strip(),
            required_events=events,
            continuity_in=self.continuity_in_edit.toPlainText().strip(),
            continuity_out=self.continuity_out_edit.toPlainText().strip(),
            scene_constraints=constraints,
        )


class ScenePlannerDialog(QDialog):
    """Plan production scenes beneath one selected Episode Plan."""

    def __init__(
        self,
        service: ScenePlanningService,
        episode: EpisodePlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.episode_id = episode.episode_id
        self.setObjectName("scenePlannerDialog")
        self.setWindowTitle(f"Scene Planner — {episode.episode_id} — {episode.title}")
        self.setMinimumSize(780, 500)
        self.resize(1080, 720)

        root = QVBoxLayout(self)
        self.upstream_label = QLabel(self)
        self.upstream_label.setObjectName("scenePlannerUpstreamStatus")
        self.upstream_label.setWordWrap(True)
        root.addWidget(self.upstream_label)

        self.budget_label = QLabel(self)
        self.budget_label.setObjectName("scenePlannerRuntimeBudget")
        root.addWidget(self.budget_label)

        guidance = QLabel(
            "Scene Plans define only what each scene must accomplish for Shot Planning. "
            "Asset resolution, camera, lighting and environment implementation belong to later planners.",
            self,
        )
        guidance.setWordWrap(True)
        root.addWidget(guidance)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New Scene", self)
        self.edit_button = QPushButton("Edit", self)
        self.delete_button = QPushButton("Delete Draft", self)
        self.ready_button = QPushButton("Mark Ready", self)
        self.draft_button = QPushButton("Return to Draft", self)
        for button in (
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.ready_button,
            self.draft_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 7, self)
        self.table.setObjectName("scenePlannerTable")
        self.table.setHorizontalHeaderLabels(
            ["Scene", "Title", "Runtime", "Status", "Setting", "Story Scope", "Objective"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_buttons.rejected.connect(self.reject)
        root.addWidget(close_buttons)

        self.new_button.clicked.connect(self._new)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.ready_button.clicked.connect(self._mark_ready)
        self.draft_button.clicked.connect(self._return_to_draft)
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit())
        self.refresh()

    def refresh(self) -> None:
        """Reload scene plans, budget and upstream state."""
        episode = self.service.episodes.plan(self.episode_id)
        if episode is None:
            self.upstream_label.setText("Episode Plan is unavailable.")
            self.new_button.setEnabled(False)
            self.table.setRowCount(0)
            return

        upstream_ready = episode.status is EpisodePlanStatus.READY
        self.upstream_label.setText(
            "Upstream Episode: Ready — scene creation/editing is enabled."
            if upstream_ready
            else "Upstream Episode: Draft — existing scenes remain visible, but planning changes are blocked until the Episode is Ready."
        )
        allocated = self.service.allocated_runtime_seconds(self.episode_id)
        remaining = self.service.remaining_runtime_seconds(self.episode_id)
        self.budget_label.setText(
            f"Runtime budget: {self._runtime_label(allocated)} allocated / "
            f"{self._runtime_label(episode.target_runtime_seconds)} Episode target • "
            f"{self._runtime_label(remaining)} remaining"
        )

        plans = self.service.list_plans(episode_id=self.episode_id)
        self.table.setRowCount(len(plans))
        for row, plan in enumerate(plans):
            status = plan.status.value.title()
            if not self.service.is_upstream_current(plan):
                status = f"{status} / Stale"
            values = (
                plan.scene_id,
                plan.title,
                self._runtime_label(plan.target_runtime_seconds),
                status,
                plan.setting_requirement,
                plan.story_scope,
                plan.production_objective,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, plan.scene_id)
                self.table.setItem(row, column, item)
        self._update_actions()

    def _selected(self) -> ScenePlan | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        scene_id = item.data(Qt.ItemDataRole.UserRole)
        return self.service.plan(scene_id) if isinstance(scene_id, str) else None

    def _update_actions(self) -> None:
        episode = self.service.episodes.plan(self.episode_id)
        upstream_ready = episode is not None and episode.status is EpisodePlanStatus.READY
        scene = self._selected()
        draft = scene is not None and scene.status is ScenePlanStatus.DRAFT
        ready = scene is not None and scene.status is ScenePlanStatus.READY
        current = scene is not None and self.service.is_upstream_current(scene)
        self.new_button.setEnabled(upstream_ready)
        self.edit_button.setEnabled(upstream_ready and draft)
        self.delete_button.setEnabled(draft)
        self.ready_button.setEnabled(upstream_ready and draft and current)
        self.draft_button.setEnabled(ready)

    def _new(self) -> None:
        episode = self.service.episodes.plan(self.episode_id)
        if episode is None or episode.status is not EpisodePlanStatus.READY:
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
        if (
            scene is None
            or episode is None
            or episode.status is not EpisodePlanStatus.READY
            or scene.status is not ScenePlanStatus.DRAFT
        ):
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

    def _delete(self) -> None:
        scene = self._selected()
        if scene is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Scene Plan",
            f"Delete draft {scene.scene_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(scene.scene_id)
        except ScenePlanningError as exc:
            QMessageBox.warning(self, "Scene Planner", str(exc))
            return
        self.refresh()

    def _mark_ready(self) -> None:
        scene = self._selected()
        if scene is None:
            return
        try:
            self.service.mark_ready(scene.scene_id)
        except ScenePlanningError as exc:
            QMessageBox.warning(self, "Scene Planner", str(exc))
            return
        self.refresh()

    def _return_to_draft(self) -> None:
        scene = self._selected()
        if scene is None:
            return
        try:
            self.service.return_to_draft(scene.scene_id)
        except ScenePlanningError as exc:
            QMessageBox.warning(self, "Scene Planner", str(exc))
            return
        self.refresh()

    @staticmethod
    def _runtime_label(seconds: int) -> str:
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}:{remainder:02d}"
