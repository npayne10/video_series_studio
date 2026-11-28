"""Read-only display of persisted governed CAP specifications and design reviews.

No writes, model calls, canonical promotion or approval actions.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.design_revision import REVISION_REFRESH_KEY, revise_reviewed_field
from vscs.application.caps.review_snapshot import load_review_snapshot
from vscs.application.caps.service import CAPService
from vscs.domain.caps import CAPStatus


class ReviewedFieldRevisionDialog(QDialog):
    """Independent operator authorization for one accepted design field."""

    def __init__(self, field: str, existing: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Revise Reviewed Specification — {field}")
        self.setObjectName("capReviewedFieldRevisionDialog")
        self.resize(760, 600)
        form = QFormLayout(self)
        self.existing = QPlainTextEdit(existing)
        self.existing.setReadOnly(True)
        self.revised = QPlainTextEdit(existing)
        self.revised.setObjectName("capReviewedRevisionValue")
        self.reviewer = QLineEdit()
        self.reviewer.setObjectName("capReviewedRevisionReviewer")
        self.rationale = QPlainTextEdit()
        self.rationale.setObjectName("capReviewedRevisionRationale")
        form.addRow("Original reviewed value (read-only)", self.existing)
        form.addRow("Revised specification", self.revised)
        form.addRow("Reviewer", self.reviewer)
        form.addRow("Revision rationale", self.rationale)
        notice = QLabel(
            "This revises a Draft design requirement only. Existing knowledge, guidance and "
            "visual candidate assessments must be refreshed. It does not approve the CAP, "
            "MASTER or images, or start generation."
        )
        notice.setWordWrap(True)
        form.addRow(notice)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._confirm)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _confirm(self) -> None:
        if (
            not self.revised.toPlainText().strip()
            or not self.reviewer.text().strip()
            or len(self.rationale.toPlainText().strip()) < 15
            or self.revised.toPlainText().strip() == self.existing.toPlainText().strip()
        ):
            QMessageBox.warning(
                self,
                "Revision Incomplete",
                "Enter a changed specification, reviewer and rationale (15+ characters).",
            )
            return
        if (
            QMessageBox.question(
                self,
                "Authorize Design Revision?",
                "Save this human-authorized Draft specification revision and preserve the prior audit? "
                "Derived knowledge and visual assessments will require refresh.",
            )
            is QMessageBox.StandardButton.Yes
        ):
            self.accept()


class CAPReviewedSpecificationPanel(QWidget):
    """Non-editable, project-backed view of structured CAP details and review decisions."""

    def __init__(
        self,
        metadata: dict[str, str],
        parent: QWidget | None = None,
        *,
        caps: CAPService | None = None,
        asset_id: str = "",
        status: CAPStatus | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("capReviewedSpecificationPanel")
        self.specification, self.review, message = load_review_snapshot(metadata)

        layout = QVBoxLayout(self)
        title = QLabel("Reviewed CAP Specification & Decisions")
        title.setStyleSheet("font-weight: 600;")
        layout.addWidget(title)

        self.status_label = QLabel(message)
        self.status_label.setObjectName("capReviewedSpecificationStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        if metadata.get(REVISION_REFRESH_KEY):
            warning = QLabel(
                "Design revised: refresh structured CAP knowledge, Visual Identity and "
                "Production Notes; reassess candidate images before approval."
            )
            warning.setObjectName("capReviewedRevisionRefreshWarning")
            warning.setWordWrap(True)
            layout.addWidget(warning)
        if self.specification is None or self.review is None:
            return

        if caps is not None and status is CAPStatus.DRAFT:
            revise_button = QPushButton("Revise Reviewed Specification…")
            revise_button.setObjectName("capReviseReviewedSpecificationButton")
            revise_button.clicked.connect(lambda: self._revise(caps, asset_id))
            layout.addWidget(revise_button)

        summary = QFormLayout()
        summary.addRow("Asset ID", QLabel(self.specification.asset_id))
        summary.addRow("Reviewer", QLabel(self.review.reviewer))
        summary.addRow("Story fingerprint", self._wrapped(self.review.story_fingerprint))
        summary.addRow("Context fingerprint", self._wrapped(self.review.context_fingerprint))
        layout.addLayout(summary)

        self.fields_table = QTableWidget(0, 3)
        self.fields_table.setObjectName("capReviewedFieldDecisions")
        self.fields_table.setHorizontalHeaderLabels(("Field", "Decision", "Saved?"))
        self.fields_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fields_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fields_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.fields_table.setWordWrap(False)
        self.fields_table.verticalHeader().setVisible(False)
        self.fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.fields_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.fields_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.fields_table.verticalHeader().setDefaultSectionSize(28)
        self.fields_table.setMinimumWidth(210)
        self.fields_table.setMinimumHeight(220)

        self.final_value_view = QPlainTextEdit()
        self.final_value_view.setObjectName("capReviewedFinalValue")
        self.proposed_value_view = QPlainTextEdit()
        self.proposed_value_view.setObjectName("capReviewedProposedValue")
        self.review_reason_view = QPlainTextEdit()
        self.review_reason_view.setObjectName("capReviewedOriginRationale")
        for view in (
            self.final_value_view,
            self.proposed_value_view,
            self.review_reason_view,
        ):
            view.setReadOnly(True)
            view.setMinimumHeight(75)

        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        for heading, view in (
            ("Persisted final value", self.final_value_view),
            ("Original AI proposal", self.proposed_value_view),
            ("Origin, evidence and review rationale", self.review_reason_view),
        ):
            label = QLabel(heading)
            label.setStyleSheet("font-weight: 600;")
            detail_layout.addWidget(label)
            detail_layout.addWidget(view)

        decisions_layout = QHBoxLayout()
        decisions_layout.addWidget(self.fields_table, 2)
        decisions_layout.addWidget(detail_container, 3)
        layout.addLayout(decisions_layout)

        attributes = self.specification.canonical_attributes
        for review_field in self.review.fields:
            row = self.fields_table.rowCount()
            self.fields_table.insertRow(row)
            cells = (
                review_field.field,
                review_field.decision.value.title(),
                "Yes" if review_field.field in attributes else "No",
            )
            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(value)
                self.fields_table.setItem(row, column, item)
        self.fields_table.currentCellChanged.connect(self._show_decision)
        if self.fields_table.rowCount():
            self.fields_table.setCurrentCell(0, 0)

        for heading, text in (
            ("Design intent", self.specification.design_intent),
            ("Reviewed master reference prompt (unapproved)", self.specification.master_prompt),
            ("Continuity rules", "\n".join(self.specification.continuity_rules)),
            ("Dependency assets", "\n".join(self.specification.dependency_asset_ids)),
        ):
            label = QLabel(heading)
            label.setStyleSheet("font-weight: 600;")
            layout.addWidget(label)
            field = QPlainTextEdit()
            field.setReadOnly(True)
            field.setPlainText(text or "(none)")
            field.setMaximumHeight(105)
            layout.addWidget(field)

    def _show_decision(
        self, row: int, _column: int, _previous_row: int, _previous_column: int
    ) -> None:
        if self.review is None or self.specification is None:
            return
        if row < 0 or row >= len(self.review.fields):
            return
        field = self.review.fields[row]
        self.final_value_view.setPlainText(
            self.specification.canonical_attributes.get(field.field, "(not persisted)")
        )
        self.proposed_value_view.setPlainText(field.proposed_value or "(none)")
        self.review_reason_view.setPlainText(
            "\n".join(
                part
                for part in (
                    f"Decision: {field.decision.value.title()}",
                    f"Origin: {field.origin.value}",
                    f"Rationale: {field.rationale}" if field.rationale else "",
                    f"Evidence: {field.evidence}" if field.evidence else "",
                )
                if part
            )
        )

    @staticmethod
    def _wrapped(value: str) -> QLabel:
        label = QLabel(value or "—")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _revise(self, caps: CAPService, asset_id: str) -> None:
        if self.specification is None or self.review is None:
            return
        row = self.fields_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select Field", "Select a reviewed field first.")
            return
        field = self.review.fields[row]
        existing = self.specification.canonical_attributes.get(field.field)
        if existing is None:
            QMessageBox.warning(
                self, "Field Not Revisable", "Only saved accepted/edited fields can be revised."
            )
            return
        dialog = ReviewedFieldRevisionDialog(field.field, existing, self)
        if not dialog.exec():
            return
        try:
            revise_reviewed_field(
                caps,
                asset_id,
                field=field.field,
                final_value=dialog.revised.toPlainText(),
                reviewer=dialog.reviewer.text(),
                rationale=dialog.rationale.toPlainText(),
                expected_fingerprint=self.specification.fingerprint(),
            )
        except (ValueError, RuntimeError) as exc:
            QMessageBox.critical(self, "Design Revision Not Saved", str(exc))
            return
        self.status_label.setText(
            "Design revision saved with prior audit preserved. Close and reopen this Production "
            "Contract to inspect the current review; refresh derived knowledge and reassess images."
        )
        revision_button = self.findChild(QPushButton, "capReviseReviewedSpecificationButton")
        if revision_button is not None:
            revision_button.setEnabled(False)
