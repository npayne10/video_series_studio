"""Synchronize persisted ProductionTask state into the Phase 19.6.11 UI."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from vscs.application.production_tasks import ProductionTask, ProductionTaskState


def install_production_task_readiness_workspace(workspace_class: type[Any]) -> None:
    """Expose authoritative persisted task state and graph-derived readiness in the UI."""
    if getattr(workspace_class, "_production_task_readiness_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_refresh_tasks = workspace_type._refresh_production_tasks

    def readiness_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        group = self.production_task_table.parentWidget()
        layout = group.layout()
        if not isinstance(layout, QVBoxLayout):
            return

        self.production_task_readiness_status = QLabel("", group)
        self.production_task_readiness_status.setObjectName("production_task_readiness_status")
        self.production_task_readiness_status.setWordWrap(True)
        self.production_task_refresh_readiness_button = QPushButton("Refresh Task Readiness", group)
        self.production_task_refresh_readiness_button.setObjectName(
            "production_task_refresh_readiness_button"
        )
        self.production_task_supersede_button = QPushButton("Supersede Obsolete Task", group)
        self.production_task_supersede_button.setObjectName("production_task_supersede_button")
        self.production_task_supersede_button.setToolTip(
            "Preserve the selected obsolete ProductionTask as durable provenance while marking "
            "it Superseded by the replacement compiled from the current READY UPD authority."
        )
        self.production_task_actions = QWidget(group)
        self.production_task_actions.setObjectName("production_task_actions")
        action_layout = QHBoxLayout(self.production_task_actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addWidget(self.production_task_refresh_readiness_button)
        action_layout.addWidget(self.production_task_supersede_button)
        action_layout.addStretch(1)

        table_index = layout.indexOf(self.production_task_table)
        layout.insertWidget(table_index, self.production_task_readiness_status)
        layout.insertWidget(table_index + 1, self.production_task_actions)
        self.production_task_refresh_readiness_button.clicked.connect(
            self._production_task_refresh_readiness
        )
        self.production_task_supersede_button.clicked.connect(
            self._production_task_supersede_obsolete
        )
        self.production_task_table.itemSelectionChanged.connect(
            self._refresh_production_task_supersession_eligibility
        )
        self._refresh_production_tasks()

    def _persisted_tasks_for_selected_shot(
        self: Any,
        production_id: str | None = None,
    ) -> tuple[ProductionTask, ...]:
        if not hasattr(self, "production_scheduling"):
            return ()
        editor = getattr(self, "production_task_production_id", None)
        normalized_production_id = (
            production_id.strip()
            if production_id is not None
            else str(editor.text() if editor is not None else "").strip()
        )
        shot_id = self._production_task_shot_id()
        if not normalized_production_id or not shot_id or not self.projects.is_project_open:
            return ()
        tasks = cast(
            tuple[ProductionTask, ...],
            self.production_scheduling.tasks(normalized_production_id),
        )
        filtered: tuple[ProductionTask, ...] = tuple(
            task for task in tasks if task.shot_id == shot_id
        )
        return filtered

    def _refresh_persisted_production_tasks(
        self: Any,
        production_id: str | None = None,
    ) -> tuple[ProductionTask, ...]:
        persisted = cast(
            tuple[ProductionTask, ...],
            self._persisted_tasks_for_selected_shot(production_id),
        )
        shot_id = self._production_task_shot_id()
        if persisted and shot_id:
            authoritative_production_id = persisted[0].production_id
            self.production_task_production_id.setText(authoritative_production_id)
            self._compiled_production_tasks[shot_id] = persisted
            self._render_production_tasks(persisted)
        return persisted

    def _selected_persisted_production_task(self: Any) -> ProductionTask | None:
        row = self.production_task_table.currentRow()
        if row < 0:
            return None
        item = self.production_task_table.item(row, 0)
        if item is None:
            return None
        task_id = item.text().strip()
        return next(
            (task for task in self._persisted_tasks_for_selected_shot() if task.task_id == task_id),
            None,
        )

    def _current_replacement_production_task(self: Any) -> ProductionTask | None:
        shot_id = self._production_task_shot_id()
        if not shot_id:
            return None
        try:
            current = self.production_task_compiler.compile_shot(
                shot_id,
                self._production_task_context(),
            )
        except (ValueError, RuntimeError):
            return None
        if not current:
            return None
        current_task = current[0]
        return next(
            (
                task
                for task in self._persisted_tasks_for_selected_shot()
                if task.task_id == current_task.task_id
                and task.authority.fingerprint == current_task.authority.fingerprint
            ),
            None,
        )

    def _production_task_supersession_context(
        self: Any,
    ) -> tuple[ProductionTask | None, ProductionTask | None, str]:
        selected = self._selected_persisted_production_task()
        if selected is None:
            return None, None, "Select an obsolete ProductionTask row to supersede."
        if selected.state is ProductionTaskState.SUPERSEDED:
            return selected, None, "Selected ProductionTask is already Superseded."
        if selected.state in {ProductionTaskState.CANCELLED, ProductionTaskState.COMPLETED}:
            return (
                selected,
                None,
                f"Selected ProductionTask is terminal ({selected.state.value}) and cannot be superseded.",
            )
        replacement = self._current_replacement_production_task()
        if replacement is None:
            return (
                selected,
                None,
                "Compile and persist the replacement ProductionTask from the current READY UPD first.",
            )
        if selected.task_id == replacement.task_id:
            return selected, replacement, "Selected ProductionTask is the current UPD authority."
        if selected.authority.fingerprint == replacement.authority.fingerprint:
            return (
                selected,
                replacement,
                "Selected ProductionTask is not obsolete against current UPD authority.",
            )
        return selected, replacement, ""

    def _refresh_production_task_supersession_eligibility(self: Any, *_args: Any) -> None:
        if not hasattr(self, "production_task_supersede_button"):
            return
        _selected, _replacement, blocker = self._production_task_supersession_context()
        self.production_task_supersede_button.setEnabled(not blocker)
        if blocker:
            self.production_task_supersede_button.setToolTip(blocker)
        else:
            self.production_task_supersede_button.setToolTip(
                "Mark the selected obsolete task Superseded while preserving it as durable provenance."
            )

    def _production_task_supersede_obsolete(self: Any) -> None:
        selected, replacement, blocker = self._production_task_supersession_context()
        if blocker or selected is None or replacement is None:
            self.production_task_readiness_status.setText(blocker)
            return
        answer = QMessageBox.question(
            self,
            "Supersede Obsolete ProductionTask",
            "Supersede obsolete task\n\n"
            f"{selected.task_id}\n\n"
            "with current governed replacement\n\n"
            f"{replacement.task_id}?\n\n"
            "The obsolete task will be preserved as durable provenance and will no longer be "
            "eligible for scheduling.",
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        reason = (
            "Replaced by current READY UPD authority via Production Tasks UI; "
            f"replacement={replacement.task_id}"
        )
        try:
            updated = self.production_scheduling.supersede_task(
                selected.task_id,
                replacement_task_id=replacement.task_id,
                reason=reason,
            )
        except (ValueError, RuntimeError) as exc:
            self.production_task_readiness_status.setText(str(exc))
            QMessageBox.warning(self, "ProductionTask Supersession", str(exc))
            return
        self._refresh_persisted_production_tasks(updated.production_id)
        self.production_task_readiness_status.setText(
            f"Superseded {updated.task_id}. Current replacement: {replacement.task_id}. "
            "Refresh Task Readiness before creating a new schedule revision."
        )
        self._refresh_production_task_supersession_eligibility()
        self._refresh_production_scheduling()

    def readiness_refresh_tasks(self: Any) -> None:
        editor = getattr(self, "production_task_production_id", None)
        requested_production_id = str(editor.text() if editor is not None else "").strip()
        original_refresh_tasks(self)

        # Base ProductionPackageWorkspace construction invokes refresh() before the
        # Phase 19.6.2 ProductionTask controls and Phase 19.6.11 scheduling facade
        # have been created. The wrapper must remain inert during that early pass.
        if (
            not hasattr(self, "production_task_table")
            or not hasattr(self, "production_task_production_id")
            or not hasattr(self, "production_scheduling")
        ):
            return

        persisted = cast(
            tuple[ProductionTask, ...],
            self._refresh_persisted_production_tasks(requested_production_id or None),
        )
        if not hasattr(self, "production_task_readiness_status"):
            return
        if persisted:
            states = ", ".join(sorted({task.state.value for task in persisted}))
            self.production_task_readiness_status.setText(
                f"Authoritative persisted ProductionTask state: {states}. "
                "Readiness is derived from the dependency graph, not set manually."
            )
        else:
            self.production_task_readiness_status.setText(
                "No persisted ProductionTask exists for the selected Shot. Compile the task first."
            )
        enabled = bool(
            persisted
            and self.production_task_production_id.text().strip()
            and self.projects.is_project_open
        )
        self.production_task_refresh_readiness_button.setEnabled(enabled)
        self._refresh_production_task_supersession_eligibility()

    def _production_task_refresh_readiness(self: Any) -> None:
        production_id = self.production_task_production_id.text().strip()
        if not production_id:
            return
        try:
            result = self.production_scheduling.refresh_readiness(production_id)
        except (ValueError, RuntimeError) as exc:
            self.production_task_readiness_status.setText(str(exc))
            return
        persisted = cast(
            tuple[ProductionTask, ...],
            self._refresh_persisted_production_tasks(production_id),
        )
        states = ", ".join(sorted({task.state.value for task in persisted})) or "none"
        self.production_task_readiness_status.setText(
            f"Readiness refreshed: {len(result.transitions)} transition(s). "
            f"Current authoritative state: {states}."
        )
        self._refresh_production_task_supersession_eligibility()
        self._refresh_production_scheduling()

    workspace_type.__init__ = readiness_init
    workspace_type._persisted_tasks_for_selected_shot = _persisted_tasks_for_selected_shot
    workspace_type._refresh_persisted_production_tasks = _refresh_persisted_production_tasks
    workspace_type._selected_persisted_production_task = _selected_persisted_production_task
    workspace_type._current_replacement_production_task = _current_replacement_production_task
    workspace_type._production_task_supersession_context = _production_task_supersession_context
    workspace_type._refresh_production_task_supersession_eligibility = (
        _refresh_production_task_supersession_eligibility
    )
    workspace_type._production_task_supersede_obsolete = _production_task_supersede_obsolete
    workspace_type._refresh_production_tasks = readiness_refresh_tasks
    workspace_type._production_task_refresh_readiness = _production_task_refresh_readiness
    workspace_type._production_task_readiness_workspace_installed = True
