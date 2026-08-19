"""Operator workspace for scheduled live production execution."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
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

from vscs.application.production_execution import (
    ProductionExecutionCandidate,
    ProductionExecutionResult,
    ProductionExecutionUiService,
)


class ProductionExecutionWorkspace(QWidget):
    """Start and monitor approved scheduled production without bypassing queue authority."""

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

        guidance = QLabel(
            "Production Planning ends when an approved schedule is ready. This workspace "
            "starts the scheduled task through VSCS queue/lease/provider authority. On "
            "provider completion, outputs are automatically copied into the project media "
            "output folder and ingested as Generated Media."
        )
        guidance.setWordWrap(True)

        package_row = QHBoxLayout()
        self.production_package = QLineEdit()
        self.production_package.setPlaceholderText(
            "Select the production package JSON consumed by the ComfyUI production workflow"
        )
        self.production_package.textChanged.connect(self._update_start_enabled)
        self.browse_package_button = QPushButton("Browse…")
        self.browse_package_button.clicked.connect(self._browse_package)
        package_row.addWidget(QLabel("Production Package"))
        package_row.addWidget(self.production_package, 1)
        package_row.addWidget(self.browse_package_button)

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
        self.start_button.setEnabled(False)
        self.status_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh)
        self.start_button.clicked.connect(self._start)
        self.status_button.clicked.connect(self._reconcile)

        buttons = QHBoxLayout()
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.status_button)
        buttons.addStretch(1)

        self.summary = QLabel("Open a project to inspect scheduled production work.")
        self.summary.setWordWrap(True)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMinimumHeight(170)

        layout = QVBoxLayout(self)
        layout.addWidget(guidance)
        layout.addLayout(package_row)
        layout.addLayout(buttons)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary)
        layout.addWidget(self.details)

    def refresh(self) -> None:
        service = self._service_provider()
        self._candidates.clear()
        self._selected_task_id = None
        self._execution_active = False
        self.table.setRowCount(0)
        self.start_button.setEnabled(False)
        self.status_button.setEnabled(False)
        self.details.clear()
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
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._selected_task_id = None
            self._execution_active = False
            self._update_start_enabled()
            self.status_button.setEnabled(False)
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
        candidate = self._candidates[task_id]
        self._update_start_enabled()
        self.status_button.setEnabled(True)
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
                )
            )
        )

    def _update_start_enabled(self, _text: str | None = None) -> None:
        self.start_button.setEnabled(
            self._selected_task_id is not None
            and bool(self.production_package.text().strip())
            and not self._execution_active
        )

    def _browse_package(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select Production Package",
            self.production_package.text().strip() or str(Path.home()),
            "JSON files (*.json)",
        )
        if selected:
            self.production_package.setText(selected)

    def _start(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        package = Path(self.production_package.text().strip())
        self._execution_active = True
        self._update_start_enabled()
        try:
            result = service.start(self._selected_task_id, package)
        except Exception as exc:
            self._execution_active = False
            self._update_start_enabled()
            QMessageBox.warning(self, "Start Production", str(exc))
            return
        self._execution_active = not result.terminal
        self._render_result(result)
        self._update_start_enabled()
        self.status_button.setEnabled(not result.terminal)

    def _reconcile(self) -> None:
        if self._selected_task_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        try:
            result = service.reconcile(self._selected_task_id)
        except Exception as exc:
            QMessageBox.warning(self, "Production Execution Status", str(exc))
            return
        self._execution_active = not result.terminal
        self._render_result(result)
        self._update_start_enabled()
        self.status_button.setEnabled(not result.terminal)

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
