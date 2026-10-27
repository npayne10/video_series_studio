"""Field-by-field review of untrusted CAP design detail proposals."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.completeness import REQUIRED_FIELDS
from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification


class CAPDetailReviewDialog(QDialog):
    """Explicit decision for each required field; no writes before confirmation."""

    def __init__(
        self,
        spec: CAPStructuredSpecification,
        *,
        reviewer: str = "Operator",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.reviewer = reviewer
        self.setWindowTitle(f"Review CAP Detail Decisions — {spec.asset_id}")
        self.setMinimumSize(850, 620)
        self.rows: list[tuple[str, QLineEdit, QComboBox, QLineEdit]] = []
        layout = QVBoxLayout(self)
        note = QLabel(
            "Every required field needs Accept/Edit/Reject/Defer. "
            "Suggested details are not proven Story Canon. "
            "This creates only a Draft specification and review record."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        for field in REQUIRED_FIELDS.get(spec.category, ("identity",)):
            value = QLineEdit(spec.canonical_attributes.get(field, ""))
            value.setPlaceholderText("Enter reviewed design detail")
            choice = QComboBox()
            for decision in DetailDecision:
                choice.addItem(decision.value.title(), decision)
            choice.setCurrentIndex(
                choice.findData(
                    DetailDecision.EDIT if not value.text().strip() else DetailDecision.DEFER
                )
            )
            evidence = QLineEdit()
            evidence.setPlaceholderText("Evidence / reason (optional; not auto-verified)")
            row = QHBoxLayout()
            row.addWidget(value, 3)
            row.addWidget(choice, 1)
            row.addWidget(evidence, 2)
            form.addRow(field, row)
            self.rows.append((field, value, choice, evidence))
        scroll.setWidget(body)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_review)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._package: DesignReviewPackage | None = None

    def reviewed(self) -> DesignReviewPackage:
        if self._package is None:
            raise ValueError("No accepted review")
        return self._package

    def _accept_review(self) -> None:
        try:
            fields = []
            for field, value, choice, evidence in self.rows:
                decision: DetailDecision = choice.currentData()
                text = value.text().strip()
                fields.append(
                    DesignFieldReview(
                        field=field,
                        proposed_value=self.spec.canonical_attributes.get(field, ""),
                        final_value=text
                        if decision in {DetailDecision.ACCEPT, DetailDecision.EDIT}
                        else "",
                        decision=decision,
                        origin=(DetailOrigin.DESIGN_PROPOSAL if text else DetailOrigin.UNRESOLVED),
                        evidence=evidence.text().strip(),
                    )
                )
            package = DesignReviewPackage(
                asset_id=self.spec.asset_id,
                base_fingerprint=self.spec.fingerprint(),
                reviewer=self.reviewer,
                fields=tuple(fields),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Detail Review", str(exc))
            return
        self._package = package
        self.accept()
