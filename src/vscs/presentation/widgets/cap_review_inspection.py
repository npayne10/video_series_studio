"""Read-only display of persisted governed CAP specifications and design reviews.

No writes, model calls, canonical promotion or approval actions.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.review_snapshot import load_review_snapshot


class CAPReviewedSpecificationPanel(QWidget):
    """Non-editable, project-backed view of structured CAP details and review decisions."""

    def __init__(self, metadata: dict[str, str], parent: QWidget | None = None) -> None:
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
        if self.specification is None or self.review is None:
            return

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
