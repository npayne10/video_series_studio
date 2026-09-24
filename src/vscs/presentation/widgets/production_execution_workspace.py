"""Operator workspace for scheduled live production execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.production_execution import (
    GovernedRetryOverrideStatus,
    ProductionDeviceTelemetry,
    ProductionExecutionCandidate,
    ProductionExecutionResult,
    ProductionExecutionUiService,
    ProductionPackageStatus,
    ProductionTelemetrySnapshot,
    ShotBoundaryAuthorityStatus,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
)


class TimedSpanQcDialog(QDialog):
    """Collect explicit human visual QC for one internal introduction boundary."""

    def __init__(self, requirement_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Timed Span Visual QC")
        self.requirement_id = requirement_id

        layout = QVBoxLayout(self)
        guidance = QLabel(
            "Confirm each visual criterion against the assembled Shot. Acceptance is "
            "recorded only when every criterion is explicitly checked."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        form = QFormLayout()
        self.actor = QLineEdit()
        self.actor.setPlaceholderText("Human reviewer")
        form.addRow("Reviewed by", self.actor)

        self.absent_before = QCheckBox("Introduced asset is absent before the governed boundary")
        self.present_from = QCheckBox("Introduced asset is present from the target frame")
        self.continuity = QCheckBox("Source visual continuity is preserved across the boundary")
        self.no_unapproved = QCheckBox("No unapproved asset appears at the transition")
        form.addRow(self.absent_before)
        form.addRow(self.present_from)
        form.addRow(self.continuity)
        form.addRow(self.no_unapproved)

        self.notes = QTextEdit()
        self.notes.setMaximumHeight(90)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> tuple[bool, bool, bool, bool, str, str]:
        return (
            self.absent_before.isChecked(),
            self.present_from.isChecked(),
            self.continuity.isChecked(),
            self.no_unapproved.isChecked(),
            self.actor.text().strip(),
            self.notes.toPlainText().strip(),
        )


class ProductionExecutionWorkspace(QWidget):
    """Compile, start and monitor approved scheduled production through VSCS authority."""

    POLL_INTERVAL_MS = 2000

    def __init__(
        self,
        service_provider: Callable[[], ProductionExecutionUiService | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_provider = service_provider
        self._candidates: dict[str, ProductionExecutionCandidate] = {}
        self._selected_task_id: str | None = None
        self._execution_active = False
        self._package_status: ProductionPackageStatus | None = None
        self._retry_status: GovernedRetryOverrideStatus | None = None
        self._boundary_status: ShotBoundaryAuthorityStatus | None = None
        self._timed_span_status: TimedSpanAcceptanceStatus | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_live_status)

        guidance = QLabel(
            "Production Planning ends when an approved schedule is ready. This workspace "
            "compiles the governed Production Package from the selected task's approved "
            "production authority, validates its ComfyUI input contract, and starts the "
            "scheduled task through VSCS queue/lease/provider authority. Preview, Production "
            "and Master each have independent execution-attempt authority. Provider outputs "
            "are copied into the project media output folder and ingested as Generated Media."
        )
        guidance.setWordWrap(True)

        package_row = QHBoxLayout()
        self.profile = QComboBox()
        self.profile.addItems(("production", "preview", "master"))
        self.profile.currentTextChanged.connect(self._profile_changed)
        self.package_state = QLabel("Select a scheduled task.")
        self.package_state.setWordWrap(True)
        self.compile_package_button = QPushButton("Compile Production Package")
        self.compile_package_button.setEnabled(False)
        self.compile_package_button.clicked.connect(self._compile_package)
        package_row.addWidget(QLabel("Profile"))
        package_row.addWidget(self.profile)
        package_row.addWidget(QLabel("Production Package"))
        package_row.addWidget(self.package_state, 1)
        package_row.addWidget(self.compile_package_button)

        boundary_row = QHBoxLayout()
        self.opening_boundary_state = QLabel("Opening Boundary: -")
        self.opening_boundary_state.setWordWrap(True)
        self.closing_boundary_state = QLabel("Closing Boundary: -")
        self.closing_boundary_state.setWordWrap(True)
        self.publish_boundary_button = QPushButton("Publish Closing Boundary")
        self.publish_boundary_button.setEnabled(False)
        self.publish_boundary_button.clicked.connect(self._publish_closing_boundary)
        boundary_row.addWidget(self.opening_boundary_state, 1)
        boundary_row.addWidget(self.closing_boundary_state, 1)
        boundary_row.addWidget(self.publish_boundary_button)

        self.timed_span_group = QGroupBox("Timed Asset / Span Functional Acceptance")
        timed_span_layout = QGridLayout(self.timed_span_group)
        self.timed_span_state = QLabel("Timed Span Acceptance: -")
        self.timed_span_state.setWordWrap(True)
        self.timed_span_detail = QLabel(
            "Compile a dynamic Shot to inspect internal spans and Introduction Keyframes."
        )
        self.timed_span_detail.setWordWrap(True)
        self.build_span_packages_button = QPushButton("Build Span Packages")
        self.approve_introduction_keyframe_button = QPushButton("Approve Introduction Keyframe")
        self.assemble_span_outputs_button = QPushButton("Verify & Assemble Span Outputs")
        self.record_span_qc_button = QPushButton("Record Visual QC")
        for button in (
            self.build_span_packages_button,
            self.approve_introduction_keyframe_button,
            self.assemble_span_outputs_button,
            self.record_span_qc_button,
        ):
            button.setEnabled(False)
        self.build_span_packages_button.clicked.connect(self._build_span_packages)
        self.approve_introduction_keyframe_button.clicked.connect(
            self._approve_introduction_keyframe
        )
        self.assemble_span_outputs_button.clicked.connect(self._assemble_span_outputs)
        self.record_span_qc_button.clicked.connect(self._record_span_qc)
        timed_span_layout.addWidget(self.timed_span_state, 0, 0, 1, 3)
        timed_span_layout.addWidget(self.timed_span_detail, 1, 0, 1, 3)
        timed_span_layout.addWidget(self.build_span_packages_button, 2, 0)
        timed_span_layout.addWidget(self.approve_introduction_keyframe_button, 2, 1)
        timed_span_layout.addWidget(self.assemble_span_outputs_button, 3, 0)
        timed_span_layout.addWidget(self.record_span_qc_button, 3, 1)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ("Production", "Episode", "Scene", "Shot", "Task", "Resource", "State")
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._selection_changed)

        self.refresh_button = QPushButton("Refresh Scheduled Work")
        self.start_button = QPushButton("Start Production")
        self.status_button = QPushButton("Refresh Execution Status")
        self.retry_button = QPushButton("Authorize Additional Retry")
        self.retry_state = QLabel("Retry Override: -")
        self.retry_state.setWordWrap(True)
        self.start_button.setEnabled(False)
        self.status_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh)
        self.start_button.clicked.connect(self._start)
        self.status_button.clicked.connect(self._reconcile)
        self.retry_button.clicked.connect(self._authorize_retry)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.status_button)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.retry_state, 1)

        self.monitor_group = QGroupBox("Live Production Monitor")
        monitor = QGridLayout(self.monitor_group)
        self.monitor_state = QLabel("No execution selected.")
        self.monitor_state.setWordWrap(True)
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("No active execution")
        self.step_progress = QProgressBar()
        self.step_progress.setRange(0, 100)
        self.step_progress.setValue(0)
        self.step_progress.setFormat("Detailed step progress unavailable")
        self.monitor_stage = QLabel("-")
        self.monitor_queue = QLabel("-")
        self.monitor_elapsed = QLabel("-")
        self.monitor_eta = QLabel("-")
        self.monitor_provider = QLabel("-")
        self.monitor_prompt = QLabel("-")
        self.monitor_health = QLabel("-")
        self.monitor_device = QLabel("-")
        self.monitor_note = QLabel("")
        self.monitor_note.setWordWrap(True)
        monitor.addWidget(self.monitor_state, 0, 0, 1, 4)
        monitor.addWidget(QLabel("Overall progress"), 1, 0)
        monitor.addWidget(self.overall_progress, 1, 1, 1, 3)
        monitor.addWidget(QLabel("Current operation"), 2, 0)
        monitor.addWidget(self.monitor_stage, 2, 1)
        monitor.addWidget(QLabel("Queue"), 2, 2)
        monitor.addWidget(self.monitor_queue, 2, 3)
        monitor.addWidget(QLabel("Current step"), 3, 0)
        monitor.addWidget(self.step_progress, 3, 1, 1, 3)
        monitor.addWidget(QLabel("Elapsed"), 4, 0)
        monitor.addWidget(self.monitor_elapsed, 4, 1)
        monitor.addWidget(QLabel("Estimated remaining"), 4, 2)
        monitor.addWidget(self.monitor_eta, 4, 3)
        monitor.addWidget(QLabel("Provider"), 5, 0)
        monitor.addWidget(self.monitor_provider, 5, 1)
        monitor.addWidget(QLabel("ComfyUI Prompt"), 5, 2)
        monitor.addWidget(self.monitor_prompt, 5, 3)
        monitor.addWidget(QLabel("ComfyUI Health"), 6, 0)
        monitor.addWidget(self.monitor_health, 6, 1)
        monitor.addWidget(QLabel("Device / VRAM"), 6, 2)
        monitor.addWidget(self.monitor_device, 6, 3)
        monitor.addWidget(self.monitor_note, 7, 0, 1, 4)

        self.summary = QLabel("Open a project to inspect scheduled production work.")
        self.summary.setWordWrap(True)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(170)

        layout = QVBoxLayout(self)
        layout.addWidget(guidance)
        layout.addLayout(package_row)
        layout.addLayout(boundary_row)
        layout.addWidget(self.timed_span_group)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.monitor_group)
        layout.addWidget(self.summary)
        layout.addWidget(self.details)

    def refresh(self) -> None:
        self._poll_timer.stop()
        service = self._service_provider()
        self._candidates.clear()
        self._selected_task_id = None
        self._execution_active = False
        self._package_status = None
        self._retry_status = None
        self._boundary_status = None
        self._timed_span_status = None
        self.table.setRowCount(0)
        self.start_button.setEnabled(False)
        self.status_button.setEnabled(False)
        self.retry_button.setEnabled(False)
        self.retry_state.setText("Retry Override: -")
        self.opening_boundary_state.setText("Opening Boundary: -")
        self.closing_boundary_state.setText("Closing Boundary: -")
        self.publish_boundary_button.setEnabled(False)
        self._reset_timed_span_status()
        self.compile_package_button.setEnabled(False)
        self.package_state.setText("Select a scheduled task.")
        self.details.clear()
        self._reset_monitor()
        if service is None:
            self.summary.setText("Open a project to inspect scheduled production work.")
            return
        try:
            candidates = service.candidates()
        except Exception as exc:
            QMessageBox.warning(self, "Production Execution", str(exc))
            self.summary.setText("Unable to read executable scheduled work.")
            return
        for candidate in candidates:
            self._candidates[candidate.task_id] = candidate
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                candidate.production_id,
                candidate.episode_id,
                candidate.scene_id or "-",
                candidate.shot_id or "-",
                candidate.label,
                candidate.resource_id,
                candidate.task_state.value,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 4:
                    item.setData(Qt.ItemDataRole.UserRole, candidate.task_id)
                    item.setToolTip(candidate.task_id)
                self.table.setItem(row, column, item)
        if candidates:
            self.summary.setText(
                f"{len(candidates)} approved scheduled task(s) ready for Production Execution."
            )
        else:
            self.summary.setText(
                "No executable scheduled tasks are available. In Production Planning, ensure "
                "the ProductionTask is READY, a schedule revision exists, and the schedule is approved."
            )

    def _selection_changed(self) -> None:
        self._poll_timer.stop()
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._selected_task_id = None
            self._execution_active = False
            self._package_status = None
            self._retry_status = None
            self._boundary_status = None
            self._timed_span_status = None
            self.compile_package_button.setEnabled(False)
            self.retry_button.setEnabled(False)
            self.retry_state.setText("Retry Override: -")
            self.opening_boundary_state.setText("Opening Boundary: -")
            self.closing_boundary_state.setText("Closing Boundary: -")
            self.publish_boundary_button.setEnabled(False)
            self._reset_timed_span_status()
            self.package_state.setText("Select a scheduled task.")
            self._update_start_enabled()
            self.status_button.setEnabled(False)
            self._reset_monitor()
            return
        task_item = self.table.item(rows[0].row(), 4)
        if task_item is None:
            return
        raw = task_item.data(Qt.ItemDataRole.UserRole)
        task_id = str(raw or "").strip()
        if not task_id:
            return
        self._selected_task_id = task_id
        self._execution_active = False
        self.compile_package_button.setEnabled(True)
        self._refresh_package_status()
        self._refresh_execution_availability()
        self._refresh_retry_override_status()
        self._refresh_boundary_status()
        self._refresh_timed_span_status()
        candidate = self._candidates[task_id]
        self._render_candidate(candidate)

    def _profile_changed(self, _profile: str) -> None:
        if self._selected_task_id is None:
            return
        self._poll_timer.stop()
        self._execution_active = False
        self._refresh_package_status()
        self._refresh_execution_availability()
        self._refresh_retry_override_status()
        self._refresh_boundary_status()
        self._refresh_timed_span_status()
        candidate = self._candidates.get(self._selected_task_id)
        if candidate is not None:
            self._render_candidate(candidate)

    def _refresh_execution_availability(self) -> None:
        if self._selected_task_id is None:
            self.status_button.setEnabled(False)
            self._reset_monitor()
            return
        service = self._service_provider()
        if service is None:
            self.status_button.setEnabled(False)
            self._reset_monitor()
            return
        try:
            available = service.has_execution(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception:
            available = False
        self.status_button.setEnabled(available)
        if available:
            self._refresh_telemetry()
        else:
            self._reset_monitor()

    def _refresh_retry_override_status(self) -> None:
        if self._selected_task_id is None:
            self._retry_status = None
            self.retry_button.setEnabled(False)
            self.retry_state.setText("Retry Override: -")
            return
        service = self._service_provider()
        if service is None:
            return
        profile = self.profile.currentText()
        try:
            status = service.retry_override_status(
                self._selected_task_id,
                profile=profile,
            )
        except Exception as exc:
            self._retry_status = None
            self.retry_button.setEnabled(False)
            self.retry_state.setText(f"{profile.title()} Retry: unavailable — {exc}")
            return
        self._retry_status = status
        self.retry_button.setEnabled(status.eligible)
        self.retry_state.setText(
            f"{profile.title()} Retry: {status.state.value.upper()} — profile attempts "
            f"{status.attempts_recorded}/{status.effective_maximum_attempts}. {status.message}"
        )

    def _refresh_boundary_status(self) -> None:
        if self._selected_task_id is None:
            self._boundary_status = None
            self.opening_boundary_state.setText("Opening Boundary: -")
            self.closing_boundary_state.setText("Closing Boundary: -")
            self.publish_boundary_button.setEnabled(False)
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            status = service.shot_boundary_status(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self._boundary_status = None
            self.opening_boundary_state.setText(f"Opening Boundary: unavailable — {exc}")
            self.closing_boundary_state.setText("Closing Boundary: unavailable")
            self.publish_boundary_button.setEnabled(False)
            return
        self._boundary_status = status
        source = (
            f" from {status.opening_source_shot_id} / {status.opening_boundary_id}"
            if status.opening_source_shot_id
            else ""
        )
        self.opening_boundary_state.setText(
            f"Opening Boundary: {status.opening_mode.value.upper()} — "
            f"{status.opening_state.upper()}{source}"
        )
        if status.closing_state == "published":
            frame = (
                f" frame {status.closing_frame_index}/{status.closing_frame_count}"
                if status.closing_frame_index is not None and status.closing_frame_count is not None
                else ""
            )
            self.closing_boundary_state.setText(
                f"Closing Boundary: PUBLISHED — {status.closing_boundary_id or '-'}{frame}"
            )
        else:
            suffix = f" — {status.message}" if status.message else ""
            self.closing_boundary_state.setText(
                f"Closing Boundary: {status.closing_state.upper()}{suffix}"
            )
        self.publish_boundary_button.setEnabled(status.closing_state != "published")

    def _publish_closing_boundary(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        published_by, accepted = QInputDialog.getText(
            self,
            "Publish Closing Shot Boundary",
            "Published by (human operator):",
        )
        if not accepted:
            return
        actor = published_by.strip()
        if not actor:
            QMessageBox.warning(
                self,
                "Publish Closing Shot Boundary",
                "Publishing identity is required.",
            )
            return
        try:
            boundary = service.publish_closing_boundary(
                self._selected_task_id,
                published_by=actor,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Publish Closing Shot Boundary", str(exc))
            self._refresh_boundary_status()
            return
        self.summary.setText(
            f"Published {boundary.boundary_id} from exact governed frame "
            f"{boundary.frame_index}/{boundary.frame_count}."
        )
        self._refresh_boundary_status()
        self._refresh_package_status()
        self._refresh_timed_span_status()

    def _authorize_retry(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        profile = self.profile.currentText()
        authorized_by, accepted = QInputDialog.getText(
            self,
            f"Authorize Additional {profile.title()} Retry",
            "Authorized by (human operator):",
        )
        if not accepted:
            return
        actor = authorized_by.strip()
        if not actor:
            QMessageBox.warning(
                self,
                "Authorize Additional Retry",
                "Authorizing identity is required.",
            )
            return
        reason, accepted = QInputDialog.getMultiLineText(
            self,
            f"Authorize Additional {profile.title()} Retry",
            f"Reason for exceeding the configured {profile} retry limit:",
        )
        if not accepted:
            return
        justification = reason.strip()
        if not justification:
            QMessageBox.warning(self, "Authorize Additional Retry", "A retry reason is required.")
            return
        try:
            status = service.authorize_retry(
                self._selected_task_id,
                authorized_by=actor,
                reason=justification,
                profile=profile,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Authorize Additional Retry", str(exc))
            self._refresh_retry_override_status()
            return
        self._retry_status = status
        self.summary.setText(status.message)
        self._refresh_retry_override_status()
        self._refresh_execution_availability()
        self._refresh_package_status()

    def _refresh_timed_span_status(self) -> None:
        if self._selected_task_id is None:
            self._timed_span_status = None
            self._reset_timed_span_status()
            self._update_start_enabled()
            return
        service = self._service_provider()
        if service is None:
            self._timed_span_status = None
            self._reset_timed_span_status()
            self._update_start_enabled()
            return
        try:
            status = service.timed_span_acceptance_status(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self._timed_span_status = None
            self.timed_span_state.setText(f"Timed Span Acceptance: unavailable — {exc}")
            self.timed_span_detail.setText(
                "This backend does not expose Phase 20.18.2.3.5 timed-span acceptance."
            )
            self.build_span_packages_button.setEnabled(False)
            self.approve_introduction_keyframe_button.setEnabled(False)
            self.assemble_span_outputs_button.setEnabled(False)
            self.record_span_qc_button.setEnabled(False)
            self._update_start_enabled()
            return
        self._timed_span_status = status
        self._render_timed_span_status(status)
        self._update_start_enabled()

    def _render_timed_span_status(self, status: TimedSpanAcceptanceStatus) -> None:
        self.timed_span_state.setText(
            f"Timed Span Acceptance: {status.state.value.upper()} — {status.message}"
        )
        final_frames = (
            str(status.final_frame_count) if status.final_frame_count is not None else "-"
        )
        boundaries = (
            " • ".join(status.boundary_summaries)
            if status.boundary_summaries
            else "no internal introduction boundary"
        )
        final_path = status.final_path or "-"
        self.timed_span_detail.setText(
            f"Spans {status.span_count} • Boundaries {status.boundary_count} • "
            f"Introduction Keyframes {status.approved_keyframe_count}/{status.requirement_count} • "
            f"Visual QC {status.qc_passed_count}/{status.requirement_count} • "
            f"Assembly {'verified' if status.assembly_present else 'pending'} • "
            f"Final frames {final_frames}\n"
            f"Transitions: {boundaries}\n"
            f"Assembled Shot: {final_path}"
        )
        self.build_span_packages_button.setEnabled(
            status.applicable
            and status.state is not TimedSpanAcceptanceState.PACKAGE_REQUIRED
            and not status.pending_keyframe_requirement_ids
        )
        self.approve_introduction_keyframe_button.setEnabled(
            bool(status.pending_keyframe_requirement_ids)
        )
        self.assemble_span_outputs_button.setEnabled(
            status.applicable
            and status.state is not TimedSpanAcceptanceState.PACKAGE_REQUIRED
            and not status.pending_keyframe_requirement_ids
        )
        self.record_span_qc_button.setEnabled(
            status.assembly_present and bool(status.pending_qc_requirement_ids)
        )

    def _reset_timed_span_status(self) -> None:
        self.timed_span_state.setText("Timed Span Acceptance: -")
        self.timed_span_detail.setText(
            "Compile a dynamic Shot to inspect internal spans and Introduction Keyframes."
        )
        self.build_span_packages_button.setEnabled(False)
        self.approve_introduction_keyframe_button.setEnabled(False)
        self.assemble_span_outputs_button.setEnabled(False)
        self.record_span_qc_button.setEnabled(False)

    def _select_timed_requirement(
        self,
        requirement_ids: tuple[str, ...],
        title: str,
    ) -> str | None:
        if not requirement_ids:
            return None
        if len(requirement_ids) == 1:
            return requirement_ids[0]
        selected, accepted = QInputDialog.getItem(
            self,
            title,
            "Governed requirement:",
            list(requirement_ids),
            0,
            False,
        )
        if not accepted:
            return None
        value = selected.strip()
        return value or None

    def _build_span_packages(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            paths = service.build_timed_span_packages(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Build Span Packages", str(exc))
            self._refresh_timed_span_status()
            return
        self.summary.setText(
            "Built governed timed-span Candidate C packages: "
            + ", ".join(str(path) for path in paths)
        )
        self._refresh_timed_span_status()

    def _approve_introduction_keyframe(self) -> None:
        if self._selected_task_id is None or self._timed_span_status is None:
            return
        requirement_id = self._select_timed_requirement(
            self._timed_span_status.pending_keyframe_requirement_ids,
            "Approve Introduction Keyframe",
        )
        if requirement_id is None:
            return
        image_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select approved Introduction Keyframe",
            "",
            "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if not image_path:
            return
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select exact preceding internal-boundary frame",
            "",
            "Images (*.png *.jpg *.jpeg *.webp);;All Files (*)",
        )
        if not source_path:
            return
        approved_by, accepted = QInputDialog.getText(
            self,
            "Approve Introduction Keyframe",
            "Approved by (human operator):",
        )
        if not accepted:
            return
        actor = approved_by.strip()
        if not actor:
            QMessageBox.warning(
                self,
                "Approve Introduction Keyframe",
                "Human approval identity is required.",
            )
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            status = service.approve_introduction_keyframe(
                self._selected_task_id,
                requirement_id=requirement_id,
                image_path=Path(image_path),
                source_boundary_image_path=Path(source_path),
                approved_by=actor,
                approved_at=datetime.now(UTC).isoformat(),
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Approve Introduction Keyframe", str(exc))
            self._refresh_timed_span_status()
            return
        self._timed_span_status = status
        self._render_timed_span_status(status)
        self.summary.setText(f"Governed Introduction Keyframe approved for {requirement_id}.")

    def _assemble_span_outputs(self) -> None:
        if self._selected_task_id is None or self._timed_span_status is None:
            return
        expected = self._timed_span_status.span_count
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            f"Select {expected} normalized span outputs in governed sequence",
            "",
            "Video (*.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )
        if not paths:
            return
        if len(paths) != expected:
            QMessageBox.warning(
                self,
                "Verify & Assemble Span Outputs",
                f"Select exactly {expected} span output files in governed sequence.",
            )
            return
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save assembled governed Shot inside the VSCS project",
            "",
            "MP4 Video (*.mp4)",
        )
        if not output_path:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            status = service.assemble_timed_span_outputs(
                self._selected_task_id,
                span_paths=tuple(Path(path) for path in paths),
                output_path=Path(output_path),
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Verify & Assemble Span Outputs", str(exc))
            self._refresh_timed_span_status()
            return
        self._timed_span_status = status
        self._render_timed_span_status(status)
        self.summary.setText(f"Verified and assembled {expected} governed span outputs.")

    def _record_span_qc(self) -> None:
        if self._selected_task_id is None or self._timed_span_status is None:
            return
        requirement_id = self._select_timed_requirement(
            self._timed_span_status.pending_qc_requirement_ids,
            "Record Timed Span Visual QC",
        )
        if requirement_id is None:
            return
        dialog = TimedSpanQcDialog(requirement_id, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        (
            absent_before,
            present_from,
            continuity,
            no_unapproved,
            actor,
            notes,
        ) = dialog.values()
        if not actor:
            QMessageBox.warning(
                self,
                "Record Timed Span Visual QC",
                "Human reviewer identity is required.",
            )
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            status = service.record_timed_span_qc(
                self._selected_task_id,
                requirement_id=requirement_id,
                absent_before_boundary=absent_before,
                present_from_target_frame=present_from,
                source_continuity_preserved=continuity,
                no_unapproved_assets=no_unapproved,
                approved_by=actor,
                notes=notes,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Record Timed Span Visual QC", str(exc))
            self._refresh_timed_span_status()
            return
        self._timed_span_status = status
        self._render_timed_span_status(status)
        self.summary.setText(
            f"Timed-span visual QC recorded for {requirement_id}: "
            f"{'PASSED' if status.accepted else status.state.value.upper()}."
        )

    def _refresh_telemetry(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            snapshot = service.telemetry(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self.monitor_note.setText(f"Telemetry unavailable: {exc}")
            return
        self._render_telemetry(snapshot)
        if snapshot.live and not snapshot.terminal:
            self._execution_active = True
            if not self._poll_timer.isActive():
                self._poll_timer.start()
        elif not snapshot.live:
            self._poll_timer.stop()

    def _refresh_package_status(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            status = service.package_status(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self._package_status = None
            self.package_state.setText(f"Unable to inspect package: {exc}")
            self._update_start_enabled()
            return
        self._package_status = status
        path = str(status.path) if status.path is not None else "-"
        self.package_state.setText(f"{status.state.value.upper()} — {status.message} Path: {path}")
        self._update_start_enabled()

    def _compile_package(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            status = service.compile_package(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Compile Production Package", str(exc))
            self._refresh_package_status()
            return
        self._package_status = status
        self.package_state.setText(
            f"{status.state.value.upper()} — {status.message} Path: {status.path or '-'}"
        )
        self.summary.setText(
            f"Production Package compiled for {self._candidates[self._selected_task_id].label}."
        )
        self._refresh_execution_availability()
        self._refresh_retry_override_status()
        self._refresh_boundary_status()
        self._refresh_timed_span_status()
        self._update_start_enabled()

    def _update_start_enabled(self) -> None:
        timed_span_blocks_monolithic_start = (
            self._timed_span_status is not None and self._timed_span_status.applicable
        )
        self.start_button.setEnabled(
            self._selected_task_id is not None
            and self._package_status is not None
            and self._package_status.executable
            and not self._execution_active
            and not timed_span_blocks_monolithic_start
        )

    def _start(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        self._execution_active = True
        self._update_start_enabled()
        try:
            result = service.start(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            self._execution_active = False
            self._refresh_retry_override_status()
            self._refresh_package_status()
            QMessageBox.warning(self, "Start Production", str(exc))
            return
        self._execution_active = not result.terminal
        self._render_result(result)
        self._refresh_retry_override_status()
        self._update_start_enabled()
        self.status_button.setEnabled(not result.terminal)
        self._refresh_telemetry()

    def _reconcile(self) -> None:
        self._refresh_execution(show_warning=True)

    def _poll_live_status(self) -> None:
        if not self._execution_active or self._selected_task_id is None:
            self._poll_timer.stop()
            return
        self._refresh_execution(show_warning=False)

    def _refresh_execution(self, *, show_warning: bool) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            result = service.reconcile(
                self._selected_task_id,
                profile=self.profile.currentText(),
            )
        except Exception as exc:
            if show_warning:
                QMessageBox.warning(self, "Production Execution Status", str(exc))
            else:
                self.monitor_note.setText(f"Automatic monitoring paused: {exc}")
                self._poll_timer.stop()
            return
        self._execution_active = not result.terminal
        self._render_result(result)
        self._refresh_telemetry()
        self._refresh_retry_override_status()
        self._refresh_boundary_status()
        if show_warning:
            self._refresh_package_status()
        self.status_button.setEnabled(not result.terminal)
        if result.terminal:
            self._poll_timer.stop()
            self._update_start_enabled()

    def _render_candidate(self, candidate: ProductionExecutionCandidate) -> None:
        status = self._package_status
        package_text = status.state.value if status is not None else "unknown"
        self.details.setPlainText(
            "\n".join(
                (
                    f"Task ID: {candidate.task_id}",
                    f"Type: {candidate.task_type.value}",
                    f"Production: {candidate.production_id}",
                    f"Episode: {candidate.episode_id}",
                    f"Scene: {candidate.scene_id or '-'}",
                    f"Shot: {candidate.shot_id or '-'}",
                    f"Scheduled Resource: {candidate.resource_id}",
                    f"Queue Entry: {candidate.queue_entry_id}",
                    f"Production Package: {package_text}",
                    f"Profile: {self.profile.currentText()}",
                )
            )
        )

    def _render_result(self, result: ProductionExecutionResult) -> None:
        progress = "-" if result.progress is None else f"{result.progress * 100:.1f}%"
        media = ", ".join(result.generated_media_ids) or "none yet"
        self.summary.setText(
            f"{result.candidate.label}: {result.state.value.upper()} — progress {progress}"
        )
        self.details.setPlainText(
            "\n".join(
                (
                    f"Task ID: {result.candidate.task_id}",
                    f"Profile: {self.profile.currentText()}",
                    f"Provider: {result.provider_id or '-'}",
                    f"Execution ID: {result.execution_id or '-'}",
                    f"Provider Job: {result.provider_job_id or '-'}",
                    f"State: {result.state.value}",
                    f"Progress: {progress}",
                    f"Project Media Output: {result.media_output_directory or '-'}",
                    f"Generated Media: {media}",
                    f"Message: {result.message or '-'}",
                )
            )
        )

    def _render_telemetry(self, snapshot: ProductionTelemetrySnapshot) -> None:
        mode = "LIVE" if snapshot.live else "DURABLE SUMMARY"
        self.monitor_state.setText(f"{mode} — {snapshot.state.value.upper()}")
        if snapshot.progress is None:
            self.overall_progress.setValue(0)
            self.overall_progress.setFormat("Progress unavailable")
        else:
            percent = max(0, min(100, round(snapshot.progress * 100)))
            self.overall_progress.setValue(percent)
            self.overall_progress.setFormat(f"{snapshot.state.value.upper()} — {percent}%")
        self.monitor_stage.setText(snapshot.current_node or snapshot.stage or "-")
        self.monitor_queue.setText(_queue_text(snapshot))
        self.monitor_elapsed.setText(_duration_text(snapshot.elapsed_seconds))
        self.monitor_eta.setText(_duration_text(snapshot.estimated_remaining_seconds))
        self.monitor_provider.setText(snapshot.provider_id or "-")
        self.monitor_prompt.setText(snapshot.provider_job_id or "-")
        self.monitor_health.setText(_health_text(snapshot.provider_healthy, snapshot.live))
        self.monitor_device.setText(_device_text(snapshot.devices))
        if snapshot.step_current is not None and snapshot.step_total is not None:
            percent = round(snapshot.step_current * 100 / snapshot.step_total)
            self.step_progress.setValue(percent)
            self.step_progress.setFormat(
                f"{snapshot.step_current} / {snapshot.step_total} — {percent}%"
            )
        else:
            self.step_progress.setValue(0)
            self.step_progress.setFormat("Detailed step progress unavailable")
        self.monitor_note.setText(snapshot.message)

    def _reset_monitor(self) -> None:
        self.monitor_state.setText("No execution selected.")
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("No active execution")
        self.step_progress.setValue(0)
        self.step_progress.setFormat("Detailed step progress unavailable")
        self.monitor_stage.setText("-")
        self.monitor_queue.setText("-")
        self.monitor_elapsed.setText("-")
        self.monitor_eta.setText("-")
        self.monitor_provider.setText("-")
        self.monitor_prompt.setText("-")
        self.monitor_health.setText("-")
        self.monitor_device.setText("-")
        self.monitor_note.setText("")


def _duration_text(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _queue_text(snapshot: ProductionTelemetrySnapshot) -> str:
    parts = [snapshot.queue_state]
    if snapshot.queue_position is not None:
        parts.append(f"position {snapshot.queue_position}")
    if snapshot.live:
        parts.append(
            f"running {snapshot.queue_running_count}, pending {snapshot.queue_pending_count}"
        )
    return " — ".join(parts)


def _health_text(healthy: bool | None, live: bool) -> str:
    if not live:
        return "Not live"
    if healthy is True:
        return "Healthy"
    if healthy is False:
        return "Unavailable / unhealthy"
    return "Unknown"


def _device_text(devices: tuple[ProductionDeviceTelemetry, ...]) -> str:
    if not devices:
        return "-"
    device = devices[0]
    used = device.used_memory_bytes
    total = device.total_memory_bytes
    if used is not None and total is not None and total > 0:
        return f"{device.name} — VRAM {_gib(used):.2f} / {_gib(total):.2f} GiB"
    return device.name


def _gib(value: int) -> float:
    return value / (1024**3)
