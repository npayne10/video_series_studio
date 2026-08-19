"""Operator workspace for authoritative Generated Media governance."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

from vscs.application.generated_media import (
    GeneratedMediaDetailView,
    GeneratedMediaListItem,
    GeneratedMediaUiService,
)
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
        self._all_items: tuple[GeneratedMediaListItem, ...] = ()
        self._rebuilding_filters = False

        self.production_filter = QComboBox()
        self.episode_filter = QComboBox()
        self.task_filter = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.production_filter.currentIndexChanged.connect(self._production_changed)
        self.episode_filter.currentIndexChanged.connect(self._episode_changed)
        self.task_filter.currentIndexChanged.connect(self._apply_filters)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Production"))
        filter_row.addWidget(self.production_filter, 2)
        filter_row.addWidget(QLabel("Episode"))
        filter_row.addWidget(self.episode_filter, 2)
        filter_row.addWidget(QLabel("Task"))
        filter_row.addWidget(self.task_filter, 3)
        filter_row.addWidget(self.refresh_button)

        self.media_table = QTableWidget(0, 10)
        self.media_table.setHorizontalHeaderLabels(
            (
                "Production",
                "Episode",
                "Scene",
                "Shot",
                "Task",
                "Kind",
                "State",
                "Revision",
                "Technical",
                "Selected",
            )
        )
        self.media_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.media_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.media_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.media_table.itemSelectionChanged.connect(self._selection_changed)

        self.summary = QLabel("Open a project to browse Generated Media.")
        self.summary.setWordWrap(True)
        self.path_label = QLabel()
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.identifiers = QTextEdit()
        self.identifiers.setReadOnly(True)
        self.identifiers.setMaximumHeight(115)
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
        details_layout.addWidget(QLabel("Stable IDs"))
        details_layout.addWidget(self.identifiers)
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
        self._reset_filters()

    def refresh(self) -> None:
        service = self._service_provider()
        self._current_media_id = None
        self._clear_detail()
        if service is None:
            self._all_items = ()
            self._reset_filters()
            self.media_table.setRowCount(0)
            self.summary.setText("Open a project to browse Generated Media.")
            return
        try:
            self._all_items = service.list_all()
        except Exception as exc:
            QMessageBox.critical(self, "Generated Media", str(exc))
            return
        self._rebuild_filters_preserving_selection()
        self._apply_filters()

    def _production_changed(self) -> None:
        if self._rebuilding_filters:
            return
        self._rebuild_episode_filter()
        self._rebuild_task_filter()
        self._apply_filters()

    def _episode_changed(self) -> None:
        if self._rebuilding_filters:
            return
        self._rebuild_task_filter()
        self._apply_filters()

    def _apply_filters(self) -> None:
        if self._rebuilding_filters:
            return
        production = self._combo_value(self.production_filter)
        episode = self._combo_value(self.episode_filter)
        task = self._combo_value(self.task_filter)
        items = tuple(
            item
            for item in self._all_items
            if (production is None or item.production_id == production)
            and (episode is None or item.episode_id == episode)
            and (task is None or item.task_id == task)
        )
        self._populate_table(items)
        if not self._all_items:
            self.summary.setText("No Generated Media has been ingested for this project yet.")
        elif not items:
            self.summary.setText("No Generated Media matches the current filters.")
        else:
            self.summary.setText(
                f"Showing {len(items)} of {len(self._all_items)} Generated Media record(s)."
            )

    def _populate_table(self, items: tuple[GeneratedMediaListItem, ...]) -> None:
        self.media_table.setRowCount(0)
        self._current_media_id = None
        self._set_actions_enabled(False)
        for item in items:
            row = self.media_table.rowCount()
            self.media_table.insertRow(row)
            values = (
                item.production_id,
                item.episode_id,
                item.scene_id or "—",
                item.shot_id or "—",
                item.task_label,
                item.kind.value,
                item.state.value,
                str(item.revision),
                item.technical_status,
                "Yes" if item.selected else "No",
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 4:
                    cell.setToolTip(item.task_id)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.media_id)
                self.media_table.setItem(row, column, cell)

    def _rebuild_filters_preserving_selection(self) -> None:
        previous_production = self._combo_value(self.production_filter)
        previous_episode = self._combo_value(self.episode_filter)
        previous_task = self._combo_value(self.task_filter)
        self._rebuilding_filters = True
        try:
            self._fill_combo(
                self.production_filter,
                "All Productions",
                tuple(sorted({item.production_id for item in self._all_items})),
                previous_production,
            )
            self._rebuild_episode_filter(previous_episode)
            self._rebuild_task_filter(previous_task)
        finally:
            self._rebuilding_filters = False

    def _rebuild_episode_filter(self, preferred: str | None = None) -> None:
        production = self._combo_value(self.production_filter)
        if preferred is None:
            preferred = self._combo_value(self.episode_filter)
        episodes = tuple(
            sorted(
                {
                    item.episode_id
                    for item in self._all_items
                    if production is None or item.production_id == production
                }
            )
        )
        was_rebuilding = self._rebuilding_filters
        self._rebuilding_filters = True
        try:
            self._fill_combo(self.episode_filter, "All Episodes", episodes, preferred)
        finally:
            self._rebuilding_filters = was_rebuilding

    def _rebuild_task_filter(self, preferred: str | None = None) -> None:
        production = self._combo_value(self.production_filter)
        episode = self._combo_value(self.episode_filter)
        if preferred is None:
            preferred = self._combo_value(self.task_filter)
        task_items = {
            item.task_id: item.task_label
            for item in self._all_items
            if (production is None or item.production_id == production)
            and (episode is None or item.episode_id == episode)
        }
        was_rebuilding = self._rebuilding_filters
        self._rebuilding_filters = True
        try:
            self.task_filter.clear()
            self.task_filter.addItem("All Tasks", None)
            for task_id, label in sorted(task_items.items(), key=lambda pair: pair[1].casefold()):
                self.task_filter.addItem(label, task_id)
                index = self.task_filter.count() - 1
                self.task_filter.setItemData(index, task_id, Qt.ItemDataRole.ToolTipRole)
            self._select_combo_value(self.task_filter, preferred)
        finally:
            self._rebuilding_filters = was_rebuilding

    def _reset_filters(self) -> None:
        self._rebuilding_filters = True
        try:
            for combo, label in (
                (self.production_filter, "All Productions"),
                (self.episode_filter, "All Episodes"),
                (self.task_filter, "All Tasks"),
            ):
                combo.clear()
                combo.addItem(label, None)
        finally:
            self._rebuilding_filters = False

    @staticmethod
    def _fill_combo(
        combo: QComboBox,
        all_label: str,
        values: tuple[str, ...],
        preferred: str | None,
    ) -> None:
        combo.clear()
        combo.addItem(all_label, None)
        for value in values:
            combo.addItem(value, value)
        GeneratedMediaWorkspaceWidget._select_combo_value(combo, preferred)

    @staticmethod
    def _select_combo_value(combo: QComboBox, value: str | None) -> None:
        if value is None:
            combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    @staticmethod
    def _combo_value(combo: QComboBox) -> str | None:
        value = combo.currentData()
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def _selection_changed(self) -> None:
        rows = self.media_table.selectionModel().selectedRows()
        if not rows:
            self._current_media_id = None
            self._set_actions_enabled(False)
            return
        first_cell = self.media_table.item(rows[0].row(), 0)
        if first_cell is None:
            return
        media_id = first_cell.data(Qt.ItemDataRole.UserRole)
        if media_id is None:
            return
        self._current_media_id = str(media_id)
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
        selected = (
            detail.selection is not None and detail.selection.selected_media_id == media.media_id
        )
        location = media.scope.shot_id or media.scope.scene_id or media.scope.episode_id
        self.summary.setText(
            f"{media.kind.value.replace('_', ' ').title()} — {location} — {media.state.value} — "
            f"revision {media.revision} — technical {technical} — "
            f"selected {'yes' if selected else 'no'}"
        )
        self.path_label.setText(f"Managed file: {media.file.relative_path}")
        self.identifiers.setPlainText(
            "\n".join(
                (
                    f"Media ID: {media.media_id}",
                    f"Production ID: {media.scope.production_id}",
                    f"Episode ID: {media.scope.episode_id}",
                    f"Scene ID: {media.scope.scene_id or '-'}",
                    f"Shot ID: {media.scope.shot_id or '-'}",
                    f"ProductionTask ID: {media.scope.production_task_id}",
                )
            )
        )
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
            dict(media.technical_metadata).get("technical_validation.status", "").strip().casefold()
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
        self.refresh()

    def _clear_detail(self) -> None:
        self.path_label.clear()
        self.identifiers.clear()
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
