"""Human review of Story-derived category-specific CAP proposals."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.completeness import assess_completeness
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.presentation.dialogs.cap_document_import_dialog import parse_mapping_lines


class StoryCAPSpecificationDialog(QDialog):
    """Review and edit unapproved canonical attributes and reference prompt."""

    def __init__(self, proposal: StoryCAPProposal, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.proposal = proposal
        spec = proposal.specification
        self.setWindowTitle(f"Review Story CAP Draft — {spec.asset_id}")
        self.setMinimumSize(770, 560)
        note = QLabel(
            "Advisory AI proposal only — distinguish story evidence from inferred design. "
            "Saving stores Draft metadata, never approves Canon or references."
        )
        note.setWordWrap(True)
        self.intent = QTextEdit(spec.design_intent)
        self.attributes = QTextEdit(
            "\n".join(f"{key}={value}" for key, value in spec.canonical_attributes.items())
        )
        self.completeness = QLabel()
        self.completeness.setWordWrap(True)
        self.attributes.textChanged.connect(self._update_completeness)
        self.variants = QTextEdit()
        self.variants.setPlaceholderText("Optional variant=value1|value2")
        self.prompt = QTextEdit(spec.master_prompt)
        self.rules = QTextEdit("\n".join(spec.continuity_rules))
        form = QFormLayout()
        form.addRow("Design intent", self.intent)
        form.addRow("Canonical attributes (key=value)", self.attributes)
        form.addRow("Completeness (not approval)", self.completeness)
        form.addRow("Allowed variants", self.variants)
        form.addRow("Master reference prompt", self.prompt)
        form.addRow("Continuity (one rule per line)", self.rules)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(QLabel("\n".join(proposal.limitations)))
        layout.addWidget(buttons)
        self._reviewed: CAPStructuredSpecification | None = None
        self._update_completeness()

    def _update_completeness(self) -> None:
        try:
            attributes = parse_mapping_lines(self.attributes.toPlainText())
            proposal = self.proposal.specification.model_copy(
                update={"canonical_attributes": attributes}
            )
            result = assess_completeness(proposal)
            missing = ", ".join(result.missing) or "none"
            self.completeness.setText(
                f"Missing category fields: {missing}. "
                "Story-suggested values remain unverified until source evidence review. "
                "Saving a Draft does not authorize image generation."
            )
        except ValueError:
            self.completeness.setText("Enter valid key=value canonical attributes.")

    def reviewed(self) -> CAPStructuredSpecification:
        if self._reviewed is None:
            raise ValueError("CAP draft has not been reviewed and accepted")
        return self._reviewed

    def _validate(self) -> None:
        try:
            variants = (
                parse_mapping_lines(self.variants.toPlainText())
                if self.variants.toPlainText().strip()
                else {}
            )
            mapping = {
                key: tuple(value.strip() for value in values.split("|"))
                for key, values in variants.items()
            }
            spec = self.proposal.specification.model_copy(
                update={
                    "design_intent": self.intent.toPlainText(),
                    "canonical_attributes": parse_mapping_lines(self.attributes.toPlainText()),
                    "allowed_variants": mapping,
                    "master_prompt": self.prompt.toPlainText(),
                    "continuity_rules": tuple(
                        item.strip()
                        for item in self.rules.toPlainText().splitlines()
                        if item.strip()
                    ),
                }
            )
            spec = CAPStructuredSpecification.model_validate(spec.model_dump())
            spec.validate_category_contract()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid CAP Draft", str(exc))
            return
        self._reviewed = spec
        self.accept()
