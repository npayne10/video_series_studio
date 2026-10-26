"""Operator-reviewed DOCX CAP import into an existing Draft profile."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.document_import import (
    CAPDocumentImportError,
    CAPDocumentImportService,
    CAPDocumentProposal,
    preview_cap_docx,
)
from vscs.application.caps.service import CAPError, CAPService
from vscs.application.caps.structured_specification import (
    CAPSpecificationError,
    CAPStructuredSpecificationService,
)


def parse_mapping_lines(text: str) -> dict[str, str]:
    """Accept explicit key=value statements, refusing duplicates and empty entries."""
    mapping: dict[str, str] = {}
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        if "=" not in line:
            raise ValueError(f"Mapping line {line_number} must be key=value")
        key, value = (part.strip() for part in line.split("=", 1))
        if not key or not value or key in mapping:
            raise ValueError(f"Mapping line {line_number} has an empty or duplicate key/value")
        mapping[key] = value
    if not mapping:
        raise ValueError("Provide at least one reviewed canonical attribute")
    return mapping


class CAPDocumentImportDialog(QDialog):
    """Preview source evidence and explicitly save a reviewed Draft only."""

    def __init__(self, caps: CAPService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.caps = caps
        self.importer = CAPDocumentImportService(CAPStructuredSpecificationService(caps))
        self.proposals: tuple[CAPDocumentProposal, ...] = ()
        self.setWindowTitle("Import CAP Document — Review Draft")
        self.setMinimumSize(820, 670)

        self.source_label = QLabel("No DOCX selected")
        self.browse = QPushButton("Choose DOCX…")
        self.browse.clicked.connect(self._choose)
        self.proposal_selector = QComboBox()
        self.proposal_selector.currentIndexChanged.connect(self._show_proposal)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.target = QComboBox()
        self.attributes = QTextEdit()
        self.attributes.setPlaceholderText(
            "Explicit locked attributes, one per line, e.g. layout=Fixed console position"
        )
        self.attributes.setMaximumHeight(115)
        self.variants = QTextEdit()
        self.variants.setPlaceholderText(
            "Optional permitted variants, one per line: camera=wide|close or time=day|night"
        )
        self.variants.setMaximumHeight(95)
        self.status = QLabel(
            "Preview only. Import needs an existing Draft CAP and explicit approval."
        )
        self.status.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Source", self.source_label)
        form.addRow("", self.browse)
        form.addRow("Detected CAP", self.proposal_selector)
        form.addRow("Extracted source evidence", self.preview)
        form.addRow("Target existing Draft CAP", self.target)
        form.addRow("Reviewed immutable attributes", self.attributes)
        form.addRow("Permitted variants", self.variants)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(buttons)
        self._refresh_targets()

    def _refresh_targets(self) -> None:
        self.target.clear()
        for cap in self.caps.list():
            if cap.status.value == "draft":
                self.target.addItem(f"{cap.asset_id} — {cap.title}", cap.asset_id)

    def _choose(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select CAP Document", "", "Word Documents (*.docx)"
        )
        if not filename:
            return
        try:
            self.proposals = preview_cap_docx(Path(filename))
        except (CAPDocumentImportError, OSError, ValueError) as exc:
            QMessageBox.warning(self, "CAP Document Import", str(exc))
            return
        self.source_label.setText(
            f"{Path(filename).name} — SHA256 {self.proposals[0].source_sha256}"
        )
        self.proposal_selector.clear()
        for proposal in self.proposals:
            self.proposal_selector.addItem(
                f"{proposal.source_id} — {proposal.name} ({proposal.category.value})", proposal
            )
        self._show_proposal()

    def _show_proposal(self) -> None:
        proposal = self.proposal_selector.currentData()
        if not isinstance(proposal, CAPDocumentProposal):
            self.preview.clear()
            return
        descriptions = [f"Document identity: {proposal.source_id} — {proposal.name}"]
        descriptions.append(f"Category: {proposal.category.value}")
        descriptions.append("Source labels such as LOCKED are not VSCS approvals.")
        for heading, value in proposal.sections.items():
            descriptions.append(f"\n{heading.replace('_', ' ').title()}:\n{value}")
        if proposal.warnings:
            descriptions.append("\nWarnings: " + "; ".join(proposal.warnings))
        self.preview.setPlainText("\n".join(descriptions))
        index = self.target.findData(proposal.source_id)
        self.target.setCurrentIndex(index if index >= 0 else -1)
        self.attributes.clear()
        self.variants.clear()
        self.status.setText(
            "Review and type canonical attributes. No automatic identity remapping or approval."
        )

    def _save(self) -> None:
        proposal = self.proposal_selector.currentData()
        asset_id = self.target.currentData()
        if not isinstance(proposal, CAPDocumentProposal) or not isinstance(asset_id, str):
            QMessageBox.warning(self, "CAP Document Import", "Choose a CAP and matching Draft.")
            return
        try:
            attributes = parse_mapping_lines(self.attributes.toPlainText())
            raw_variants = (
                parse_mapping_lines(self.variants.toPlainText())
                if self.variants.toPlainText().strip()
                else {}
            )
            variants = {
                key: tuple(part.strip() for part in value.split("|"))
                for key, value in raw_variants.items()
            }
            specification = proposal.to_draft_specification(
                target_asset_id=asset_id,
                attributes=attributes,
                allowed_variants=variants,
            )
            confirmed = QMessageBox.question(
                self,
                "Confirm Draft Import",
                f"Save a non-approved specification for {asset_id}?\n\n"
                f"Category: {proposal.category.value}\nSource SHA256: {proposal.source_sha256}\n\n"
                "No asset, CAP or canonical reference will be approved.",
            )
            if confirmed != QMessageBox.StandardButton.Yes:
                return
            self.importer.apply_reviewed(
                proposal,
                target_asset_id=asset_id,
                attributes=specification.canonical_attributes,
                allowed_variants=specification.allowed_variants,
            )
        except (CAPError, CAPDocumentImportError, CAPSpecificationError, ValueError) as exc:
            QMessageBox.warning(self, "CAP Import Refused", str(exc))
            return
        self.accept()
