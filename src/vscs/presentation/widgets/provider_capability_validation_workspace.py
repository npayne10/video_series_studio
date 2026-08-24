"""Operator workspace for provider capability validation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
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

from vscs.application.provider_capability_validation import (
    ProviderCapabilityValidationService,
    ValidationEvidenceIngestionService,
)
from vscs.domain.provider_capability_validation import (
    CriterionResult,
    HumanDecision,
    ValidationOutcome,
)


class ProviderCapabilityValidationWorkspace(QWidget):
    """Capture provider-validation evidence while preserving human authority."""

    def __init__(
        self,
        service_provider: Callable[[], ProviderCapabilityValidationService | None],
        evidence_service_provider: Callable[[], ValidationEvidenceIngestionService | None]
        | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_provider = service_provider
        self._evidence_service_provider = evidence_service_provider
        self._session_id: str | None = None
        self._selected_evidence_file: Path | None = None
        self._refreshing_selectors = False

        self.provider_id = QComboBox()
        self.provider_id.setEditable(True)
        self.provider_id.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.session_id = QComboBox()
        self.session_id.setEditable(True)
        self.session_id.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.pack = QComboBox()
        self.pack.currentIndexChanged.connect(self._validation_pack_changed)
        self.provider_id.currentTextChanged.connect(self._provider_changed)
        self.session_id.currentIndexChanged.connect(self._session_selection_changed)
        self.start_button = QPushButton("Start / Resume Validation")
        self.start_button.clicked.connect(self._start)
        start_form = QFormLayout()
        start_form.addRow("Provider ID", self.provider_id)
        start_form.addRow("Session ID", self.session_id)
        start_form.addRow("Validation pack", self.pack)
        start_row = QHBoxLayout()
        start_row.addLayout(start_form, 1)
        start_row.addWidget(self.start_button)

        self.summary = QLabel("Open a project to validate provider capability.")
        self.summary.setWordWrap(True)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ("Scenario", "Criterion", "Outcome", "Evidence media IDs", "Notes")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.DoubleClicked)

        self.evidence_path = QLineEdit()
        self.evidence_path.setReadOnly(True)
        self.evidence_media_id = QLineEdit()
        self.evidence_media_id.setReadOnly(True)
        self.select_evidence_button = QPushButton("Select Evidence File")
        self.ingest_evidence_button = QPushButton("Ingest Evidence")
        self.select_evidence_button.clicked.connect(self._select_evidence_file)
        self.ingest_evidence_button.clicked.connect(self._ingest_evidence)
        evidence_form = QFormLayout()
        evidence_form.addRow("Selected evidence file", self.evidence_path)
        evidence_form.addRow("Evidence Media ID", self.evidence_media_id)
        evidence_actions = QHBoxLayout()
        evidence_actions.addWidget(self.select_evidence_button)
        evidence_actions.addWidget(self.ingest_evidence_button)
        evidence_actions.addStretch(1)

        self.actor = QLineEdit()
        self.decision_reason = QTextEdit()
        self.decision_reason.setMaximumHeight(80)
        self.record_button = QPushButton("Record Selected Scenario")
        self.approve_button = QPushButton("Approve Capability")
        self.reject_button = QPushButton("Reject Capability")
        self.refresh_button = QPushButton("Refresh")
        self.record_button.clicked.connect(self._record_selected)
        self.approve_button.clicked.connect(lambda: self._decide(HumanDecision.APPROVED))
        self.reject_button.clicked.connect(lambda: self._decide(HumanDecision.REJECTED))
        self.refresh_button.clicked.connect(self.refresh)
        authority_form = QFormLayout()
        authority_form.addRow("Human actor ID", self.actor)
        authority_form.addRow("Decision reason", self.decision_reason)
        actions = QHBoxLayout()
        for button in (
            self.record_button,
            self.approve_button,
            self.reject_button,
            self.refresh_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(start_row)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(evidence_form)
        layout.addLayout(evidence_actions)
        layout.addLayout(authority_form)
        layout.addLayout(actions)
        self._set_session_actions(False)
        self.refresh()

    def refresh(self) -> None:
        service = self._service_provider()
        selected_pack = self.pack.currentData()
        self._refreshing_selectors = True
        self.pack.clear()
        if service is None:
            self.provider_id.clear()
            self.session_id.clear()
            self.table.setRowCount(0)
            self.summary.setText("Open a project to validate provider capability.")
            self._set_session_actions(False)
            self._refreshing_selectors = False
            return
        for pack in service.available_packs():
            self.pack.addItem(
                f"{pack.provider_family} / {pack.capability_id} / {pack.version}", pack.pack_id
            )
        if selected_pack is not None:
            selected_index = self.pack.findData(selected_pack)
            if selected_index >= 0:
                self.pack.setCurrentIndex(selected_index)
        self._refreshing_selectors = False
        self._populate_known_sessions()

        if self._session_id is None:
            self.table.setRowCount(0)
            self.summary.setText(
                "Choose a validation pack, then select an existing Provider ID and Session ID, "
                "or enter new IDs to create a validation session."
            )
            self._set_session_actions(False)
            return
        session = service.get(self._session_id)
        if session is None:
            self._session_id = None
            self.table.setRowCount(0)
            self._set_session_actions(False)
            return
        self._set_combo_text(self.provider_id, session.provider_id)
        self._set_combo_text(self.session_id, session.session_id)
        pack_index = self.pack.findData(session.pack_id)
        if pack_index >= 0:
            self.pack.setCurrentIndex(pack_index)
        pack = next(item for item in service.available_packs() if item.pack_id == session.pack_id)
        results = {result.scenario_id: result for result in session.scenario_results}
        self.table.setRowCount(0)
        for scenario in pack.scenarios:
            result = results[scenario.scenario_id]
            criteria = {item.criterion_id: item for item in result.criterion_results}
            for criterion in scenario.criteria:
                row = self.table.rowCount()
                self.table.insertRow(row)
                scenario_item = QTableWidgetItem(scenario.label)
                scenario_item.setData(Qt.ItemDataRole.UserRole, scenario.scenario_id)
                self.table.setItem(row, 0, scenario_item)
                criterion_item = QTableWidgetItem(criterion.label)
                criterion_item.setData(Qt.ItemDataRole.UserRole, criterion.criterion_id)
                self.table.setItem(row, 1, criterion_item)
                combo = QComboBox()
                for outcome in ValidationOutcome:
                    combo.addItem(outcome.value.replace("_", " ").title(), outcome.value)
                combo.setCurrentIndex(combo.findData(criteria[criterion.criterion_id].outcome.value))
                self.table.setCellWidget(row, 2, combo)
                self.table.setItem(row, 3, QTableWidgetItem(", ".join(result.evidence_media_ids)))
                self.table.setItem(
                    row, 4, QTableWidgetItem(criteria[criterion.criterion_id].notes or "")
                )
        self.summary.setText(
            f"Session {session.session_id} — recommendation: {session.recommendation.value} — "
            f"human decision: {session.human_decision.value}"
        )
        self._set_session_actions(True)

    def _validation_pack_changed(self) -> None:
        if self._refreshing_selectors:
            return
        self._session_id = None
        self.table.setRowCount(0)
        self._set_session_actions(False)
        self._populate_known_sessions()

    def _provider_changed(self) -> None:
        if self._refreshing_selectors:
            return
        self._session_id = None
        self.table.setRowCount(0)
        self._set_session_actions(False)
        self._populate_session_ids_for_provider()

    def _session_selection_changed(self, index: int) -> None:
        if self._refreshing_selectors or index < 0:
            return
        service = self._service_provider()
        session_id = self.session_id.itemData(index)
        if service is None or not session_id:
            return
        session = service.get(str(session_id))
        if session is None:
            return
        self._set_combo_text(self.provider_id, session.provider_id)

    def _populate_known_sessions(self) -> None:
        service = self._service_provider()
        pack_id = self.pack.currentData()
        if service is None or pack_id is None:
            return
        current_provider = self.provider_id.currentText().strip()
        matching_sessions = tuple(
            session for session in service.list_all() if session.pack_id == str(pack_id)
        )
        providers = sorted({session.provider_id for session in matching_sessions})
        self._refreshing_selectors = True
        self.provider_id.clear()
        self.provider_id.addItems(providers)
        self._refreshing_selectors = False
        if current_provider and current_provider in providers:
            self._set_combo_text(self.provider_id, current_provider)
        elif providers:
            self.provider_id.setCurrentIndex(0)
        else:
            self.provider_id.setEditText("")
        self._populate_session_ids_for_provider()

    def _populate_session_ids_for_provider(self) -> None:
        service = self._service_provider()
        pack_id = self.pack.currentData()
        provider_id = self.provider_id.currentText().strip()
        if service is None or pack_id is None:
            return
        current_session = self.session_id.currentText().strip()
        sessions = sorted(
            (
                session
                for session in service.list_all()
                if session.pack_id == str(pack_id)
                and (not provider_id or session.provider_id == provider_id)
            ),
            key=lambda session: session.session_id,
        )
        self._refreshing_selectors = True
        self.session_id.clear()
        for session in sessions:
            self.session_id.addItem(session.session_id, session.session_id)
        self._refreshing_selectors = False
        if current_session and any(session.session_id == current_session for session in sessions):
            self._set_combo_text(self.session_id, current_session)
        elif sessions:
            self.session_id.setCurrentIndex(0)
        else:
            self.session_id.setEditText("")

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setEditText(value)

    def _start(self) -> None:
        service = self._service_provider()
        if service is None:
            return
        provider_id = self.provider_id.currentText().strip()
        session_id = self.session_id.currentText().strip()
        pack_id = self.pack.currentData()
        if not provider_id or not session_id or not pack_id:
            QMessageBox.warning(
                self, "Capability Validation", "Provider, session and pack are required."
            )
            return

        existing = service.get(session_id)
        if existing is not None:
            if existing.provider_id != provider_id:
                QMessageBox.critical(
                    self,
                    "Capability Validation",
                    f"Session {session_id} belongs to provider {existing.provider_id}, "
                    f"not {provider_id}.",
                )
                return
            if existing.pack_id != str(pack_id):
                QMessageBox.critical(
                    self,
                    "Capability Validation",
                    f"Session {session_id} uses validation pack {existing.pack_id}, not {pack_id}.",
                )
                return
            self._session_id = session_id
            self.refresh()
            return

        try:
            service.start_session(
                session_id=session_id, provider_id=provider_id, pack_id=str(pack_id)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Capability Validation", str(exc))
            return
        self._session_id = session_id
        self.refresh()

    def _selected_context(self) -> tuple[str, str] | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(
                self, "Capability Validation", "Select a scenario criterion row first."
            )
            return None
        row = rows[0].row()
        scenario = self.table.item(row, 0)
        criterion = self.table.item(row, 1)
        if scenario is None or criterion is None:
            return None
        return (
            str(scenario.data(Qt.ItemDataRole.UserRole)),
            str(criterion.data(Qt.ItemDataRole.UserRole)),
        )

    def _select_evidence_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Provider Validation Evidence",
            "",
            "Media Files (*.mp4 *.mov *.mkv *.webm *.png *.jpg *.jpeg)",
        )
        if filename:
            self._selected_evidence_file = Path(filename)
            self.evidence_path.setText(filename)
            self.evidence_media_id.clear()

    def _default_evidence_service(
        self, service: ProviderCapabilityValidationService
    ) -> ValidationEvidenceIngestionService | None:
        root = getattr(service.media_repository, "root", None)
        if root is None:
            return None
        project_directory = Path(root).resolve(strict=False).parent.parent
        return ValidationEvidenceIngestionService(
            project_directory=project_directory,
            media_repository=service.media_repository,
        )

    def _ingest_evidence(self) -> None:
        service = self._service_provider()
        if service is None or self._session_id is None:
            return
        evidence_service = (
            self._evidence_service_provider()
            if self._evidence_service_provider is not None
            else self._default_evidence_service(service)
        )
        context = self._selected_context()
        if evidence_service is None or context is None:
            QMessageBox.warning(
                self, "Capability Validation", "Validation evidence ingestion is unavailable."
            )
            return
        if self._selected_evidence_file is None:
            QMessageBox.warning(self, "Capability Validation", "Select an evidence file first.")
            return
        actor = self.actor.text().strip()
        if not actor:
            QMessageBox.warning(self, "Capability Validation", "Human actor ID is required.")
            return
        session = service.get(self._session_id)
        if session is None:
            return
        scenario_id, criterion_id = context
        try:
            result = evidence_service.ingest(
                source_file=self._selected_evidence_file,
                provider_id=session.provider_id,
                session_id=session.session_id,
                pack_id=session.pack_id,
                scenario_id=scenario_id,
                criterion_id=criterion_id,
                actor=actor,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Capability Validation", str(exc))
            return
        media_id = result.media.media_id
        self.evidence_media_id.setText(media_id)
        for row in range(self.table.rowCount()):
            scenario_item = self.table.item(row, 0)
            if (
                scenario_item is None
                or str(scenario_item.data(Qt.ItemDataRole.UserRole)) != scenario_id
            ):
                continue
            item = self.table.item(row, 3)
            values = {v.strip() for v in (item.text() if item else "").split(",") if v.strip()}
            values.add(media_id)
            self.table.setItem(row, 3, QTableWidgetItem(", ".join(sorted(values))))

    def _record_selected(self) -> None:
        service = self._service_provider()
        if service is None or self._session_id is None:
            return
        context = self._selected_context()
        if context is None:
            return
        scenario_id, _ = context
        actor = self.actor.text().strip()
        if not actor:
            QMessageBox.warning(self, "Capability Validation", "Human actor ID is required.")
            return
        criterion_results: list[CriterionResult] = []
        evidence: set[str] = set()
        scenario_notes: list[str] = []
        for row in range(self.table.rowCount()):
            scenario = self.table.item(row, 0)
            if scenario is None or str(scenario.data(Qt.ItemDataRole.UserRole)) != scenario_id:
                continue
            criterion = self.table.item(row, 1)
            combo = self.table.cellWidget(row, 2)
            evidence_item = self.table.item(row, 3)
            notes_item = self.table.item(row, 4)
            if criterion is None or not isinstance(combo, QComboBox):
                continue
            notes = notes_item.text().strip() if notes_item else ""
            criterion_results.append(
                CriterionResult(
                    criterion_id=str(criterion.data(Qt.ItemDataRole.UserRole)),
                    outcome=ValidationOutcome(str(combo.currentData())),
                    notes=notes or None,
                )
            )
            if evidence_item:
                evidence.update(
                    value.strip() for value in evidence_item.text().split(",") if value.strip()
                )
            if notes:
                scenario_notes.append(notes)
        try:
            service.record_scenario(
                session_id=self._session_id,
                scenario_id=scenario_id,
                criterion_results=tuple(criterion_results),
                evidence_media_ids=tuple(sorted(evidence)),
                actor=actor,
                notes="; ".join(scenario_notes) or None,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Capability Validation", str(exc))
            return
        self.refresh()

    def _decide(self, decision: HumanDecision) -> None:
        service = self._service_provider()
        if service is None or self._session_id is None:
            return
        actor = self.actor.text().strip()
        reason = self.decision_reason.toPlainText().strip()
        if not actor or not reason:
            QMessageBox.warning(
                self,
                "Capability Validation",
                "Human actor ID and decision reason are required.",
            )
            return
        try:
            service.decide(
                session_id=self._session_id,
                decision=decision,
                actor=actor,
                reason=reason,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Capability Validation", str(exc))
            return
        self.refresh()

    def _set_session_actions(self, enabled: bool) -> None:
        self.select_evidence_button.setEnabled(enabled)
        self.ingest_evidence_button.setEnabled(enabled)
        self.record_button.setEnabled(enabled)
        self.approve_button.setEnabled(enabled)
        self.reject_button.setEnabled(enabled)
