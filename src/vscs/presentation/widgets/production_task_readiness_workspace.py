"""Synchronize persisted ProductionTask state into the Phase 19.6.11 UI."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout


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
        self.production_task_refresh_readiness_button = QPushButton(
            "Refresh Task Readiness", group
        )
        self.production_task_refresh_readiness_button.setObjectName(
            "production_task_refresh_readiness_button"
        )
        table_index = layout.indexOf(self.production_task_table)
        layout.insertWidget(table_index, self.production_task_readiness_status)
        layout.insertWidget(table_index + 1, self.production_task_refresh_readiness_button)
        self.production_task_refresh_readiness_button.clicked.connect(
            self._production_task_refresh_readiness
        )
        self._refresh_production_tasks()

    def _persisted_tasks_for_selected_shot(
        self: Any,
        production_id: str | None = None,
    ) -> tuple[Any, ...]:
        if not hasattr(self, "production_scheduling"):
            return ()
        normalized_production_id = (
            production_id.strip()
            if production_id is not None
            else self.production_task_production_id.text().strip()
        )
        shot_id = self._production_task_shot_id()
        if (
            not normalized_production_id
            or not shot_id
            or not self.projects.is_project_open
        ):
            return ()
        tasks = self.production_scheduling.tasks(normalized_production_id)
        return tuple(task for task in tasks if task.shot_id == shot_id)

    def _refresh_persisted_production_tasks(
        self: Any,
        production_id: str | None = None,
    ) -> tuple[Any, ...]:
        persisted = self._persisted_tasks_for_selected_shot(production_id)
        shot_id = self._production_task_shot_id()
        if persisted and shot_id:
            authoritative_production_id = persisted[0].production_id
            self.production_task_production_id.setText(authoritative_production_id)
            self._compiled_production_tasks[shot_id] = persisted
            self._render_production_tasks(persisted)
        return persisted

    def readiness_refresh_tasks(self: Any) -> None:
        requested_production_id = self.production_task_production_id.text().strip()
        original_refresh_tasks(self)
        if not hasattr(self, "production_scheduling"):
            return
        persisted = self._refresh_persisted_production_tasks(requested_production_id)
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

    def _production_task_refresh_readiness(self: Any) -> None:
        production_id = self.production_task_production_id.text().strip()
        if not production_id:
            return
        try:
            result = self.production_scheduling.refresh_readiness(production_id)
        except (ValueError, RuntimeError) as exc:
            self.production_task_readiness_status.setText(str(exc))
            return
        persisted = self._refresh_persisted_production_tasks(production_id)
        states = ", ".join(sorted({task.state.value for task in persisted})) or "none"
        self.production_task_readiness_status.setText(
            f"Readiness refreshed: {len(result.transitions)} transition(s). "
            f"Current authoritative state: {states}."
        )
        self._refresh_production_scheduling()

    workspace_type.__init__ = readiness_init
    workspace_type._persisted_tasks_for_selected_shot = _persisted_tasks_for_selected_shot
    workspace_type._refresh_persisted_production_tasks = _refresh_persisted_production_tasks
    workspace_type._refresh_production_tasks = readiness_refresh_tasks
    workspace_type._production_task_refresh_readiness = _production_task_refresh_readiness
    workspace_type._production_task_readiness_workspace_installed = True
