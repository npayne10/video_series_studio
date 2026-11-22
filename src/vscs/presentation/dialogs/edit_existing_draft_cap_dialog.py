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
    CachedDraftCAPFieldProposal,
    DraftCAPFieldGenerationError,
    DraftCAPFieldProposalCache,
    DraftCAPFieldRequest,
    generate_field_proposal,
    prepare_field_request,
    verify_proposal_for_review,
)
from vscs.application.caps.design_completion import DetailDecision
from vscs.application.caps.draft_cap_revision import (
    DraftCAPRevisionError,
    DraftCAPRevisionSnapshot,
    prepare_story_field_revisions,
    save_draft_cap_field_revision,
)
from vscs.application.caps.provider_design_expansion import (
    CAPSingleFieldRegenerationProvider,
)
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.story_field_grounding import CAPFieldProvenance
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
        self.resize(880, 700)
        layout = QVBoxLayout(self)
        note = QLabel(
            "DRAFT-ONLY REVISION. Previously accepted fields are locked. "
            "Select one deferred or rejected field. Inspect an offline "
            "approved-Story suggestion first, or separately consent to "
            "an AI-generated design proposal. Nothing accepts a field, "
            "changes Canon or generates an image without explicit review."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
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
        self.operator_reason = QPlainTextEdit()
        self.operator_reason.setObjectName("draftCAPStoryReviewReason")
        self.operator_reason.setPlaceholderText(
            "Required for Story-backed acceptance: explain why this source applies "
            "to this asset and field. No automatic approval."
        )
        self.operator_reason.setMaximumHeight(70)
        form.addRow("Operator Story-source review reason", self.operator_reason)
        layout.addLayout(form)
        self.load_story_button = QPushButton(
            "Review Approved Story Field Suggestion (Offline — No AI Charge)"
        )
        self.load_story_button.setObjectName("loadExistingDraftStorySuggestion")
        self.load_story_button.clicked.connect(self._load_story_suggestion)
        layout.addWidget(self.load_story_button)
        self.generate_button = QPushButton("Generate / Regenerate Field Proposal (AI — Paid)")
        self.generate_button.setObjectName("generateExistingDraftFieldProposal")
        self.generate_button.clicked.connect(self._generate_proposal)
        layout.addWidget(self.generate_button)
        self.load_cached_button = QPushButton("Load Latest Cached Field Proposal (No AI Charge)")
        self.load_cached_button.setObjectName("loadCachedDraftFieldProposal")
        self.load_cached_button.clicked.connect(self._load_cached_proposal)
        layout.addWidget(self.load_cached_button)
        self.reject_button = QPushButton("Reject Generated Proposal (Keep Draft)")
        self.reject_button.setObjectName("rejectExistingDraftFieldProposal")
        self.reject_button.clicked.connect(self._reject_proposal)
        layout.addWidget(self.reject_button)
        self.proposal_status = QLabel(
            "No validated generated proposal loaded. Draft revision cannot be saved."
        )
        self.proposal_status.setWordWrap(True)
        layout.addWidget(self.proposal_status)
        self._request: DraftCAPFieldRequest | None = None
        self._proposal: CachedDraftCAPFieldProposal | None = None
        self._story_provenance: CAPFieldProvenance | None = None
        self.save_button: QPushButton | None = None
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
        self.operator_reason.clear()
        self._reject_proposal()

    def _reject_proposal(self) -> None:
        """Reject the active proposal without changing Draft or erasing audit cache."""
        self._request = None
        self._proposal = None
        self._story_provenance = None
        self.value.clear()
        self.rationale.clear()
        if self.save_button is not None:
            self.save_button.setEnabled(False)
        self.proposal_status.setText(
            "No generated proposal selected. The current Draft remains unchanged."
        )

    def _load_story_suggestion(self) -> None:
        """Read current approved Story only; never touch the provider or CAP cache."""
        field = self.field.currentData()
        if not isinstance(field, str):
            return
        self._reject_proposal()
        try:
            candidates = prepare_story_field_revisions(self.service, self.snapshot)
            suggestion = next((item for item in candidates if item.field == field), None)
            if suggestion is None:
                self.proposal_status.setText(
                    "No approved-Story candidate for this deferred field. "
                    "Keep it unresolved unless separately reviewed design evidence exists. "
                    "No AI request was made."
                )
                return
            self._story_provenance = suggestion
            self.value.setPlainText(suggestion.value)
            self.rationale.setPlainText(
                "APPROVED STORY SOURCE — candidate, not CAP/Canon approval.\n"
                f"Source: {suggestion.source_record_id}.{suggestion.source_field}\n"
                f"Source SHA: {suggestion.source_fingerprint}\n"
                f"Context fingerprint: {suggestion.context_fingerprint}\n"
                f"Source excerpt: {suggestion.excerpt}\n"
                + (
                    f"SHOT-ONLY ({suggestion.shot_authority}): {suggestion.shot_excerpt}\n"
                    if suggestion.shot_authority
                    else ""
                )
                + "Confirm asset scope and record your reason before Save."
            )
            self.proposal_status.setText(
                f"Offline Story source loaded for {field}. "
                f"{len(candidates)} deferred/rejected field(s) have source suggestions. "
                "Save remains a separate confirmed Draft-only operation."
            )
            if self.save_button is not None:
                self.save_button.setEnabled(True)
        except (RuntimeError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Story Field Suggestion Unavailable", str(exc))

    def _load_cached_proposal(self) -> None:
        """Reopen the last complete AI result; do not send a provider request."""
        field = self.field.currentData()
        if not isinstance(field, str):
            return
        self._reject_proposal()
        try:
            root = self.service.batch.generator.generator.assets.projects.project_directory
            if root is None:
                raise DraftCAPFieldGenerationError("No active project")
            provider = self.service.batch.generator.generator.provider
            cache = DraftCAPFieldProposalCache(root)
            initial = prepare_field_request(
                self.service,
                self.snapshot,
                field=field,
                provider=provider,
                generation_number=1,
            )
            last = cache.latest_completed_number(initial)
            if last is None:
                raise DraftCAPFieldGenerationError("No completed cached field proposal")
            request = prepare_field_request(
                self.service,
                self.snapshot,
                field=field,
                provider=provider,
                generation_number=last,
            )
            proposal = cache.load(request)
            verify_proposal_for_review(self.service, request, proposal)
            self._request = request
            self._proposal = proposal
            self.value.setPlainText(proposal.proposed_value)
            self.rationale.setPlainText(
                f"{proposal.rationale}\n\n"
                f"Authority: {proposal.source_type}\n"
                f"Request fingerprint: {proposal.request_fingerprint}"
            )
            self.proposal_status.setText(
                f"Cached generated proposal {last} restored without provider charge."
            )
            if self.save_button is not None:
                self.save_button.setEnabled(True)
        except (RuntimeError, ValueError, OSError) as exc:
            QMessageBox.warning(self, "Cached Field Proposal Unavailable", str(exc))

    def _generate_proposal(self) -> None:
        """One explicitly consented provider call; no draft save on generation."""
        field = self.field.currentData()
        if not isinstance(field, str):
            QMessageBox.warning(self, "Field Proposal", "Select a deferred field.")
            return
        provider = self.service.batch.generator.generator.provider
        if not isinstance(provider, CAPSingleFieldRegenerationProvider):
            QMessageBox.warning(
                self,
                "Unsupported CAP Provider",
                "The configured provider cannot generate a scoped Draft field. "
                "No paid request has been submitted.",
            )
            return
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
            "This invokes the configured CAP field-regeneration AI provider "
            "and may incur a charge. It submits ONE structured provider request; "
            "invalid or ungrounded output fails closed without a silent retry. "
            "Each explicit regeneration creates a new numbered paid request. "
            "No field is approved or saved automatically.",
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
        story = self._story_provenance
        if (
            not isinstance(field, str)
            or (
                story is None
                and (
                    self._request is None or self._proposal is None or self._proposal.field != field
                )
            )
            or (story is not None and story.field != field)
        ):
            QMessageBox.warning(
                self,
                "Draft Revision",
                "Review a valid offline Story suggestion or a generated AI proposal first.",
            )
            return
        if story is not None:
            reason = self.operator_reason.toPlainText().strip()
            if not reason:
                QMessageBox.warning(
                    self,
                    "Story Source Review Reason Required",
                    "Record why the approved Story excerpt describes this asset's physical field.",
                )
                return
            try:
                current = prepare_story_field_revisions(self.service, self.snapshot)
                if story not in current:
                    raise DraftCAPRevisionError("Story source or Draft review changed")
            except (DraftCAPRevisionError, RuntimeError, ValueError, OSError) as exc:
                QMessageBox.warning(self, "Stale Story Field Suggestion", str(exc))
                return
            reviewed_value = story.value
            rationale = "Operator verified approved Story source; " + reason
        else:
            try:
                root = self.service.batch.generator.generator.assets.projects.project_directory
                if root is None:
                    raise DraftCAPFieldGenerationError("No active project for proposal audit")
                if self._request is None or self._proposal is None:
                    raise DraftCAPFieldGenerationError("No approved field proposal selected")
                verified = DraftCAPFieldProposalCache(root).load(self._request)
                if verified != self._proposal:
                    raise DraftCAPFieldGenerationError("Generated proposal changed before approval")
                verify_proposal_for_review(self.service, self._request, verified)
            except (DraftCAPFieldGenerationError, RuntimeError, ValueError) as exc:
                QMessageBox.warning(self, "Stale Field Proposal", str(exc))
                return
            reviewed_value = self._proposal.proposed_value
            rationale = (
                "Operator accepted AI-proposed Draft design; "
                + self._proposal.rationale
                + "; request "
                + self._proposal.request_fingerprint
            )
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
                reviewed_value=reviewed_value,
                rationale=rationale,
                reviewer=self.reviewer.toPlainText(),
                **({"story_provenance": story} if story is not None else {}),
            )
        except (DraftCAPRevisionError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Draft Revision Blocked", str(exc))
            return
        QMessageBox.information(
            self,
            "Reviewed Draft Revision Saved",
            f"{self.snapshot.asset_id}: {field} saved as reviewed Draft. "
            "Other decisions preserved. Reopen Visual Identity to check readiness. "
            "No image was generated or Canon approved.",
        )
        self.accept()
