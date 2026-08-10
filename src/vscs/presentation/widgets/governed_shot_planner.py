"""Authoritative Shot Planner UI for Phase 19.3.3."""

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
    GovernedShotPlanningError,
    GovernedShotPlanningService,
    ScenePlan,
    ShotPlan,
    ShotPlanStatus,
)


@dataclass(frozen=True, slots=True)
class ShotPlanEditorValues:
    """Normalized values returned by the governed Shot Plan editor."""

    sequence_number: int
    title: str
    narrative_purpose: str
    production_objective: str
    target_runtime_seconds: int
    required_action: str
    dialogue_requirement: str
    continuity_in: str
    continuity_out: str
    shot_constraints: tuple[str, ...]


class ShotPlanEditorDialog(QDialog):
    """Edit only information owned by the Shot Planning layer."""

    def __init__(
        self,
        scene: ScenePlan,
        inherited_constraints: tuple[str, ...],
        plan: ShotPlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("shotPlanEditorDialog")
        self.setWindowTitle("Edit Shot Plan" if plan else "New Shot Plan")
        self.setMinimumSize(620, 460)
        self.resize(760, 660)

        self.sequence_spin = QSpinBox(self)
        self.sequence_spin.setRange(1, 9999)
        self.sequence_spin.setValue(plan.sequence_number if plan else 1)
        self.sequence_spin.setEnabled(plan is None)
        self.title_edit = QLineEdit(plan.title if plan else "", self)
        self.purpose_edit = QPlainTextEdit(plan.narrative_purpose if plan else "", self)
        self.objective_edit = QPlainTextEdit(plan.production_objective if plan else "", self)
        self.runtime_spin = QSpinBox(self)
        self.runtime_spin.setRange(1, max(1, scene.target_runtime_seconds))
        self.runtime_spin.setValue(plan.target_runtime_seconds if plan else min(5, scene.target_runtime_seconds))
        self.action_edit = QPlainTextEdit(plan.required_action if plan else "", self)
        self.dialogue_edit = QPlainTextEdit(plan.dialogue_requirement if plan else "", self)
        self.continuity_in_edit = QPlainTextEdit(plan.continuity_in if plan else "", self)
        self.continuity_out_edit = QPlainTextEdit(plan.continuity_out if plan else "", self)
        self.constraints_edit = QPlainTextEdit(
            "\n".join(plan.shot_constraints) if plan else "",
            self,
        )
        self.inherited_edit = QPlainTextEdit("\n".join(inherited_constraints), self)
        self.inherited_edit.setReadOnly(True)
        self.inherited_edit.setObjectName("shotInheritedSceneConstraints")

        for edit in (
            self.purpose_edit,
            self.objective_edit,
            self.action_edit,
            self.dialogue_edit,
            self.continuity_in_edit,
            self.continuity_out_edit,
            self.constraints_edit,
            self.inherited_edit,
        ):
            edit.setMinimumHeight(70)

        guidance = QLabel(
            "Define what this shot must accomplish. Asset identity, camera, lens, lighting and environment "
            "implementation belong to later specialist planners.",
            self,
        )
        guidance.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Sequence", self.sequence_spin)
        form.addRow("Title *", self.title_edit)
        form.addRow("Narrative purpose *", self.purpose_edit)
        form.addRow("Production objective *", self.objective_edit)
        form.addRow("Target runtime (seconds) *", self.runtime_spin)
        form.addRow("Required action *", self.action_edit)
        form.addRow("Dialogue requirement", self.dialogue_edit)
        form.addRow("Continuity in", self.continuity_in_edit)
        form.addRow("Continuity out", self.continuity_out_edit)
        form.addRow("Shot constraints", self.constraints_edit)
        form.addRow("Inherited Scene constraints", self.inherited_edit)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(guidance)
        content_layout.addLayout(form)
        content_layout.addStretch(1)
        scroll = QScrollArea(self)
        scroll.setObjectName("shotPlanScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(scroll, 1)
        root.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Shot Planner", "Shot title is required.")
            return
        if not self.purpose_edit.toPlainText().strip():
            QMessageBox.warning(self, "Shot Planner", "Narrative purpose is required.")
            return
        if not self.objective_edit.toPlainText().strip():
            QMessageBox.warning(self, "Shot Planner", "Production objective is required.")
            return
        if not self.action_edit.toPlainText().strip():
            QMessageBox.warning(self, "Shot Planner", "Required action is required.")
            return
        self.accept()

    def values(self) -> ShotPlanEditorValues:
        """Return normalized editor values."""
        constraints = tuple(
            line.strip()
            for line in self.constraints_edit.toPlainText().splitlines()
            if line.strip()
        )
        return ShotPlanEditorValues(
            sequence_number=self.sequence_spin.value(),
            title=self.title_edit.text().strip(),
            narrative_purpose=self.purpose_edit.toPlainText().strip(),
            production_objective=self.objective_edit.toPlainText().strip(),
            target_runtime_seconds=self.runtime_spin.value(),
            required_action=self.action_edit.toPlainText().strip(),
            dialogue_requirement=self.dialogue_edit.toPlainText().strip(),
            continuity_in=self.continuity_in_edit.toPlainText().strip(),
            continuity_out=self.continuity_out_edit.toPlainText().strip(),
            shot_constraints=constraints,
        )


class GovernedShotPlannerDialog(QDialog):
    """Plan authoritative Shots beneath one current Ready Scene Plan."""

    def __init__(
        self,
        service: GovernedShotPlanningService,
        scene: ScenePlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.scene_id = scene.scene_id
        self.setObjectName("governedShotPlannerDialog")
        self.setWindowTitle(f"Shot Planner — {scene.scene_id} — {scene.title}")
        self.setMinimumSize(840, 520)
        self.resize(1160, 760)

        root = QVBoxLayout(self)
        self.upstream_label = QLabel(self)
        self.upstream_label.setObjectName("shotPlannerUpstreamStatus")
        self.upstream_label.setWordWrap(True)
        root.addWidget(self.upstream_label)
        self.budget_label = QLabel(self)
        self.budget_label.setObjectName("shotPlannerRuntimeBudget")
        root.addWidget(self.budget_label)

        guidance = QLabel(
            "Shot Plans define narrative and production intent only. Asset resolution, camera, lighting and "
            "environment implementation remain downstream specialist responsibilities.",
            self,
        )
        guidance.setWordWrap(True)
        root.addWidget(guidance)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New Shot", self)
        self.edit_button = QPushButton("Edit", self)
        self.delete_button = QPushButton("Delete Draft", self)
        self.ready_button = QPushButton("Mark Ready", self)
        self.draft_button = QPushButton("Return to Draft", self)
        self.up_button = QPushButton("Move Up", self)
        self.down_button = QPushButton("Move Down", self)
        for button in (
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.ready_button,
            self.draft_button,
            self.up_button,
            self.down_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 7, self)
        self.table.setObjectName("governedShotPlannerTable")
        self.table.setHorizontalHeaderLabels(
            ["Shot", "Title", "Runtime", "Status", "Narrative Purpose", "Required Action", "Objective"]
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
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit())
        self.refresh()

    def refresh(self) -> None:
        """Reload governed and legacy-inactive shots for this Scene."""
        scene = self.service.scenes.plan(self.scene_id)
        if scene is None:
            self.upstream_label.setText("Scene Plan is unavailable.")
            self.table.setRowCount(0)
            self._update_actions()
            return

        current_ready = self.service.scenes.is_production_ready(scene)
        self.upstream_label.setText(
            "Upstream Scene: Ready and current — Shot Planning is enabled."
            if current_ready
            else "Upstream Scene is not production-ready. Existing Shot Plans remain visible but cannot advance."
        )
        allocated = self.service.allocated_runtime_seconds(self.scene_id)
        remaining = self.service.remaining_runtime_seconds(self.scene_id)
        self.budget_label.setText(
            f"Runtime budget: {self._runtime_label(allocated)} allocated / "
            f"{self._runtime_label(scene.target_runtime_seconds)} Scene target • "
            f"{self._runtime_label(remaining)} remaining"
        )

        plans = self.service.list_plans(scene_id=self.scene_id)
        legacy = self.service.legacy_shots_for_scene(self.scene_id)
        self.table.setRowCount(len(plans) + len(legacy))
        row = 0
        for plan in plans:
            status = plan.status.value.title()
            if not self.service.is_upstream_current(plan):
                status = f"{status} / Stale"
            values = (
                plan.shot_id,
                plan.title,
                self._runtime_label(plan.target_runtime_seconds),
                status,
                plan.narrative_purpose,
                plan.required_action,
                plan.production_objective,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, ("governed", plan.shot_id))
                self.table.setItem(row, column, item)
            row += 1

        for shot in legacy:
            values = (
                shot.shot_id,
                shot.title,
                self._runtime_label(round(shot.estimated_duration_seconds)),
                "Legacy / Inactive",
                shot.description,
                "Reference only",
                "Migrate explicitly before authoritative planning",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, ("legacy", shot.shot_id))
                self.table.setItem(row, column, item)
            row += 1
        self._update_actions()

    def _selected(self) -> ShotPlan | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple) or len(data) != 2 or data[0] != "governed":
            return None
        return self.service.plan(str(data[1]))

    def _update_actions(self) -> None:
        scene = self.service.scenes.plan(self.scene_id)
        scene_ready = scene is not None and self.service.scenes.is_production_ready(scene)
        shot = self._selected()
        draft = shot is not None and shot.status is ShotPlanStatus.DRAFT
        ready = shot is not None and shot.status is ShotPlanStatus.READY
        current = shot is not None and self.service.is_upstream_current(shot)
        self.new_button.setEnabled(scene_ready)
        self.edit_button.setEnabled(scene_ready and draft)
        self.delete_button.setEnabled(draft)
        self.ready_button.setEnabled(scene_ready and draft and current)
        self.draft_button.setEnabled(ready)
        row = self.table.currentRow()
        governed = shot is not None
        self.up_button.setEnabled(governed and row > 0)
        self.down_button.setEnabled(governed and row >= 0 and row < len(self.service.list_plans(scene_id=self.scene_id)) - 1)

    def _new(self) -> None:
        scene = self.service.scenes.plan(self.scene_id)
        if scene is None or not self.service.scenes.is_production_ready(scene):
            return
        dialog = ShotPlanEditorDialog(scene, scene.scene_constraints, parent=self)
        dialog.sequence_spin.setValue(self.service.next_sequence_number(self.scene_id))
        remaining = self.service.remaining_runtime_seconds(self.scene_id)
        dialog.runtime_spin.setMaximum(max(1, remaining))
        dialog.runtime_spin.setValue(min(5, max(1, remaining)))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.create(
                scene_id=self.scene_id,
                sequence_number=values.sequence_number,
                title=values.title,
                narrative_purpose=values.narrative_purpose,
                production_objective=values.production_objective,
                target_runtime_seconds=values.target_runtime_seconds,
                required_action=values.required_action,
                dialogue_requirement=values.dialogue_requirement,
                continuity_in=values.continuity_in,
                continuity_out=values.continuity_out,
                shot_constraints=values.shot_constraints,
            )
        except GovernedShotPlanningError as exc:
            QMessageBox.warning(self, "Shot Planner", str(exc))
            return
        self.refresh()

    def _edit(self) -> None:
        shot = self._selected()
        scene = self.service.scenes.plan(self.scene_id)
        if shot is None or scene is None or shot.status is not ShotPlanStatus.DRAFT:
            return
        dialog = ShotPlanEditorDialog(scene, scene.scene_constraints, shot, self)
        remaining = self.service.remaining_runtime_seconds(self.scene_id) + shot.target_runtime_seconds
        dialog.runtime_spin.setMaximum(max(1, remaining))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.update(
                shot.shot_id,
                title=values.title,
                narrative_purpose=values.narrative_purpose,
                production_objective=values.production_objective,
                target_runtime_seconds=values.target_runtime_seconds,
                required_action=values.required_action,
                dialogue_requirement=values.dialogue_requirement,
                continuity_in=values.continuity_in,
                continuity_out=values.continuity_out,
                shot_constraints=values.shot_constraints,
            )
        except GovernedShotPlanningError as exc:
            QMessageBox.warning(self, "Shot Planner", str(exc))
            return
        self.refresh()

    def _delete(self) -> None:
        shot = self._selected()
        if shot is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Shot Plan",
            f"Delete draft {shot.shot_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(shot.shot_id)
        except GovernedShotPlanningError as exc:
            QMessageBox.warning(self, "Shot Planner", str(exc))
            return
        self.refresh()

    def _mark_ready(self) -> None:
        shot = self._selected()
        if shot is None:
            return
        try:
            self.service.mark_ready(shot.shot_id)
        except GovernedShotPlanningError as exc:
            QMessageBox.warning(self, "Shot Planner", str(exc))
            return
        self.refresh()

    def _return_to_draft(self) -> None:
        shot = self._selected()
        if shot is None:
            return
        try:
            self.service.return_to_draft(shot.shot_id)
        except GovernedShotPlanningError as exc:
            QMessageBox.warning(self, "Shot Planner", str(exc))
            return
        self.refresh()

    def _move(self, offset: int) -> None:
        shot = self._selected()
        if shot is None:
            return
        plans = list(self.service.list_plans(scene_id=self.scene_id))
        index = next((i for i, plan in enumerate(plans) if plan.shot_id == shot.shot_id), -1)
        target = index + offset
        if index < 0 or target < 0 or target >= len(plans):
            return
        plans[index], plans[target] = plans[target], plans[index]
        try:
            self.service.reorder_scene(self.scene_id, tuple(plan.shot_id for plan in plans))
        except GovernedShotPlanningError as exc:
            QMessageBox.warning(self, "Shot Planner", str(exc))
            return
        self.refresh()
        self._select_identity(shot.shot_id)

    def _select_identity(self, shot_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.text() == shot_id:
                self.table.selectRow(row)
                return

    @staticmethod
    def _runtime_label(seconds: int) -> str:
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}:{remainder:02d}"
