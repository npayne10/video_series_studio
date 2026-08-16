"""Read-only Phase 19.5.13 acceptance report dialog."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from vscs.application.automation import AcceptanceState, FunctionalAcceptanceReport


def show_functional_acceptance_report(
    parent: QWidget | None, report: FunctionalAcceptanceReport
) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Phase 19.5.13 — Integration & Functional Acceptance")
    dialog.resize(1100, 620)
    layout = QVBoxLayout(dialog)

    summary = QLabel(
        f"Story: {report.story_id}    Revision: {report.source_revision}\n"
        f"PASS: {report.passed}    REVIEW: {report.review_required}    FAIL: {report.failed}\n\n"
        "This report is read-only. It does not accept proposals, modify governed planners, "
        "create canonical authority, or perform Production Approval."
    )
    summary.setWordWrap(True)
    layout.addWidget(summary)

    table = QTableWidget(len(report.criteria), 3, dialog)
    table.setHorizontalHeaderLabels(("Acceptance Criterion", "State", "Evidence / Required Action"))
    for row, criterion in enumerate(report.criteria):
        table.setItem(row, 0, QTableWidgetItem(criterion.title))
        table.setItem(row, 1, QTableWidgetItem(criterion.state.value.upper()))
        table.setItem(row, 2, QTableWidgetItem(criterion.detail))
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.resizeColumnsToContents()
    table.horizontalHeader().setStretchLastSection(True)
    layout.addWidget(table, 1)

    if report.accepted:
        conclusion = "Phase 19 functional acceptance criteria are satisfied for this Story revision."
    elif report.failed:
        conclusion = "Functional acceptance FAILED. Resolve FAIL criteria before closing Phase 19."
    else:
        conclusion = "Functional acceptance requires human REVIEW of the remaining criteria before Phase 19 closure."
    conclusion_label = QLabel(conclusion)
    conclusion_label.setWordWrap(True)
    layout.addWidget(conclusion_label)

    close_button = QPushButton("Close", dialog)
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)
    dialog.exec()
