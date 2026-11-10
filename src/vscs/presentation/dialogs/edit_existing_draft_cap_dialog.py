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
    QPushButton,
    QVBoxLayout,
)

from vscs.application.caps.automated_draft_field import (
    DraftCAPFieldProposalCache,
    DraftCAPFieldGenerationError,
    generate_field_proposal,
    prepare_field_request,
    verify_proposal_for_review,
)
from vscs.application.caps.design_completion import DetailDecision
from vscs.application.caps.draft_cap_revision import (
    DraftCAPRevisionError,
    DraftCAPRevisionSnapshot,
    save_draft_cap_field_revision,
)
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.presentation.widgets.automation_progress import AutomationProgressRunner


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
                "Select one deferred or rejected field. VSCS generates the "
                "field proposal automatically from governed source evidence. "
                "The operator reviews, approves or rejects; no manual design "
                "entry, image generation, Canon approval or MASTER change."
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
        self.value.setReadOnly(True)
        form.addRow("Generated proposed value (read-only)", self.value)
        self.rationale = QPlainTextEdit()
        self.rationale.setObjectName("draftCAPRevisionRationale")
        self.rationale.setReadOnly(True)
        form.addRow("Generated rationale / provenance (read-only)", self.rationale)
        self.reviewer = QPlainTextEdit("Operator")
        self.reviewer.setMaximumHeight(42)
        self.reviewer.setObjectName("draftCAPRevisionReviewer")
        form.addRow("Reviewer", self.reviewer)
        layout.addLayout(form)
        self.generate_button = QPushButton("Generate / Regenerate Field Proposal (AI — Paid)")
        self.generate_button.setObjectName("generateExistingDraftFieldProposal")
        self.generate_button.clicked.connect(self._generate_proposal)
        layout.addWidget(self.generate_button)
        self.reject_button = QPushButton("Reject Generated Proposal (Keep Draft)")
        self.reject_button.setObjectName("rejectExistingDraftFieldProposal")
        self.reject_button.clicked.connect(self._reject_proposal)
        layout.addWidget(self.reject_button)
        self.proposal_status = QLabel(
            "No validated generated proposal loaded. Draft revision cannot be saved."
        )
        self.proposal_status.setWordWrap(True)
        layout.addWidget(self.proposal_status)
        self._request = None
        self._proposal = None
        self._runner = AutomationProgressRunner(self)
        self.field.currentIndexChanged.connect(self._show_original)
        self._show_original()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setText("Save Reviewed Draft Revision")
        self.save_button = save
        if self.save_button is not None:
            self.save_button.setEnabled(False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show_original(self, _index: int = 0) -> None:
        field = self.field.currentData()
        item = next((f for f in self.snapshot.review.fields if f.field == field), None)
        self.original_proposal.setPlainText("" if item is None else item.proposed_value)
        self._reject_proposal()

    def _reject_proposal(self) -> None:
        """Reject the active proposal without changing Draft or erasing audit cache."""
        self._request = None
        self._proposal = None
        self.value.clear()
        self.rationale.clear()
        if self.save_button is not None:
            self.save_button.setEnabled(False)
        self.proposal_status.setText(
            "No generated proposal selected. The current Draft remains unchanged."
        )

    def _generate_proposal(self) -> None:
        """One explicitly consented provider call; no draft save on generation."""
        field = self.field.currentData()
        if not isinstance(field, str):
            QMessageBox.warning(self, "Field Proposal", "Select a deferred field.")
            return
        provider = self.service.batch.generator.generator.provider
        projects = self.service.batch.generator.generator.assets.projects
        root = projects.project_directory
        if root is None:
            QMessageBox.warning(self, "Field Proposal", "No active VSCS project.")
            return
        cache = DraftCAPFieldProposalCache(root)
        self._reject_proposal()
        try:
            tentative = prepare_field_request(
                self.service,
                self.snapshot,
                field=field,
                provider=provider,
                generation_number=1,
            )
            generation_number = cache.next_number(tentative)
            request = prepare_field_request(
                self.service,
                self.snapshot,
                field=field,
                provider=provider,
                generation_number=generation_number,
            )
        except (RuntimeError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Field Proposal Blocked", str(exc))
            return
        choice = QMessageBox.question(
            self,
            "Authorize Paid CAP Field Proposal?",
            f"Generate ONE proposed value for {field} on {self.snapshot.asset_id}?\n"
            "This invokes the configured CAP design-expansion AI provider "
            "and may incur a charge. The provider may use one additional "
            "bounded grounding-correction request if its first response fails "
            "grounding checks. Each explicit regeneration creates a new "
            "numbered request. No field is approved or saved automatically.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            cache.reserve(request)
            self.generate_button.setEnabled(False)
            proposal = self._runner.run(
                "AI Existing Draft CAP Field Proposal",
                self.snapshot.story_id,
                lambda: generate_field_proposal(request, provider),
                may_charge=True,
            )
            cache.save(request, proposal)
            verify_proposal_for_review(self.service, request, proposal)
            self._request = request
            self._proposal = cache.load(request)
            self.value.setPlainText(self._proposal.proposed_value)
            self.rationale.setPlainText(
                f"{self._proposal.rationale}\n\n"
                f"Authority: {self._proposal.source_type}\n"
                f"Request fingerprint: {self._proposal.request_fingerprint}"
            )
            self.proposal_status.setText(
                f"Generated proposal {generation_number} ready for review. "
                "Save is a separate explicit Draft-only approval."
            )
            if self.save_button is not None:
                self.save_button.setEnabled(True)
        except (RuntimeError, ValueError, OSError) as exc:
            QMessageBox.warning(
                self,
                "Automatic Field Generation Failed",
                f"{type(exc).__name__}: {exc}\n"
                "A provider request may have occurred. Do not delete the "
                "reserved request or blindly retry; inspect the cache and "
                "provider logs before authorizing another attempt.",
            )
        finally:
            self.generate_button.setEnabled(True)

    def _save(self) -> None:
        field = self.field.currentData()
        if (
            not isinstance(field, str)
            or self._request is None
            or self._proposal is None
            or self._proposal.field != field
        ):
            QMessageBox.warning(
                self,
                "Draft Revision",
                "Generate and review a valid AI field proposal first.",
            )
            return
        try:
            verify_proposal_for_review(self.service, self._request, self._proposal)
        except (DraftCAPFieldGenerationError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Stale Field Proposal", str(exc))
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
                reviewed_value=self._proposal.proposed_value,
                rationale=(
                    "Operator accepted AI-proposed Draft design; "
                    + self._proposal.rationale
                    + "; request "
                    + self._proposal.request_fingerprint
                ),
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
