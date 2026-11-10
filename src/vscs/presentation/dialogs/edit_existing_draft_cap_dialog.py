"""Review a single deferred/rejected field of an existing, governed Draft CAP."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from vscs.application.caps.design_completion import DetailDecision
from vscs.application.caps.draft_cap_revision import (
    DraftCAPRevisionError,
    DraftCAPRevisionSnapshot,
    save_draft_cap_field_revision,
)
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService


class EditExistingDraftCAPDialog(QDialog):
    """Never generate a CAP proposal or permit edits to accepted fields."""

    def __init__(
        self,
        service: StoryCAPBatchReviewService,
        snapshot: DraftCAPRevisionSnapshot,
        parent: QDialog | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.snapshot = snapshot
        self.setWindowTitle(f"Edit Existing Draft CAP — {snapshot.asset_id}")
        self.setObjectName("editExistingDraftCAPDialog")
        self.resize(840, 550)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "DRAFT-ONLY REVISION. Previously accepted fields are locked. "
                "Select one deferred or rejected field, enter a deliberate "
                "reviewed design value and explain its source or rationale. "
                "No AI call, image generation, Canon approval or MASTER change."
            )
        )
        fields = snapshot.review.fields
        retained = "\n".join(
            f"{item.field}: {item.final_value}"
            for item in fields
            if item.decision in {DetailDecision.ACCEPT, DetailDecision.EDIT}
        )
        layout.addWidget(QLabel("Preserved accepted fields (read-only)"))
        self.accepted_view = QPlainTextEdit(retained)
        self.accepted_view.setObjectName("draftCAPRevisionAcceptedFields")
        self.accepted_view.setReadOnly(True)
        layout.addWidget(self.accepted_view)
        form = QFormLayout()
        self.field = QComboBox()
        self.field.setObjectName("draftCAPRevisionField")
        for item in fields:
            if item.decision in {DetailDecision.DEFER, DetailDecision.REJECT}:
                self.field.addItem(f"{item.field} ({item.decision.value})", item.field)
        form.addRow("Revisit field", self.field)
        self.original_proposal = QPlainTextEdit()
        self.original_proposal.setReadOnly(True)
        self.original_proposal.setObjectName("draftCAPOriginalProposal")
        form.addRow("Original proposal (advisory)", self.original_proposal)
        self.value = QPlainTextEdit()
        self.value.setObjectName("draftCAPRevisionValue")
        form.addRow("Reviewed design value", self.value)
        self.rationale = QPlainTextEdit()
        self.rationale.setObjectName("draftCAPRevisionRationale")
        form.addRow("Operator rationale / evidence", self.rationale)
        self.reviewer = QPlainTextEdit("Operator")
        self.reviewer.setMaximumHeight(42)
        self.reviewer.setObjectName("draftCAPRevisionReviewer")
        form.addRow("Reviewer", self.reviewer)
        layout.addLayout(form)
        self.field.currentIndexChanged.connect(self._show_original)
        self._show_original()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setText("Save Reviewed Draft Revision")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show_original(self, _index: int = 0) -> None:
        field = self.field.currentData()
        item = next((f for f in self.snapshot.review.fields if f.field == field), None)
        self.original_proposal.setPlainText("" if item is None else item.proposed_value)

    def _save(self) -> None:
        field = self.field.currentData()
        if not isinstance(field, str):
            QMessageBox.warning(self, "Draft Revision", "Select one deferred field.")
            return
        choice = QMessageBox.question(
            self,
            "Confirm Governed Draft Revision",
            f"Update ONLY {field} for {self.snapshot.asset_id}?\n"
            "All prior accepted fields remain unchanged; the new detail "
            "is an operator-reviewed Draft design decision, NOT Story Canon. "
            "The current Story, context and Draft database record will be "
            "revalidated immediately before saving. No AI or GPU request.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            save_draft_cap_field_revision(
                self.service,
                self.snapshot,
                field=field,
                reviewed_value=self.value.toPlainText(),
                rationale=self.rationale.toPlainText(),
                reviewer=self.reviewer.toPlainText(),
            )
        except (DraftCAPRevisionError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Draft Revision Blocked", str(exc))
            return
        QMessageBox.information(
            self,
            "Reviewed Draft Revision Saved",
            f"{self.snapshot.asset_id}: {field} saved as reviewed Draft. "
            "Other decisions preserved. Reopen Visual Identity to check readiness. "
            "Nothing was approved or generated.",
        )
        self.accept()
