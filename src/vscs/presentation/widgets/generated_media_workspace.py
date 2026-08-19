"""Operator workspace for authoritative Generated Media governance."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.generated_media import GeneratedMediaDetailView, GeneratedMediaUiService
from vscs.domain.generated_media import GeneratedMediaState


class GeneratedMediaActionDialog(QDialog):
    """Collect explicit human authority and a mandatory governance reason."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(520)
        self.actor_id = QLineEdit()
        self.display_name = QLineEdit()
        self.reason = QTextEdit()
        self.reason.setMinimumHeight(100)
        form = QFormLayout()
        form.addRow("Human actor ID", self.actor_id)
        form.addRow("Display name", self.display_name)
        form.addRow("Reason / comment", self.reason)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.actor_id.text().strip(),
            self.display_name.text().strip(),
            self.reason.toPlainText().strip(),
        )

    def _validate(self) -> None:
        if any(not value for value in self.values()):
            QMessageBox.warning(
                self,
                "Human Authority Required",
                "Actor ID, display name and reason are required.",
            )
            return
        self.accept()


class GeneratedMediaWorkspaceWidget(QWidget):
    """Browse and govern Generated Media strictly through application services."""

    def __init__(
        self,
        service_provider: Callable[[], GeneratedMediaUiService | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_provider = service_provider
        self._current_media_id: str | None = None

        self.production_id = QLineEdit()
        self.production_id.setPlaceholderText("Production ID")
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Production"))
        filter_row.addWidget(self.production_id, 1)
        filter_row.addWidget(self.refresh_button)

        self.media_table = QTableWidget(0, 7)
        self.media_table.setHorizontalHeaderLabels(
            ("Media ID", "Task", "Kind", "State", "Revision", "Technical", "Selected")
        )
        self.media_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.media_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.media_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.media_table.itemSelectionChanged.connect(self._selection_changed)

        self.summary = QLabel("Select Generated Media to inspect its authority.")
        self.summary.setWordWrap(True)
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.provenance = QTextEdit()
        self.provenance.setReadOnly(True)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.candidates = QTextEdit()
        self.candidates.setReadOnly(True)

        details = QWidget()
        details_layout = QVBoxLayout(details)
        details_layout.addWidget(self.summary)
        details_layout.addWidget(self.path_label)
        details_layout.addWidget(QLabel("Provenance"))
        details_layout.addWidget(self.provenance)
        details_layout.addWidget(QLabel("Governance / Selection History"))
        details_layout.addWidget(self.history)
        details_layout.addWidget(QLabel("Revision Candidates"))
        details_layout.addWidget(self.candidates)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.media_table)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        self.submit_button = QPushButton("Submit for Review")
        self.approve_button = QPushButton("Approve")
        self.reject_button = QPushButton("Reject")
        self.select_button = QPushButton("Select")
        self.supersede_button = QPushButton("Supersede & Select")
        self.submit_button.clicked.connect(lambda: self._run_action("submit"))
        self.approve_button.clicked.connect(lambda: self._run_action("approve"))
        self.reject_button.clicked.connect(lambda: self._run_action("reject"))
        self.select_button.clicked.connect(lambda: self._run_action("select"))
        self.supersede_button.clicked.connect(lambda: self._run_action("supersede"))
        action_row = QHBoxLayout()
        for button in (
            self.submit_button,
            self.approve_button,
            self.reject_button,
            self.select_button,
            self.supersede_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(filter_row)
        layout.addWidget(splitter, 1)
        layout.addLayout(action_row)
        self._set_actions_enabled(False)

    def refresh(self) -> None:
        service = self._service_provider()
        production_id = self.production_id.text().strip()
        self.media_table.setRowCount(0)
        self._current_media_id = None
        self._clear_detail()
        if service is None:
            self.summary.setText("Open a project to browse Generated Media.")
            return
        if not production_id:
            self.summary.setText("Enter a Production ID, then choose Refresh.")
            return
        try:
            items = service.list_for_production(production_id)
        except Exception as exc:
            QMessageBox.critical(self, "Generated Media", str(exc))
            return
        for item in items:
            row = self.media_table.rowCount()
            self.media_table.insertRow(row)
            values = (
                item.media_id,
                item.task_id,
                item.kind.value,
                item.state.value,
                str(item.revision),
                item.technical_status,
                "Yes" if item.selected else "No",
            )
            for column, value in enumerate(values):
                self.media_table.setItem(row, column, QTableWidgetItem(value))
        self.summary.setText(f"{len(items)} Generated Media record(s) for {production_id}.")

    def _selection_changed(self) -> None:
        rows = self.media_table.selectionModel().selectedRows()
        if not rows:
            self._current_media_id = None
            self._set_actions_enabled(False)
            return
        media_id_item = self.media_table.item(rows[0].row(), 0)
        if media_id_item is None:
            return
        self._current_media_id = media_id_item.text()
        service = self._service_provider()
        if service is None:
            return
        try:
            detail = service.detail(self._current_media_id)
        except Exception as exc:
            QMessageBox.critical(self, "Generated Media", str(exc))
            return
        self._show_detail(detail)
        self._update_action_availability(detail)

    def _show_detail(self, detail: GeneratedMediaDetailView) -> None:
        media = detail.media
        technical = dict(media.technical_metadata).get(
            "technical_validation.status", "not-validated"
        )
        selected = detail.selection is not None and detail.selection.selected_media_id == media.media_id
        self.summary.setText(
            f"{media.media_id} — {media.kind.value} — {media.state.value} — "
            f"revision {media.revision} — technical {technical} — "
            f"selected {'yes' if selected else 'no'}"
        )
        self.path_label.setText(f"Managed file: {media.file.relative_path}")
        provenance_lines = [
            f"Execution: {media.provenance.execution_id}",
            f"Provider: {media.provenance.provider_id}",
            f"Provider job: {media.provenance.provider_job_id}",
            f"Render request: {media.provenance.render_request_id or '-'}",
            f"Render output: {media.provenance.render_output_id or '-'}",
            f"Workflow: {media.provenance.workflow_id or '-'}",
        ]
        provenance_lines.extend(f"{key}: {value}" for key, value in media.provenance.attributes)
        self.provenance.setPlainText("\n".join(provenance_lines))

        history_lines = [
            f"{event.occurred_at.isoformat()}  {event.from_state.value} → {event.to_state.value}  "
            f"{event.actor}  {event.reason}"
            + (f"  replacement={event.replacement_media_id}" if event.replacement_media_id else "")
            for event in media.governance_history
        ]
        if detail.selection is not None:
            history_lines.append("")
            history_lines.append(f"Selection: {detail.selection.selection_id}")
            history_lines.extend(
                f"{event.occurred_at.isoformat()}  {event.previous_media_id or '-'} → "
                f"{event.selected_media_id} r{event.selected_revision}  "
                f"{event.actor}  {event.reason}"
                for event in detail.selection.history
            )
        self.history.setPlainText("\n".join(history_lines) or "No governance history yet.")
        self.candidates.setPlainText(
            "\n".join(
                f"r{candidate.revision}  {candidate.media_id}  {candidate.state.value}"
                for candidate in detail.candidates
            )
            or "No revision candidates."
        )

    def _update_action_availability(self, detail: GeneratedMediaDetailView) -> None:
        media = detail.media
        technical_passed = (
            dict(media.technical_metadata)
            .get("technical_validation.status", "")
            .strip()
            .casefold()
            == "passed"
        )
        selected_media_id = detail.selection.selected_media_id if detail.selection else None
        self.submit_button.setEnabled(
            media.state is GeneratedMediaState.GENERATED and technical_passed
        )
        reviewable = media.state is GeneratedMediaState.UNDER_REVIEW and technical_passed
        self.approve_button.setEnabled(reviewable)
        self.reject_button.setEnabled(reviewable)
        self.select_button.setEnabled(
            media.state is GeneratedMediaState.APPROVED and detail.selection is None
        )
        self.supersede_button.setEnabled(
            media.state is GeneratedMediaState.APPROVED
            and detail.selection is not None
            and selected_media_id != media.media_id
        )

    def _run_action(self, action: str) -> None:
        if self._current_media_id is None:
            return
        service = self._service_provider()
        if service is None:
            return
        title = {
            "submit": "Submit Generated Media for Review",
            "approve": "Approve Generated Media",
            "reject": "Reject Generated Media",
            "select": "Select Authoritative Generated Media",
            "supersede": "Supersede and Select Generated Media",
        }[action]
        dialog = GeneratedMediaActionDialog(title, self)
        if dialog.exec() is not QDialog.DialogCode.Accepted:
            return
        actor_id, display_name, reason = dialog.values()
        try:
            command = {
                "submit": service.submit_for_review,
                "approve": service.approve,
                "reject": service.reject,
                "select": service.select,
                "supersede": service.supersede_and_select,
            }[action]
            command(
                self._current_media_id,
                actor_id=actor_id,
                display_name=display_name,
                reason=reason,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Generated Media Governance", str(exc))
            return
        selected_media_id = self._current_media_id
        self.refresh()
        self._reselect(selected_media_id)

    def _reselect(self, media_id: str) -> None:
        for row in range(self.media_table.rowCount()):
            item = self.media_table.item(row, 0)
            if item is not None and item.text() == media_id:
                self.media_table.selectRow(row)
                return

    def _clear_detail(self) -> None:
        self.summary.setText("Select Generated Media to inspect its authority.")
        self.path_label.clear()
        self.provenance.clear()
        self.history.clear()
        self.candidates.clear()
        self._set_actions_enabled(False)

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.submit_button,
            self.approve_button,
            self.reject_button,
            self.select_button,
            self.supersede_button,
        ):
            button.setEnabled(enabled)
