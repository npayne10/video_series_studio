"""Read-only display of persisted governed CAP specifications and design reviews.

No writes, model calls, canonical promotion or approval actions.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.design_completion import DESIGN_REVIEW_KEY, DesignReviewPackage
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)


def load_review_snapshot(
    metadata: dict[str, str],
) -> tuple[CAPStructuredSpecification | None, DesignReviewPackage | None, str]:
    """Validate persisted data without changing or silently discarding invalid records."""
    spec_raw = metadata.get(SPECIFICATION_METADATA_KEY)
    review_raw = metadata.get(DESIGN_REVIEW_KEY)
    if spec_raw is None and review_raw is None:
        return None, None, "No reviewed structured CAP specification is stored."
    if spec_raw is None or review_raw is None:
        return None, None, "Incomplete stored CAP review: specification or audit is missing."
    try:
        spec = CAPStructuredSpecification.model_validate(json.loads(spec_raw))
        audit: Any = json.loads(review_raw)
        if not isinstance(audit, dict):
            raise ValueError("Review audit must be a JSON object")
        if audit.get("version") != 1:
            raise ValueError("Unsupported review audit version")
        review = DesignReviewPackage.model_validate(
            {
                "asset_id": spec.asset_id,
                "base_fingerprint": audit["base_fingerprint"],
                "fields": audit["fields"],
                "reviewer": audit["reviewer"],
                "story_fingerprint": audit.get("story_fingerprint", ""),
                "context_fingerprint": audit.get("context_fingerprint", ""),
            }
        )
        # The reviewed master prompt is rebuilt after apply_review generated
        # result_fingerprint; therefore the audit hash does not identify the
        # final serialized CAP. Validate persisted field decisions directly.
        if (
            review.asset_id != spec.asset_id
            or not audit.get("result_fingerprint")
            or audit.get("canon_approved") is not False
            or audit.get("image_authorized") is not False
        ):
            raise ValueError("Stored review identity or authority mismatch")
        for field in review.fields:
            actual = spec.canonical_attributes.get(field.field)
            if field.decision.value in {"accept", "edit"} and actual != field.final_value:
                raise ValueError(f"Reviewed field {field.field} does not match saved CAP")
            if field.decision.value in {"reject", "defer"} and actual is not None:
                raise ValueError(f"Deferred/rejected field {field.field} became canonical")
    except (ValueError, TypeError, KeyError) as exc:
        return None, None, f"Stored CAP review cannot be verified: {exc}"
    return spec, review, "Stored reviewed Draft CAP — no Canon or image approval."


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

        self.fields_table = QTableWidget(0, 5)
        self.fields_table.setObjectName("capReviewedFieldDecisions")
        self.fields_table.setHorizontalHeaderLabels(
            ("Field", "Decision", "Persisted value", "Proposed value", "Origin / rationale")
        )
        self.fields_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.fields_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.fields_table.setWordWrap(True)
        self.fields_table.verticalHeader().setVisible(False)
        self.fields_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.fields_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.fields_table.setMinimumHeight(230)

        attributes = self.specification.canonical_attributes
        for review_field in self.review.fields:
            row = self.fields_table.rowCount()
            self.fields_table.insertRow(row)
            cells = (
                review_field.field,
                review_field.decision.value.title(),
                attributes.get(review_field.field, "—"),
                review_field.proposed_value or "—",
                " | ".join(
                    value
                    for value in (
                        review_field.origin.value,
                        review_field.rationale,
                        review_field.evidence,
                    )
                    if value
                ),
            )
            for column, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.fields_table.setItem(row, column, item)
            self.fields_table.resizeRowToContents(row)
        layout.addWidget(self.fields_table)

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

    @staticmethod
    def _wrapped(value: str) -> QLabel:
        label = QLabel(value or "—")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label
