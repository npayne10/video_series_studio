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


def install_production_scheduling_workspace(workspace_class: type[Any]) -> None:
    """Add provider-neutral scheduling/review/monitoring to Production Planning."""
    if getattr(workspace_class, "_production_scheduling_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_refresh = workspace_type.refresh
    original_selection = workspace_type._selection_changed
    original_compile_tasks = workspace_type._compile_production_tasks

    def scheduling_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.production_scheduling = ProductionSchedulingUiService(self.projects)
        self._build_production_scheduling_tab()
        self._refresh_production_scheduling()

    def _build_production_scheduling_tab(self: Any) -> None:
        tab = QWidget(self.compiler_tabs)
        tab.setObjectName("production_scheduling_tab")
        layout = QVBoxLayout(tab)

        summary = QGroupBox("Production Scheduling", tab)
        summary_layout = QVBoxLayout(summary)
        guidance = QLabel(
            "Schedule persisted READY ProductionTasks onto provider-neutral resources, review the "
            "result explicitly, compile an approved ProductionQueue, and inspect runtime health. "
            "This workspace does not select a provider workflow or start external execution.",
            summary,
        )
        guidance.setWordWrap(True)
        summary_layout.addWidget(guidance)
        self.production_scheduling_status = QLabel("", summary)
        self.production_scheduling_status.setObjectName("production_scheduling_status")
        self.production_scheduling_status.setWordWrap(True)
        summary_layout.addWidget(self.production_scheduling_status)
        layout.addWidget(summary)

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
        for state in ProductionResourceState:
            self.scheduling_resource_state.addItem(state.value.title(), state)
        resource_form.addRow("Resource ID", self.scheduling_resource_id)
        resource_form.addRow("Capabilities", self.scheduling_resource_capabilities)
        resource_form.addRow("State", self.scheduling_resource_state)
        resource_layout.addLayout(resource_form)
        resource_actions = QHBoxLayout()
        self.scheduling_register_resource_button = QPushButton("Register / Update Resource", resource_group)
        self.scheduling_register_resource_button.setObjectName("scheduling_register_resource_button")
        resource_actions.addWidget(self.scheduling_register_resource_button)
        resource_actions.addStretch(1)
        resource_layout.addLayout(resource_actions)
        self.scheduling_resource_table = QTableWidget(0, 3, resource_group)
        self.scheduling_resource_table.setObjectName("scheduling_resource_table")
        self.scheduling_resource_table.setHorizontalHeaderLabels(("Resource", "State", "Capabilities"))
        self.scheduling_resource_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scheduling_resource_table.horizontalHeader().setStretchLastSection(True)
        resource_layout.addWidget(self.scheduling_resource_table)
        layout.addWidget(resource_group)

        schedule_group = QGroupBox("Schedule Revision & Human Review", tab)
        schedule_layout = QVBoxLayout(schedule_group)
        schedule_actions = QHBoxLayout()
        self.scheduling_refresh_readiness_button = QPushButton("Refresh Task Readiness", schedule_group)
        self.scheduling_refresh_readiness_button.setObjectName("scheduling_refresh_readiness_button")
        self.scheduling_create_revision_button = QPushButton("Create Schedule Revision", schedule_group)
        self.scheduling_create_revision_button.setObjectName("scheduling_create_revision_button")
        schedule_actions.addWidget(self.scheduling_refresh_readiness_button)
        schedule_actions.addWidget(self.scheduling_create_revision_button)
        schedule_actions.addStretch(1)
        schedule_layout.addLayout(schedule_actions)
        self.scheduling_review_status = QLabel("No schedule revision exists.", schedule_group)
        self.scheduling_review_status.setObjectName("scheduling_review_status")
        self.scheduling_review_status.setWordWrap(True)
        schedule_layout.addWidget(self.scheduling_review_status)
        self.scheduling_schedule_table = QTableWidget(0, 5, schedule_group)
        self.scheduling_schedule_table.setObjectName("scheduling_schedule_table")
        self.scheduling_schedule_table.setHorizontalHeaderLabels(
            ("Result", "Task", "Resource / Reason", "Priority", "Capabilities")
        )
        self.scheduling_schedule_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scheduling_schedule_table.horizontalHeader().setStretchLastSection(True)
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
        self.scheduling_refresh_monitoring_button.setObjectName("scheduling_refresh_monitoring_button")
        self.scheduling_recover_button = QPushButton("Recover Expired Leases", queue_group)
        self.scheduling_recover_button.setObjectName("scheduling_recover_button")
        queue_actions.addWidget(self.scheduling_compile_queue_button)
        queue_actions.addWidget(self.scheduling_refresh_monitoring_button)
        queue_actions.addWidget(self.scheduling_recover_button)
        queue_actions.addStretch(1)
        queue_layout.addLayout(queue_actions)
        self.scheduling_queue_table = QTableWidget(0, 6, queue_group)
        self.scheduling_queue_table.setObjectName("scheduling_queue_table")
        self.scheduling_queue_table.setHorizontalHeaderLabels(
            ("Entry", "Task", "Type", "Resource", "State", "Attempts")
        )
        self.scheduling_queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scheduling_queue_table.horizontalHeader().setStretchLastSection(True)
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
        for state in ProductionWorkerState:
            self.scheduling_worker_state.addItem(state.value.title(), state)
        worker_form.addRow("Worker ID", self.scheduling_worker_id)
        worker_form.addRow("Resource ID", self.scheduling_worker_resource_id)
        worker_form.addRow("Capabilities", self.scheduling_worker_capabilities)
        worker_form.addRow("State", self.scheduling_worker_state)
        worker_layout.addLayout(worker_form)
        self.scheduling_register_worker_button = QPushButton("Register Worker", worker_group)
        self.scheduling_register_worker_button.setObjectName("scheduling_register_worker_button")
        worker_layout.addWidget(self.scheduling_register_worker_button)
        self.scheduling_worker_table = QTableWidget(0, 4, worker_group)
        self.scheduling_worker_table.setObjectName("scheduling_worker_table")
        self.scheduling_worker_table.setHorizontalHeaderLabels(
            ("Worker", "Resource", "State", "Capabilities")
        )
        self.scheduling_worker_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.scheduling_worker_table.horizontalHeader().setStretchLastSection(True)
        worker_layout.addWidget(self.scheduling_worker_table)
        layout.addWidget(worker_group)

        self.compiler_tabs.addTab(tab, "Scheduling")
        self.scheduling_register_resource_button.clicked.connect(self._scheduling_register_resource)
        self.scheduling_refresh_readiness_button.clicked.connect(self._scheduling_refresh_readiness)
        self.scheduling_create_revision_button.clicked.connect(self._scheduling_create_revision)
        self.scheduling_approve_button.clicked.connect(self._scheduling_approve)
        self.scheduling_reject_button.clicked.connect(self._scheduling_reject)
        self.scheduling_compile_queue_button.clicked.connect(self._scheduling_compile_queue)
        self.scheduling_register_worker_button.clicked.connect(self._scheduling_register_worker)
        self.scheduling_refresh_monitoring_button.clicked.connect(self._refresh_production_scheduling)
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
            resource = ProductionResource(
                resource_id=self.scheduling_resource_id.text(),
                capabilities=self._scheduling_capabilities(
                    self.scheduling_resource_capabilities.text()
                ),
                state=self.scheduling_resource_state.currentData(),
            )
            self.production_scheduling.register_resource(resource)
        except (ValueError, ProductionSchedulingUiError) as exc:
            QMessageBox.warning(self, "Production Scheduling", str(exc))
            return
        self._refresh_production_scheduling()

    def _scheduling_register_worker(self: Any) -> None:
        try:
            worker = ProductionWorker(
                worker_id=self.scheduling_worker_id.text(),
                resource_id=self.scheduling_worker_resource_id.text(),
                capabilities=self._scheduling_capabilities(
                    self.scheduling_worker_capabilities.text()
                ),
                state=self.scheduling_worker_state.currentData(),
            )
            self.production_scheduling.register_worker(worker)
        except (ValueError, ProductionSchedulingUiError) as exc:
            QMessageBox.warning(self, "Production Scheduling", str(exc))
            return
        self._refresh_production_scheduling()

    def _scheduling_refresh_readiness(self: Any) -> None:
        production_id = self._scheduling_production_id()
        try:
            result = self.production_scheduling.refresh_readiness(production_id)
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Production Scheduling", str(exc))
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
            QMessageBox.warning(self, "Production Scheduling", str(exc))
            return
        self.production_scheduling_status.setText(
            f"Created schedule revision {snapshot.revision}. Human review is required before queue compilation."
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
            QMessageBox.warning(self, "Production Scheduling Review", str(exc))
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
            QMessageBox.warning(self, "Production Queue", str(exc))
            return
        self.production_scheduling_status.setText(
            f"Compiled {len(queue.entries)} queue entry(s) from the current approved schedule. External execution has not started."
        )
        self._refresh_production_scheduling()

    def _scheduling_recover(self: Any) -> None:
        try:
            result = self.production_scheduling.recover(self._scheduling_production_id())
        except (ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Scheduling Recovery", str(exc))
            return
        self.production_scheduling_status.setText(
            f"Scheduling recovery completed: {len(result.decisions)} recovery decision(s)."
        )
        self._refresh_production_scheduling()

    def _render_scheduling_resources(self: Any) -> None:
        values = self.production_scheduling.resources()
        self.scheduling_resource_table.setRowCount(len(values))
        for row, resource in enumerate(values):
            cells = (
                resource.resource_id,
                resource.state.value,
                ", ".join(sorted(item.value for item in resource.capabilities)),
            )
            for column, value in enumerate(cells):
                self.scheduling_resource_table.setItem(row, column, QTableWidgetItem(value))

    def _render_scheduling_workers(self: Any) -> None:
        values = self.production_scheduling.workers()
        self.scheduling_worker_table.setRowCount(len(values))
        for row, worker in enumerate(values):
            cells = (
                worker.worker_id,
                worker.resource_id,
                worker.state.value,
                ", ".join(sorted(item.value for item in worker.capabilities)),
            )
            for column, value in enumerate(cells):
                self.scheduling_worker_table.setItem(row, column, QTableWidgetItem(value))

    def _render_schedule(self: Any) -> None:
        production_id = self._scheduling_production_id()
        if not production_id or not self.projects.is_project_open:
            self.scheduling_schedule_table.setRowCount(0)
            self.scheduling_review_status.setText("Open a project with persisted ProductionTasks first.")
            self.scheduling_approve_button.setEnabled(False)
            self.scheduling_reject_button.setEnabled(False)
            self.scheduling_compile_queue_button.setEnabled(False)
            return
        snapshot = self.production_scheduling.latest_schedule(production_id)
        view = self.production_scheduling.review_view(production_id)
        if snapshot is None or view is None:
            self.scheduling_schedule_table.setRowCount(0)
            self.scheduling_review_status.setText("No schedule revision exists.")
            self.scheduling_approve_button.setEnabled(False)
            self.scheduling_reject_button.setEnabled(False)
            self.scheduling_compile_queue_button.setEnabled(False)
            return
        rows: list[tuple[str, str, str, str, str]] = []
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
            resources = ", ".join(deferral.resource_ids)
            detail = deferral.reason.value + (f" [{resources}]" if resources else "")
            rows.append(("Deferred", deferral.task_id, detail, "", ""))
        self.scheduling_schedule_table.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, value in enumerate(cells):
                self.scheduling_schedule_table.setItem(row, column, QTableWidgetItem(value))
        self.scheduling_review_status.setText(
            f"Schedule {snapshot.schedule_id} revision {snapshot.revision} — {view.state.value}. "
            f"Fingerprint: {snapshot.fingerprint[:16]}…"
        )
        can_review = view.can_review
        self.scheduling_approve_button.setEnabled(can_review)
        self.scheduling_reject_button.setEnabled(can_review)
        self.scheduling_compile_queue_button.setEnabled(
            view.state is ProductionScheduleReviewState.APPROVED
        )
        if view.review is not None:
            self.scheduling_reviewer.setText(view.review.reviewed_by)
            self.scheduling_review_notes.setPlainText(view.review.notes)

    def _render_queue_monitoring(self: Any) -> None:
        production_id = self._scheduling_production_id()
        if not production_id or not self.projects.is_project_open:
            self.scheduling_queue_table.setRowCount(0)
            self.scheduling_monitoring_summary.clear()
            self.scheduling_recover_button.setEnabled(False)
            return
        queue = self.production_scheduling.queue(production_id)
        if queue is None:
            self.scheduling_queue_table.setRowCount(0)
            self.scheduling_monitoring_summary.setPlainText(
                "No in-session ProductionQueue exists. Approve the current schedule and compile the queue first."
            )
            self.scheduling_recover_button.setEnabled(False)
            return
        self.scheduling_queue_table.setRowCount(len(queue.entries))
        for row, entry in enumerate(queue.entries):
            cells = (
                entry.entry_id,
                entry.task_id,
                entry.task_type.value,
                entry.resource_id,
                entry.state.value,
                f"{entry.attempt_count}/{entry.maximum_attempts}",
            )
            for column, value in enumerate(cells):
                self.scheduling_queue_table.setItem(row, column, QTableWidgetItem(value))
        snapshot = self.production_scheduling.monitoring(production_id)
        if snapshot is None:
            self.scheduling_monitoring_summary.clear()
        else:
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
            self.scheduling_monitoring_summary.setPlainText("\n".join(lines))
        self.scheduling_recover_button.setEnabled(True)

    def _refresh_production_scheduling(self: Any, *_args: Any) -> None:
        if not hasattr(self, "scheduling_resource_table"):
            return
        self._render_scheduling_resources()
        self._render_scheduling_workers()
        self._render_schedule()
        self._render_queue_monitoring()
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
            except RuntimeError as exc:
                QMessageBox.warning(self, "ProductionTask Persistence", str(exc))
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
    workspace_type._render_scheduling_resources = _render_scheduling_resources
    workspace_type._render_scheduling_workers = _render_scheduling_workers
    workspace_type._render_schedule = _render_schedule
    workspace_type._render_queue_monitoring = _render_queue_monitoring
    workspace_type._refresh_production_scheduling = _refresh_production_scheduling
    workspace_type._compile_production_tasks = scheduling_compile_tasks
    workspace_type.refresh = scheduling_refresh
    workspace_type._selection_changed = scheduling_selection
    workspace_type._production_scheduling_workspace_installed = True
