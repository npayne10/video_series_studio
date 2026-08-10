"""Episode Planner UI for Phase 19.3.1."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
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
    EpisodePlanningError,
    EpisodePlanningService,
    EpisodePlanStatus,
    StoryRecord,
)


class EpisodePlanEditorDialog(QDialog):
    """Create or edit one production-useful episode plan."""

    def __init__(
        self,
        story: StoryRecord,
        plan: EpisodePlan | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.story = story
        self.plan = plan
        self.setObjectName("episodePlanEditorDialog")
        self.setWindowTitle("Edit Episode Plan" if plan else "New Episode Plan")
        self.setMinimumSize(620, 460)
        self.resize(780, 680)

        root = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        form = QFormLayout(content)

        self.sequence_spin = QSpinBox(content)
        self.sequence_spin.setObjectName("episodeSequence")
        self.sequence_spin.setRange(1, 999)
        self.sequence_spin.setValue(plan.sequence_number if plan else 1)
        self.sequence_spin.setEnabled(plan is None)

        self.title_edit = QLineEdit(plan.title if plan else "", content)
        self.title_edit.setObjectName("episodeTitle")
        self.scope_edit = QPlainTextEdit(plan.story_scope if plan else "", content)
        self.scope_edit.setObjectName("episodeStoryScope")
        self.objective_edit = QPlainTextEdit(plan.production_objective if plan else "", content)
        self.objective_edit.setObjectName("episodeProductionObjective")

        self.runtime_spin = QSpinBox(content)
        self.runtime_spin.setObjectName("episodeTargetRuntime")
        self.runtime_spin.setRange(60, 21600)
        self.runtime_spin.setSuffix(" sec")
        self.runtime_spin.setValue(plan.target_runtime_seconds if plan else 2700)

        self.continuity_in_edit = QPlainTextEdit(plan.continuity_in if plan else "", content)
        self.continuity_in_edit.setObjectName("episodeContinuityIn")
        self.continuity_out_edit = QPlainTextEdit(plan.continuity_out if plan else "", content)
        self.continuity_out_edit.setObjectName("episodeContinuityOut")
        constraints = "\n".join(plan.production_constraints) if plan else ""
        self.constraints_edit = QPlainTextEdit(constraints, content)
        self.constraints_edit.setObjectName("episodeProductionConstraints")

        form.addRow("Story", QLabel(f"{story.story_id} — {story.title}", content))
        form.addRow("Episode number", self.sequence_spin)
        form.addRow("Title *", self.title_edit)
        form.addRow("Story scope *", self.scope_edit)
        form.addRow("Production objective *", self.objective_edit)
        form.addRow("Target runtime", self.runtime_spin)
        form.addRow("Continuity into episode", self.continuity_in_edit)
        form.addRow("Continuity out of episode", self.continuity_out_edit)
        form.addRow("Production / realism constraints", self.constraints_edit)

        hint = QLabel(
            "Only record constraints that downstream production must enforce. "
            "Enter one constraint per line.",
            content,
        )
        hint.setWordWrap(True)
        form.addRow("", hint)

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
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Episode Planner", "Episode title is required.")
            return
        if not self.scope_edit.toPlainText().strip():
            QMessageBox.warning(self, "Episode Planner", "Story scope is required.")
            return
        if not self.objective_edit.toPlainText().strip():
            QMessageBox.warning(self, "Episode Planner", "Production objective is required.")
            return
        self.accept()

    def values(self) -> dict[str, object]:
        """Return normalized editor values."""
        constraints = tuple(
            line.strip()
            for line in self.constraints_edit.toPlainText().splitlines()
            if line.strip()
        )
        return {
            "sequence_number": self.sequence_spin.value(),
            "title": self.title_edit.text().strip(),
            "story_scope": self.scope_edit.toPlainText().strip(),
            "production_objective": self.objective_edit.toPlainText().strip(),
            "target_runtime_seconds": self.runtime_spin.value(),
            "continuity_in": self.continuity_in_edit.toPlainText().strip(),
            "continuity_out": self.continuity_out_edit.toPlainText().strip(),
            "production_constraints": constraints,
        }


class EpisodePlannerDialog(QDialog):
    """Plan episodes for one selected Story without duplicating later planning data."""

    def __init__(
        self,
        service: EpisodePlanningService,
        story: StoryRecord,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.story = story
        self.setObjectName("episodePlannerDialog")
        self.setWindowTitle(f"Episode Planner — {story.title}")
        self.setMinimumSize(760, 480)
        self.resize(980, 680)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Define only episode-level information required to turn the Story into production. "
            "Scene, shot, asset, camera, lighting and environment decisions belong to later planners.",
            self,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New Episode", self)
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

        self.table = QTableWidget(0, 6, self)
        self.table.setObjectName("episodePlannerTable")
        self.table.setHorizontalHeaderLabels(
            ["Episode", "Title", "Runtime", "Status", "Story Scope", "Objective"]
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
        """Reload plans for the selected Story."""
        plans = self.service.list_plans(story_id=self.story.story_id)
        self.table.setRowCount(len(plans))
        for row, plan in enumerate(plans):
            values = (
                plan.episode_id,
                plan.title,
                self._runtime_label(plan.target_runtime_seconds),
                plan.status.value.title(),
                plan.story_scope,
                plan.production_objective,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, plan.episode_id)
                self.table.setItem(row, column, item)
        self._update_actions()

    def _selected(self) -> EpisodePlan | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        episode_id = item.data(Qt.ItemDataRole.UserRole)
        return self.service.plan(episode_id) if isinstance(episode_id, str) else None

    def _update_actions(self) -> None:
        plan = self._selected()
        draft = plan is not None and plan.status is EpisodePlanStatus.DRAFT
        ready = plan is not None and plan.status is EpisodePlanStatus.READY
        self.edit_button.setEnabled(draft)
        self.delete_button.setEnabled(draft)
        self.ready_button.setEnabled(draft)
        self.draft_button.setEnabled(ready)

    def _new(self) -> None:
        dialog = EpisodePlanEditorDialog(self.story, parent=self)
        dialog.sequence_spin.setValue(self.service.next_sequence_number(self.story.story_id))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            self.service.create(story_id=self.story.story_id, **values)
        except (TypeError, EpisodePlanningError) as exc:
            QMessageBox.warning(self, "Episode Planner", str(exc))
            return
        self.refresh()

    def _edit(self) -> None:
        plan = self._selected()
        if plan is None or plan.status is not EpisodePlanStatus.DRAFT:
            return
        dialog = EpisodePlanEditorDialog(self.story, plan, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        values.pop("sequence_number", None)
        try:
            self.service.update(plan.episode_id, **values)
        except (TypeError, EpisodePlanningError) as exc:
            QMessageBox.warning(self, "Episode Planner", str(exc))
            return
        self.refresh()

    def _delete(self) -> None:
        plan = self._selected()
        if plan is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Episode Plan",
            f"Delete draft {plan.episode_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(plan.episode_id)
        except EpisodePlanningError as exc:
            QMessageBox.warning(self, "Episode Planner", str(exc))
            return
        self.refresh()

    def _mark_ready(self) -> None:
        plan = self._selected()
        if plan is None:
            return
        try:
            self.service.mark_ready(plan.episode_id)
        except EpisodePlanningError as exc:
            QMessageBox.warning(self, "Episode Planner", str(exc))
            return
        self.refresh()

    def _return_to_draft(self) -> None:
        plan = self._selected()
        if plan is None:
            return
        try:
            self.service.return_to_draft(plan.episode_id)
        except EpisodePlanningError as exc:
            QMessageBox.warning(self, "Episode Planner", str(exc))
            return
        self.refresh()

    @staticmethod
    def _runtime_label(seconds: int) -> str:
        minutes, remainder = divmod(seconds, 60)
        return f"{minutes}:{remainder:02d}"


def install_episode_planner(
    workspace: QWidget,
    service: EpisodePlanningService,
) -> QPushButton:
    """Install the Episode Planner action into the Story governance toolbar."""
    button = QPushButton("Episode Planner…", workspace)
    button.setObjectName("episodePlannerButton")
    button.setToolTip("Plan production episodes for the selected Story")
    button.setEnabled(False)

    panel = workspace.findChild(QWidget, "storyGovernancePanel")
    if panel is None or panel.layout() is None:
        raise RuntimeError("Story governance panel is unavailable")
    panel_layout = panel.layout()
    toolbar_item = panel_layout.itemAt(1)
    toolbar = toolbar_item.layout() if toolbar_item is not None else None
    if isinstance(toolbar, QHBoxLayout):
        toolbar.insertWidget(max(0, toolbar.count() - 1), button)

    def selected_story() -> StoryRecord | None:
        selector = getattr(workspace, "_selected_story", None)
        return selector() if callable(selector) else None

    def update_enabled() -> None:
        story = selected_story()
        button.setEnabled(story is not None and not story.archived)

    def open_planner() -> None:
        story = selected_story()
        if story is None:
            return
        EpisodePlannerDialog(service, story, workspace).exec()

    story_list = getattr(workspace, "story_list", None)
    if story_list is not None:
        story_list.currentItemChanged.connect(lambda _current, _previous: update_enabled())
    button.clicked.connect(open_planner)
    update_enabled()
    return button
