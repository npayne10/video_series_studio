"""Synchronize persisted ProductionTask state into the Phase 19.6.11 UI."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    ProductionTaskCompletionReconciliationService,
)
from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskLifecycleService,
    ProductionTaskPriority,
    ProductionTaskState,
)
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    JsonGeneratedMediaSelectionRepository,
)
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


def install_production_task_readiness_workspace(workspace_class: type[Any]) -> None:
    """Expose authoritative persisted task state and graph-derived readiness in the UI."""
    if getattr(workspace_class, "_production_task_readiness_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_refresh_tasks = workspace_type._refresh_production_tasks
    original_compile_tasks = workspace_type._compile_production_tasks
    original_task_context = workspace_type._production_task_context
    original_task_blocker = workspace_type._production_task_blocker

    def readiness_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        group = self.production_task_table.parentWidget()
        layout = group.layout()
        actions_layout = getattr(self, "production_task_actions_layout", None)
        if not isinstance(layout, QVBoxLayout) or actions_layout is None:
            return

        self.production_task_readiness_status = QLabel("", group)
        self.production_task_readiness_status.setObjectName("production_task_readiness_status")
        self.production_task_readiness_status.setWordWrap(True)
        self.production_task_refresh_readiness_button = QPushButton("Refresh Task Readiness", group)
        self.production_task_refresh_readiness_button.setObjectName(
            "production_task_refresh_readiness_button"
        )
        self.production_task_reconcile_completion_button = QPushButton(
            "Reconcile Task Completion",
            group,
        )
        self.production_task_reconcile_completion_button.setObjectName(
            "production_task_reconcile_completion_button"
        )
        self.production_task_reconcile_completion_button.setToolTip(
            "Complete the selected READY/RUNNING ProductionTask only when its governed "
            "authoritative Generated Media selection, technical validation, human approval "
            "and production-authority fingerprint all pass Phase 20.13 reconciliation."
        )
        self.production_task_supersede_button = QPushButton("Supersede Obsolete Task", group)
        self.production_task_supersede_button.setObjectName("production_task_supersede_button")
        self.production_task_supersede_button.setMinimumWidth(210)
        self.production_task_supersede_button.setMinimumHeight(28)
        self.production_task_supersede_button.setVisible(True)
        self.production_task_supersede_button.setToolTip(
            "Select an obsolete ProductionTask row. VSCS will preserve it as durable provenance "
            "and supersede it only when a governed replacement compiled from current READY UPD "
            "authority exists."
        )

        self.production_task_priority_label = QLabel("Scheduling Priority", group)
        self.production_task_priority_combo = QComboBox(group)
        self.production_task_priority_combo.setObjectName("production_task_priority_combo")
        for priority in ProductionTaskPriority:
            self.production_task_priority_combo.addItem(
                priority.name.title(),
                int(priority),
            )
        self.production_task_priority_apply_button = QPushButton(
            "Apply Scheduling Priority",
            group,
        )
        self.production_task_priority_apply_button.setObjectName(
            "production_task_priority_apply_button"
        )
        self.production_task_priority_apply_button.setToolTip(
            "Persist operator scheduling priority for the selected ProductionTask. "
            "Existing schedule revisions remain immutable; create and approve a new "
            "schedule revision after changing priority."
        )
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(self.production_task_priority_label)
        priority_layout.addWidget(self.production_task_priority_combo)
        priority_layout.addWidget(self.production_task_priority_apply_button)
        priority_layout.addStretch(1)

        # Anchor readiness/supersession actions in the compiler's existing visible
        # action row rather than injecting another child container around the table.
        # This toolbar already renders Compile Production Tasks reliably in the UI.
        insertion_index = max(actions_layout.count() - 1, 0)
        actions_layout.insertWidget(
            insertion_index,
            self.production_task_refresh_readiness_button,
        )
        actions_layout.insertWidget(
            insertion_index + 1,
            self.production_task_reconcile_completion_button,
        )
        actions_layout.insertWidget(
            insertion_index + 2,
            self.production_task_supersede_button,
        )

        table_index = layout.indexOf(self.production_task_table)
        layout.insertWidget(table_index, self.production_task_readiness_status)
        layout.insertLayout(table_index + 1, priority_layout)
        self.production_task_refresh_readiness_button.clicked.connect(
            self._production_task_refresh_readiness
        )
        self.production_task_reconcile_completion_button.clicked.connect(
            self._production_task_reconcile_completion
        )
        self.production_task_supersede_button.clicked.connect(
            self._production_task_supersede_obsolete
        )
        self.production_task_priority_apply_button.clicked.connect(
            self._production_task_apply_priority
        )
        self.production_task_table.itemSelectionChanged.connect(
            self._refresh_production_task_completion_eligibility
        )
        self.production_task_table.itemSelectionChanged.connect(
            self._refresh_production_task_supersession_eligibility
        )
        self.production_task_table.itemSelectionChanged.connect(
            self._refresh_production_task_priority_control
        )
        self._refresh_production_tasks()

    def _production_task_previous_shot_id(self: Any) -> str:
        shot_id = self._production_task_shot_id()
        if not shot_id:
            return ""
        package = self.packages.current_package(shot_id)
        if package is None:
            return ""
        continuity = getattr(package, "continuity", None)
        if not isinstance(continuity, dict):
            return ""

        # ContinuityCompilerService persists canonical continuity as
        # {"governed": {...}, "production": {...}}. ProductionTask dependency
        # authority must consume that compiled shape rather than the draft shape.
        for section_name in ("production", "governed"):
            section = continuity.get(section_name)
            if not isinstance(section, dict):
                continue
            previous = str(section.get("previous_shot_id") or "").strip().upper()
            if previous:
                return previous

        # Backward-compatible fallback for legacy flat continuity payloads.
        return str(continuity.get("previous_shot_id") or "").strip().upper()

    def _production_task_dependencies(self: Any) -> tuple[tuple[str, ...], str]:
        previous_shot_id = self._production_task_previous_shot_id()
        if not previous_shot_id:
            return (), ""
        production_id = self.production_task_production_id.text().strip()
        if not production_id:
            return (), "Production ID is required before resolving previous-Shot dependency."
        if not hasattr(self, "production_scheduling"):
            return (), "Production scheduling service is unavailable for dependency resolution."
        try:
            dependencies = self.production_scheduling.resolve_previous_shot_dependency(
                production_id,
                previous_shot_id,
            )
        except (ValueError, RuntimeError) as exc:
            return (), str(exc)
        return dependencies, ""

    def readiness_task_context(self: Any) -> Any:
        context = original_task_context(self)
        dependencies, blocker = self._production_task_dependencies()
        if blocker:
            raise ValueError(blocker)
        return replace(context, dependencies=dependencies)

    def readiness_task_blocker(self: Any) -> str:
        blocker = str(original_task_blocker(self) or "")
        if blocker:
            return blocker
        _dependencies, dependency_blocker = self._production_task_dependencies()
        return str(dependency_blocker or "")

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

    def _refresh_production_task_priority_control(self: Any, *_args: Any) -> None:
        if not hasattr(self, "production_task_priority_combo"):
            return
        selected = self._selected_persisted_production_task()
        if selected is None:
            self.production_task_priority_combo.setEnabled(False)
            self.production_task_priority_apply_button.setEnabled(False)
            self.production_task_priority_combo.setToolTip(
                "Select a persisted ProductionTask row to inspect scheduling priority."
            )
            return

        index = self.production_task_priority_combo.findData(int(selected.priority))
        if index >= 0:
            self.production_task_priority_combo.setCurrentIndex(index)

        editable = selected.state in {
            ProductionTaskState.PLANNED,
            ProductionTaskState.READY,
            ProductionTaskState.BLOCKED,
            ProductionTaskState.FAILED,
        }
        self.production_task_priority_combo.setEnabled(editable)
        self.production_task_priority_apply_button.setEnabled(editable)
        if editable:
            self.production_task_priority_combo.setToolTip(
                "Priority controls deterministic scheduling order. Higher-priority READY "
                "tasks are considered before older lower-priority tasks."
            )
        else:
            self.production_task_priority_combo.setToolTip(
                f"Priority cannot be changed while the task is {selected.state.value}."
            )

    def _production_task_apply_priority(self: Any) -> None:
        selected = self._selected_persisted_production_task()
        if selected is None:
            self.production_task_readiness_status.setText(
                "Select a persisted ProductionTask row before changing scheduling priority."
            )
            return

        raw_priority = self.production_task_priority_combo.currentData()
        try:
            priority = ProductionTaskPriority(int(raw_priority))
        except (TypeError, ValueError):
            self.production_task_readiness_status.setText(
                "Select a valid ProductionTask scheduling priority."
            )
            return

        previous = selected.priority
        try:
            updated = self.production_scheduling.update_task_priority(
                selected.task_id,
                priority,
            )
        except (ValueError, RuntimeError) as exc:
            self.production_task_readiness_status.setText(str(exc))
            QMessageBox.warning(self, "ProductionTask Scheduling Priority", str(exc))
            return

        self._refresh_persisted_production_tasks(updated.production_id)
        if previous is updated.priority:
            message = f"Scheduling priority for {updated.task_id} remains {updated.priority.name}."
        else:
            message = (
                f"Scheduling priority updated for {updated.task_id}: "
                f"{previous.name} -> {updated.priority.name}. "
                "Existing schedule revisions remain unchanged. Refresh Task Readiness, "
                "then create and approve a new schedule revision before compiling a queue."
            )
        self.production_task_readiness_status.setText(message)
        self._refresh_production_task_priority_control()
        self._refresh_production_task_supersession_eligibility()
        self._refresh_production_scheduling()

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
        if (
            selected.authority.fingerprint == replacement.authority.fingerprint
            and selected.dependencies == replacement.dependencies
        ):
            return (
                selected,
                replacement,
                "Selected ProductionTask is not obsolete against current governed "
                "UPD/dependency authority.",
            )
        return selected, replacement, ""

    def _refresh_production_task_supersession_eligibility(self: Any, *_args: Any) -> None:
        if not hasattr(self, "production_task_supersede_button"):
            return
        _selected, _replacement, blocker = self._production_task_supersession_context()
        self.production_task_supersede_button.setVisible(True)
        self.production_task_supersede_button.setEnabled(True)
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
            QMessageBox.information(self, "ProductionTask Supersession", blocker)
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
        self._refresh_production_task_priority_control()
        self._refresh_production_task_supersession_eligibility()

    def readiness_compile_tasks(self: Any) -> None:
        original_compile_tasks(self)
        self._refresh_production_tasks()

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
        self._refresh_production_task_priority_control()
        self._refresh_production_task_supersession_eligibility()
        self._refresh_production_scheduling()

    workspace_type.__init__ = readiness_init
    workspace_type._production_task_previous_shot_id = _production_task_previous_shot_id
    workspace_type._production_task_dependencies = _production_task_dependencies
    workspace_type._production_task_context = readiness_task_context
    workspace_type._production_task_blocker = readiness_task_blocker
    workspace_type._persisted_tasks_for_selected_shot = _persisted_tasks_for_selected_shot
    workspace_type._refresh_persisted_production_tasks = _refresh_persisted_production_tasks
    workspace_type._selected_persisted_production_task = _selected_persisted_production_task
    workspace_type._refresh_production_task_priority_control = (
        _refresh_production_task_priority_control
    )
    workspace_type._production_task_apply_priority = _production_task_apply_priority
    workspace_type._current_replacement_production_task = _current_replacement_production_task
    workspace_type._production_task_supersession_context = _production_task_supersession_context
    workspace_type._refresh_production_task_supersession_eligibility = (
        _refresh_production_task_supersession_eligibility
    )
    workspace_type._production_task_supersede_obsolete = _production_task_supersede_obsolete
    workspace_type._refresh_production_tasks = readiness_refresh_tasks
    workspace_type._compile_production_tasks = readiness_compile_tasks
    workspace_type._production_task_refresh_readiness = _production_task_refresh_readiness
    workspace_type._production_task_readiness_workspace_installed = True
