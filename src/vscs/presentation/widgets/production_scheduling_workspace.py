"""Production Scheduling UI integration for Phase 19.6.11."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.production_tasks import (
    ProductionCapability,
    ProductionResource,
    ProductionResourceState,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewState,
    ProductionSchedulingUiError,
    ProductionSchedulingUiService,
    ProductionWorker,
    ProductionWorkerState,
)
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


def install_production_scheduling_workspace(workspace_class: type[Any]) -> None:
    """Add scheduling/review/monitoring to the existing Production Planning workspace."""
    if getattr(workspace_class, "_production_scheduling_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_refresh = workspace_type.refresh
    original_selection = workspace_type._selection_changed
    original_compile_tasks = workspace_type._compile_production_tasks

    def scheduling_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)

        def task_repository() -> JsonProductionTaskRepository:
            directory = self.projects.project_directory
            if directory is None:
                raise ProductionSchedulingUiError(
                    "Open a VSCS project before using Production Scheduling"
                )
            return JsonProductionTaskRepository(directory / "production" / "scheduling" / "tasks")

        def schedule_repository() -> JsonProductionScheduleRepository:
            directory = self.projects.project_directory
            if directory is None:
                raise ProductionSchedulingUiError(
                    "Open a VSCS project before using Production Scheduling"
                )
            return JsonProductionScheduleRepository(
                directory / "production" / "scheduling" / "schedules"
            )

        self.production_scheduling = ProductionSchedulingUiService(
            task_repository,
            schedule_repository,
        )
        self._build_production_scheduling_tab()
        self._refresh_production_scheduling()

    def _build_production_scheduling_tab(self: Any) -> None:
        tab = QWidget(self.compiler_tabs)
        tab.setObjectName("production_scheduling_tab")
        layout = QVBoxLayout(tab)

        guidance = QLabel(
            "Schedule persisted READY ProductionTasks onto provider-neutral resources; "
            "review the schedule explicitly; compile the approved ProductionQueue; and "
            "inspect runtime diagnostics. This tab does not choose provider workflows "
            "or start external execution.",
            tab,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.production_scheduling_status = QLabel("", tab)
        self.production_scheduling_status.setObjectName("production_scheduling_status")
        self.production_scheduling_status.setWordWrap(True)
        layout.addWidget(self.production_scheduling_status)

        resource_group = QGroupBox("Session Resources", tab)
        resource_layout = QVBoxLayout(resource_group)
        resource_form = QFormLayout()
        self.scheduling_resource_id = QLineEdit(resource_group)
        self.scheduling_resource_id.setObjectName("scheduling_resource_id")
        self.scheduling_resource_capabilities = QLineEdit(resource_group)
        self.scheduling_resource_capabilities.setObjectName("scheduling_resource_capabilities")
        self.scheduling_resource_capabilities.setPlaceholderText(
            "video_generation, image_generation, audio_generation"
        )
        self.scheduling_resource_state = QComboBox(resource_group)
        self.scheduling_resource_state.setObjectName("scheduling_resource_state")
        for resource_state in ProductionResourceState:
            self.scheduling_resource_state.addItem(
                resource_state.value.title(),
                resource_state,
            )
        resource_form.addRow("Resource ID", self.scheduling_resource_id)
        resource_form.addRow("Capabilities", self.scheduling_resource_capabilities)
        resource_form.addRow("State", self.scheduling_resource_state)
        resource_layout.addLayout(resource_form)
        self.scheduling_register_resource_button = QPushButton(
            "Register / Update Resource", resource_group
        )
        self.scheduling_register_resource_button.setObjectName(
            "scheduling_register_resource_button"
        )
        resource_layout.addWidget(self.scheduling_register_resource_button)
        self.scheduling_resource_table = _table(
            resource_group,
            "scheduling_resource_table",
            ("Resource", "State", "Capabilities"),
        )
        resource_layout.addWidget(self.scheduling_resource_table)
        layout.addWidget(resource_group)

        schedule_group = QGroupBox("Schedule Revision & Human Review", tab)
        schedule_layout = QVBoxLayout(schedule_group)
        schedule_actions = QHBoxLayout()
        self.scheduling_refresh_readiness_button = QPushButton(
            "Refresh Task Readiness", schedule_group
        )
        self.scheduling_refresh_readiness_button.setObjectName(
            "scheduling_refresh_readiness_button"
        )
        self.scheduling_create_revision_button = QPushButton(
            "Create Schedule Revision", schedule_group
        )
        self.scheduling_create_revision_button.setObjectName("scheduling_create_revision_button")
        schedule_actions.addWidget(self.scheduling_refresh_readiness_button)
        schedule_actions.addWidget(self.scheduling_create_revision_button)
        schedule_actions.addStretch(1)
        schedule_layout.addLayout(schedule_actions)
        self.scheduling_review_status = QLabel("No schedule revision exists.", schedule_group)
        self.scheduling_review_status.setObjectName("scheduling_review_status")
        self.scheduling_review_status.setWordWrap(True)
        schedule_layout.addWidget(self.scheduling_review_status)
        self.scheduling_schedule_table = _table(
            schedule_group,
            "scheduling_schedule_table",
            ("Result", "Task", "Resource / Reason", "Priority", "Capabilities"),
        )
        schedule_layout.addWidget(self.scheduling_schedule_table)
        review_form = QFormLayout()
        self.scheduling_reviewer = QLineEdit(schedule_group)
        self.scheduling_reviewer.setObjectName("scheduling_reviewer")
        self.scheduling_review_notes = QTextEdit(schedule_group)
        self.scheduling_review_notes.setObjectName("scheduling_review_notes")
        self.scheduling_review_notes.setMaximumHeight(80)
        review_form.addRow("Reviewer", self.scheduling_reviewer)
        review_form.addRow("Review notes", self.scheduling_review_notes)
        schedule_layout.addLayout(review_form)
        review_actions = QHBoxLayout()
        self.scheduling_approve_button = QPushButton("Approve Schedule", schedule_group)
        self.scheduling_approve_button.setObjectName("scheduling_approve_button")
        self.scheduling_reject_button = QPushButton("Reject Schedule", schedule_group)
        self.scheduling_reject_button.setObjectName("scheduling_reject_button")
        review_actions.addWidget(self.scheduling_approve_button)
        review_actions.addWidget(self.scheduling_reject_button)
        review_actions.addStretch(1)
        schedule_layout.addLayout(review_actions)
        layout.addWidget(schedule_group)

        queue_group = QGroupBox("Production Queue & Monitoring", tab)
        queue_layout = QVBoxLayout(queue_group)
        queue_actions = QHBoxLayout()
        self.scheduling_compile_queue_button = QPushButton("Compile Approved Queue", queue_group)
        self.scheduling_compile_queue_button.setObjectName("scheduling_compile_queue_button")
        self.scheduling_refresh_monitoring_button = QPushButton("Refresh Monitoring", queue_group)
        self.scheduling_refresh_monitoring_button.setObjectName(
            "scheduling_refresh_monitoring_button"
        )
        self.scheduling_recover_button = QPushButton("Recover Expired Leases", queue_group)
        self.scheduling_recover_button.setObjectName("scheduling_recover_button")
        queue_actions.addWidget(self.scheduling_compile_queue_button)
        queue_actions.addWidget(self.scheduling_refresh_monitoring_button)
        queue_actions.addWidget(self.scheduling_recover_button)
        queue_actions.addStretch(1)
        queue_layout.addLayout(queue_actions)
        self.scheduling_queue_table = _table(
            queue_group,
            "scheduling_queue_table",
            ("Entry", "Task", "Type", "Resource", "State", "Attempts"),
        )
        queue_layout.addWidget(self.scheduling_queue_table)
        self.scheduling_monitoring_summary = QTextEdit(queue_group)
        self.scheduling_monitoring_summary.setObjectName("scheduling_monitoring_summary")
        self.scheduling_monitoring_summary.setReadOnly(True)
        self.scheduling_monitoring_summary.setMaximumHeight(130)
        queue_layout.addWidget(self.scheduling_monitoring_summary)
        layout.addWidget(queue_group, 1)

        worker_group = QGroupBox("Session Workers", tab)
        worker_layout = QVBoxLayout(worker_group)
        worker_form = QFormLayout()
        self.scheduling_worker_id = QLineEdit(worker_group)
        self.scheduling_worker_id.setObjectName("scheduling_worker_id")
        self.scheduling_worker_resource_id = QLineEdit(worker_group)
        self.scheduling_worker_resource_id.setObjectName("scheduling_worker_resource_id")
        self.scheduling_worker_capabilities = QLineEdit(worker_group)
        self.scheduling_worker_capabilities.setObjectName("scheduling_worker_capabilities")
        self.scheduling_worker_state = QComboBox(worker_group)
        self.scheduling_worker_state.setObjectName("scheduling_worker_state")
        for worker_state in ProductionWorkerState:
            self.scheduling_worker_state.addItem(
                worker_state.value.title(),
                worker_state,
            )
        worker_form.addRow("Worker ID", self.scheduling_worker_id)
        worker_form.addRow("Resource ID", self.scheduling_worker_resource_id)
        worker_form.addRow("Capabilities", self.scheduling_worker_capabilities)
        worker_form.addRow("State", self.scheduling_worker_state)
        worker_layout.addLayout(worker_form)
        self.scheduling_register_worker_button = QPushButton("Register Worker", worker_group)
        self.scheduling_register_worker_button.setObjectName("scheduling_register_worker_button")
        worker_layout.addWidget(self.scheduling_register_worker_button)
        self.scheduling_worker_table = _table(
            worker_group,
            "scheduling_worker_table",
            ("Worker", "Resource", "State", "Capabilities"),
        )
        worker_layout.addWidget(self.scheduling_worker_table)
        layout.addWidget(worker_group)

        self.compiler_tabs.addTab(tab, "Scheduling")
        self.scheduling_register_resource_button.clicked.connect(self._scheduling_register_resource)
        self.scheduling_register_worker_button.clicked.connect(self._scheduling_register_worker)
        self.scheduling_refresh_readiness_button.clicked.connect(self._scheduling_refresh_readiness)
        self.scheduling_create_revision_button.clicked.connect(self._scheduling_create_revision)
        self.scheduling_approve_button.clicked.connect(self._scheduling_approve)
        self.scheduling_reject_button.clicked.connect(self._scheduling_reject)
        self.scheduling_compile_queue_button.clicked.connect(self._scheduling_compile_queue)
        self.scheduling_refresh_monitoring_button.clicked.connect(
            self._refresh_production_scheduling
        )
        self.scheduling_recover_button.clicked.connect(self._scheduling_recover)

    def _scheduling_production_id(self: Any) -> str:
        editor = getattr(self, "production_task_production_id", None)
        return str(editor.text() if editor is not None else "").strip()

    def _scheduling_capabilities(self: Any, text: str) -> frozenset[ProductionCapability]:
        values = [part.strip().lower() for part in text.split(",") if part.strip()]
        if not values:
            raise ValueError("At least one ProductionCapability is required")
        try:
            return frozenset(ProductionCapability(value) for value in values)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in ProductionCapability)
            raise ValueError(f"Unknown ProductionCapability. Allowed values: {allowed}") from exc

    def _scheduling_register_resource(self: Any) -> None:
        try:
            self.production_scheduling.register_resource(
                ProductionResource(
                    resource_id=self.scheduling_resource_id.text(),
                    capabilities=self._scheduling_capabilities(
                        self.scheduling_resource_capabilities.text()
                    ),
                    state=self.scheduling_resource_state.currentData(),
                )
            )
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Production Scheduling", exc)
            return
        self._refresh_production_scheduling()

    def _scheduling_register_worker(self: Any) -> None:
        try:
            self.production_scheduling.register_worker(
                ProductionWorker(
                    worker_id=self.scheduling_worker_id.text(),
                    resource_id=self.scheduling_worker_resource_id.text(),
                    capabilities=self._scheduling_capabilities(
                        self.scheduling_worker_capabilities.text()
                    ),
                    state=self.scheduling_worker_state.currentData(),
                )
            )
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Production Scheduling", exc)
            return
        self._refresh_production_scheduling()

    def _scheduling_refresh_readiness(self: Any) -> None:
        production_id = self._scheduling_production_id()
        try:
            result = self.production_scheduling.refresh_readiness(production_id)
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Production Scheduling", exc)
            return
        self.production_scheduling_status.setText(
            f"Readiness refreshed for {production_id}: {len(result.transitions)} transition(s)."
        )
        self._refresh_production_scheduling()

    def _scheduling_create_revision(self: Any) -> None:
        try:
            snapshot = self.production_scheduling.create_schedule_revision(
                self._scheduling_production_id()
            )
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Production Scheduling", exc)
            return
        self.production_scheduling_status.setText(
            f"Created schedule revision {snapshot.revision}. Human review is required."
        )
        self._refresh_production_scheduling()

    def _scheduling_review(self: Any, decision: ProductionScheduleReviewDecision) -> None:
        try:
            self.production_scheduling.review_current(
                self._scheduling_production_id(),
                decision=decision,
                reviewed_by=self.scheduling_reviewer.text(),
                notes=self.scheduling_review_notes.toPlainText(),
            )
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Production Scheduling Review", exc)
            return
        self._refresh_production_scheduling()

    def _scheduling_approve(self: Any) -> None:
        self._scheduling_review(ProductionScheduleReviewDecision.APPROVED)

    def _scheduling_reject(self: Any) -> None:
        self._scheduling_review(ProductionScheduleReviewDecision.REJECTED)

    def _scheduling_compile_queue(self: Any) -> None:
        try:
            queue = self.production_scheduling.compile_queue(self._scheduling_production_id())
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Production Queue", exc)
            return
        self.production_scheduling_status.setText(
            f"Compiled {len(queue.entries)} queue entry(s). External execution has not started."
        )
        self._refresh_production_scheduling()

    def _scheduling_recover(self: Any) -> None:
        try:
            result = self.production_scheduling.recover(self._scheduling_production_id())
        except (ValueError, RuntimeError) as exc:
            _warning(self, "Scheduling Recovery", exc)
            return
        self.production_scheduling_status.setText(
            f"Recovery completed: {len(result.decisions)} decision(s)."
        )
        self._refresh_production_scheduling()

    def _refresh_production_scheduling(self: Any, *_args: Any) -> None:
        if not hasattr(self, "scheduling_resource_table"):
            return
        _render_resources(self)
        _render_workers(self)
        _render_schedule(self)
        _render_queue(self)
        production_id = self._scheduling_production_id()
        enabled = bool(production_id and self.projects.is_project_open)
        self.scheduling_refresh_readiness_button.setEnabled(enabled)
        self.scheduling_create_revision_button.setEnabled(enabled)

    def scheduling_compile_tasks(self: Any) -> None:
        original_compile_tasks(self)
        shot_id = str(self._selected_shot_id or "").strip().upper()
        tasks = self._compiled_production_tasks.get(shot_id, ())
        if tasks:
            try:
                self.production_scheduling.register_compiled_tasks(tasks)
            except (ValueError, RuntimeError) as exc:
                _warning(self, "ProductionTask Persistence", exc)
        self._refresh_production_scheduling()

    def scheduling_refresh(self: Any) -> None:
        original_refresh(self)
        self._refresh_production_scheduling()

    def scheduling_selection(self: Any) -> None:
        original_selection(self)
        self._refresh_production_scheduling()

    workspace_type.__init__ = scheduling_init
    workspace_type._build_production_scheduling_tab = _build_production_scheduling_tab
    workspace_type._scheduling_production_id = _scheduling_production_id
    workspace_type._scheduling_capabilities = _scheduling_capabilities
    workspace_type._scheduling_register_resource = _scheduling_register_resource
    workspace_type._scheduling_register_worker = _scheduling_register_worker
    workspace_type._scheduling_refresh_readiness = _scheduling_refresh_readiness
    workspace_type._scheduling_create_revision = _scheduling_create_revision
    workspace_type._scheduling_review = _scheduling_review
    workspace_type._scheduling_approve = _scheduling_approve
    workspace_type._scheduling_reject = _scheduling_reject
    workspace_type._scheduling_compile_queue = _scheduling_compile_queue
    workspace_type._scheduling_recover = _scheduling_recover
    workspace_type._refresh_production_scheduling = _refresh_production_scheduling
    workspace_type._compile_production_tasks = scheduling_compile_tasks
    workspace_type.refresh = scheduling_refresh
    workspace_type._selection_changed = scheduling_selection
    workspace_type._production_scheduling_workspace_installed = True


def _table(parent: QWidget, name: str, headers: tuple[str, ...]) -> QTableWidget:
    table = QTableWidget(0, len(headers), parent)
    table.setObjectName(name)
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def _warning(parent: QWidget, title: str, exc: Exception) -> None:
    QMessageBox.warning(parent, title, str(exc))


def _render_resources(workspace: Any) -> None:
    values = workspace.production_scheduling.resources()
    workspace.scheduling_resource_table.setRowCount(len(values))
    for row, resource in enumerate(values):
        _set_row(
            workspace.scheduling_resource_table,
            row,
            (
                resource.resource_id,
                resource.state.value,
                ", ".join(sorted(item.value for item in resource.capabilities)),
            ),
        )


def _render_workers(workspace: Any) -> None:
    values = workspace.production_scheduling.workers()
    workspace.scheduling_worker_table.setRowCount(len(values))
    for row, worker in enumerate(values):
        _set_row(
            workspace.scheduling_worker_table,
            row,
            (
                worker.worker_id,
                worker.resource_id,
                worker.state.value,
                ", ".join(sorted(item.value for item in worker.capabilities)),
            ),
        )


def _render_schedule(workspace: Any) -> None:
    production_id = workspace._scheduling_production_id()
    if not production_id or not workspace.projects.is_project_open:
        _no_schedule(workspace, "Open a project with persisted ProductionTasks first.")
        return
    snapshot = workspace.production_scheduling.latest_schedule(production_id)
    view = workspace.production_scheduling.review_view(production_id)
    if snapshot is None or view is None:
        _no_schedule(workspace, "No schedule revision exists.")
        return

    rows: list[tuple[str, ...]] = []
    for assignment in snapshot.schedule.assignments:
        rows.append(
            (
                "Assigned",
                assignment.task_id,
                assignment.resource_id,
                assignment.priority.name,
                ", ".join(item.value for item in assignment.required_capabilities),
            )
        )
    for deferral in snapshot.schedule.deferrals:
        candidates = ", ".join(deferral.resource_ids)
        detail = deferral.reason.value + (f" [{candidates}]" if candidates else "")
        rows.append(("Deferred", deferral.task_id, detail, "", ""))
    workspace.scheduling_schedule_table.setRowCount(len(rows))
    for row, values in enumerate(rows):
        _set_row(workspace.scheduling_schedule_table, row, values)

    workspace.scheduling_review_status.setText(
        f"Schedule {snapshot.schedule_id} revision {snapshot.revision} — {view.state.value}. "
        f"Fingerprint: {snapshot.fingerprint[:16]}…"
    )
    workspace.scheduling_approve_button.setEnabled(view.can_review)
    workspace.scheduling_reject_button.setEnabled(view.can_review)
    workspace.scheduling_compile_queue_button.setEnabled(
        view.state is ProductionScheduleReviewState.APPROVED
    )
    if view.review is not None:
        workspace.scheduling_reviewer.setText(view.review.reviewed_by)
        workspace.scheduling_review_notes.setPlainText(view.review.notes)


def _no_schedule(workspace: Any, text: str) -> None:
    workspace.scheduling_schedule_table.setRowCount(0)
    workspace.scheduling_review_status.setText(text)
    workspace.scheduling_approve_button.setEnabled(False)
    workspace.scheduling_reject_button.setEnabled(False)
    workspace.scheduling_compile_queue_button.setEnabled(False)


def _render_queue(workspace: Any) -> None:
    production_id = workspace._scheduling_production_id()
    if not production_id or not workspace.projects.is_project_open:
        workspace.scheduling_queue_table.setRowCount(0)
        workspace.scheduling_monitoring_summary.clear()
        workspace.scheduling_recover_button.setEnabled(False)
        return
    queue = workspace.production_scheduling.queue(production_id)
    if queue is None:
        workspace.scheduling_queue_table.setRowCount(0)
        workspace.scheduling_monitoring_summary.setPlainText(
            "No in-session ProductionQueue exists. Approve and compile the current schedule first."
        )
        workspace.scheduling_recover_button.setEnabled(False)
        return

    workspace.scheduling_queue_table.setRowCount(len(queue.entries))
    for row, entry in enumerate(queue.entries):
        _set_row(
            workspace.scheduling_queue_table,
            row,
            (
                entry.entry_id,
                entry.task_id,
                entry.task_type.value,
                entry.resource_id,
                entry.state.value,
                f"{entry.attempt_count}/{entry.maximum_attempts}",
            ),
        )
    snapshot = workspace.production_scheduling.monitoring(production_id)
    if snapshot is not None:
        progress = snapshot.progress
        lines = [
            f"Queue {snapshot.queue_id} — {progress.completed}/{progress.total} completed "
            f"({progress.completion_percentage:.1f}%)",
            f"Ready {progress.ready} | Claimed {progress.claimed} | Running {progress.running} | "
            f"Retrying {progress.retrying} | Failed {progress.failed} | Blocked {progress.blocked}",
            "Diagnostics:",
        ]
        lines.extend(
            f"- [{item.severity.value.upper()}] {item.code}: {item.message}"
            for item in snapshot.diagnostics
        )
        if not snapshot.diagnostics:
            lines.append("- No scheduling runtime diagnostics.")
        workspace.scheduling_monitoring_summary.setPlainText("\n".join(lines))
    workspace.scheduling_recover_button.setEnabled(True)


def _set_row(table: QTableWidget, row: int, values: tuple[str, ...]) -> None:
    for column, value in enumerate(values):
        table.setItem(row, column, QTableWidgetItem(value))
