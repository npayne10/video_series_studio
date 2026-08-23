"""Operator workspace for provider capability validation."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
)
from vscs.domain.provider_capability_validation import (
    CriterionResult,
    HumanDecision,
    ValidationOutcome,
)


class ProviderCapabilityValidationWorkspace(QWidget):
    """Capture evidence and human authority without making providers authoritative."""

    def __init__(
        self,
        service_provider: Callable[[], ProviderCapabilityValidationService | None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service_provider = service_provider
        self._session_id: str | None = None

        self.provider_id = QLineEdit()
        self.session_id = QLineEdit()
        self.pack = QComboBox()
        self.start_button = QPushButton("Start Validation")
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
        actions.addWidget(self.record_button)
        actions.addWidget(self.approve_button)
        actions.addWidget(self.reject_button)
        actions.addWidget(self.refresh_button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(start_row)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addLayout(authority_form)
        layout.addLayout(actions)
        self._set_session_actions(False)
        self.refresh()

    def refresh(self) -> None:
        service = self._service_provider()
        self.pack.clear()
        if service is None:
            self.table.setRowCount(0)
            self.summary.setText("Open a project to validate provider capability.")
            self._set_session_actions(False)
            return
        for pack in service.available_packs():
            self.pack.addItem(
                f"{pack.provider_family} / {pack.capability_id} / {pack.version}",
                pack.pack_id,
            )
        if self._session_id is None:
            self.summary.setText("Start a validation session to capture governed evidence.")
            self._set_session_actions(False)
            return
        session = service.get(self._session_id)
        if session is None:
            self._session_id = None
            self.table.setRowCount(0)
            self._set_session_actions(False)
            return
        pack = next(item for item in service.available_packs() if item.pack_id == session.pack_id)
        results = {result.scenario_id: result for result in session.scenario_results}
        self.table.setRowCount(0)
        for scenario in pack.scenarios:
            result = results[scenario.scenario_id]
            criteria = {item.criterion_id: item for item in result.criterion_results}
            for criterion in scenario.criteria:
                row = self.table.rowCount()
                self.table.insertRow(row)
                scenario_cell = QTableWidgetItem(scenario.label)
                scenario_cell.setData(Qt.ItemDataRole.UserRole, scenario.scenario_id)
                self.table.setItem(row, 0, scenario_cell)
                criterion_cell = QTableWidgetItem(criterion.label)
                criterion_cell.setData(Qt.ItemDataRole.UserRole, criterion.criterion_id)
                self.table.setItem(row, 1, criterion_cell)
                combo = QComboBox()
                for outcome in ValidationOutcome:
                    combo.addItem(outcome.value.replace("_", " ").title(), outcome.value)
                combo.setCurrentIndex(
                    combo.findData(criteria[criterion.criterion_id].outcome.value)
                )
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

    def _start(self) -> None:
        service = self._service_provider()
        if service is None:
            return
        provider_id = self.provider_id.text().strip()
        session_id = self.session_id.text().strip()
        pack_id = self.pack.currentData()
        if not provider_id or not session_id or not pack_id:
            QMessageBox.warning(
                self, "Capability Validation", "Provider, session and pack are required."
            )
            return
        try:
            service.start_session(
                session_id=session_id,
                provider_id=provider_id,
                pack_id=str(pack_id),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Capability Validation", str(exc))
            return
        self._session_id = session_id
        self.refresh()

    def _record_selected(self) -> None:
        service = self._service_provider()
        if service is None or self._session_id is None:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(
                self, "Capability Validation", "Select a scenario criterion row first."
            )
            return
        row = selected[0].row()
        scenario_item = self.table.item(row, 0)
        if scenario_item is None:
            return
        scenario_id = str(scenario_item.data(Qt.ItemDataRole.UserRole))
        actor = self.actor.text().strip()
        if not actor:
            QMessageBox.warning(self, "Capability Validation", "Human actor ID is required.")
            return
        criterion_results: list[CriterionResult] = []
        evidence: set[str] = set()
        scenario_notes: list[str] = []
        for current_row in range(self.table.rowCount()):
            current_scenario = self.table.item(current_row, 0)
            if (
                current_scenario is None
                or str(current_scenario.data(Qt.ItemDataRole.UserRole)) != scenario_id
            ):
                continue
            criterion_item = self.table.item(current_row, 1)
            combo = self.table.cellWidget(current_row, 2)
            evidence_item = self.table.item(current_row, 3)
            notes_item = self.table.item(current_row, 4)
            if criterion_item is None or not isinstance(combo, QComboBox):
                continue
            notes = notes_item.text().strip() if notes_item is not None else ""
            criterion_results.append(
                CriterionResult(
                    criterion_id=str(criterion_item.data(Qt.ItemDataRole.UserRole)),
                    outcome=ValidationOutcome(str(combo.currentData())),
                    notes=notes or None,
                )
            )
            if notes:
                scenario_notes.append(notes)
            if evidence_item is not None:
                evidence.update(
                    value.strip() for value in evidence_item.text().split(",") if value.strip()
                )
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
        self.record_button.setEnabled(enabled)
        self.approve_button.setEnabled(enabled)
        self.reject_button.setEnabled(enabled)
