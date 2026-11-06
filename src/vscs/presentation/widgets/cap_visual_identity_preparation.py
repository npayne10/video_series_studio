"""B.5.26 read-only CAP visual identity and MASTER candidate preparation UI."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.visual_candidate_generation import VisualCandidateGenerationService
from vscs.application.caps.visual_identity_preparation import VisualIdentityPreparation
from vscs.presentation.widgets.cap_manager import CAPManagerWidget


class VisualIdentityPreparationDialog(QDialog):
    """Inspect reviewed design; local candidate rendering needs explicit consent."""

    def __init__(
        self,
        preparation: VisualIdentityPreparation,
        generation_service: VisualCandidateGenerationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.preparation = preparation
        self.generation_service = generation_service
        self.setWindowTitle(f"Prepare MASTER Candidate (Offline) — {preparation.title}")
        self.setMinimumSize(850, 680)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setObjectName("visualIdentityPreparationScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        status = (
            "BLOCKED — cannot prepare image generation"
            if preparation.blockers
            else "READY FOR LOCAL VISUAL CANDIDATE — MASTER approval separate; not approved"
        )
        self.status_label = QLabel(status)
        self.status_label.setObjectName("visualIdentityPreparationStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        form = QFormLayout()
        form.addRow("Asset", QLabel(f"{preparation.asset_id} — {preparation.category.value}"))
        form.addRow(
            "Default execution preference",
            QLabel("Local / ComfyUI; only called by the explicit Generate action"),
        )
        form.addRow(
            "Source fingerprint", QLabel(preparation.specification_fingerprint or "Missing")
        )
        form.addRow(
            "Decision audit fingerprint", QLabel(preparation.review_fingerprint or "Missing")
        )
        required = ", ".join(view.value for view in preparation.required_reference_views)
        missing = ", ".join(view.value for view in preparation.missing_reference_views)
        form.addRow("Category-required views", QLabel(required or "(none)"))
        form.addRow("Missing reference views", QLabel(missing or "(none)"))
        layout.addLayout(form)

        def readonly(title: str, value: str, object_name: str) -> QPlainTextEdit:
            label = QLabel(title)
            layout.addWidget(label)
            control = QPlainTextEdit()
            control.setObjectName(object_name)
            control.setReadOnly(True)
            control.setPlainText(value)
            layout.addWidget(control, 1)
            return control

        self.blockers_view = readonly(
            "Unresolved preparation blockers",
            "\n".join(preparation.blockers) or "(none)",
            "visualIdentityPreparationBlockers",
        )
        readonly(
            "Reviewed Draft design fields",
            "\n".join(f"{key}: {value}" for key, value in preparation.accepted_fields) or "(none)",
            "visualIdentityReviewedFields",
        )
        readonly(
            "Deferred / rejected design fields (not physical authority)",
            "\n".join(preparation.deferred_fields) or "(none)",
            "visualIdentityDeferredFields",
        )
        readonly(
            "Cross-asset continuity (context only, not a substitute for physical identity)",
            "\n".join(preparation.continuity_context) or "(none)",
            "visualIdentityContinuityContext",
        )
        readonly(
            "Related canonical asset IDs (reference-only)",
            "\n".join(preparation.dependency_asset_ids) or "(none)",
            "visualIdentityRelatedAssets",
        )
        self.prompt_view = readonly(
            "Provider-neutral proposed MASTER prompt (not an approved reference)",
            preparation.master_candidate_prompt,
            "visualIdentityMasterPrompt",
        )
        self.negative_view = readonly(
            "Negative prompt", preparation.negative_prompt, "visualIdentityNegativePrompt"
        )
        self.copy_button = QPushButton("Copy Proposed MASTER Prompt")
        self.copy_button.setObjectName("copyVisualIdentityMasterPrompt")
        self.copy_button.setEnabled(preparation.ready_for_master_candidate)
        self.copy_button.clicked.connect(self._copy_prompt)
        layout.addWidget(self.copy_button)
        self.generate_button = QPushButton("Generate One Local Image Candidate (ComfyUI)")
        self.generate_button.setObjectName("generateLocalVisualCandidate")
        self.generate_button.setEnabled(
            generation_service is not None and preparation.ready_for_master_candidate
        )
        self.generate_button.clicked.connect(self._generate_local)
        layout.addWidget(self.generate_button)
        note = QLabel(
            "Inspection and prompt preparation are offline, with zero provider calls. "
            "The separate Generate One Local Image Candidate action requires confirmation "
            "and calls XCIC/ComfyUI; it creates only a reviewable Candidate image, not a MASTER. "
            "No action grants approved Canon or Production Approval. "
            "Resolve blockers through a reviewed CAP design decision before continuing. "
            "Once an approved MASTER is locked, use Generate Production References "
            "for MASTER-conditioned derived views."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _generate_local(self) -> None:
        service = self.generation_service
        if service is None or not self.preparation.ready_for_master_candidate:
            return
        answer = QMessageBox.question(
            self,
            "Local Visual Candidate Generation",
            "Generate ONE candidate image using the configured local XCIC/ComfyUI "
            "text-to-image workflow? This uses local GPU resources but no paid "
            "OpenAI image request. Output remains Candidate only and is NOT a "
            "ChatGPT MASTER. No Canon or Production Approval will be granted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            from vscs.presentation.widgets.automation_progress import AutomationProgressRunner

            project, request = service.prepare_request(self.preparation)
            rendered = AutomationProgressRunner(self).run(
                "Local Visual Candidate",
                self.preparation.asset_id,
                lambda: service.render(self.preparation, project, request),
            )
            # Only the provider render ran in the worker. Persist references
            # on the UI thread after revalidating the CAP and review snapshot.
            reference_id = service.persist_candidate(self.preparation, project, request, rendered)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "Local Visual Candidate", str(exc))
            return
        QMessageBox.information(
            self,
            "Visual Candidate Saved",
            f"Candidate reference {reference_id} created for review. "
            "It is not approved, not a MASTER and not a production reference.",
        )
        self.accept()

    def _copy_prompt(self) -> None:
        if self.preparation.ready_for_master_candidate:
            QApplication.clipboard().setText(self.prompt_view.toPlainText())


def install_visual_identity_preparation(cap_manager: CAPManagerWidget) -> QPushButton | None:
    """Integrate B.5.26 into Canonical Profiles using existing CAP reference services."""
    references = getattr(cap_manager, "references", None)
    caps = getattr(cap_manager, "caps", None)
    if references is None or caps is None:
        return None
    service = VisualCandidateGenerationService(references)
    button = QPushButton("Prepare Visual Identity…")
    button.setToolTip(
        "Inspect reviewed CAP design offline; optionally generate a local ComfyUI Candidate"
    )
    button.setObjectName("prepareVisualIdentityOffline")

    def open_dialog() -> None:
        selected = cap_manager._selected_asset_id()
        if selected is None:
            QMessageBox.information(cap_manager, "Visual Identity", "Select a CAP first.")
            return
        try:
            preparation = service.prepare(selected)
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(cap_manager, "Visual Identity Preparation", str(exc))
            return
        if VisualIdentityPreparationDialog(preparation, service, cap_manager).exec():
            cap_manager.refresh()

    button.clicked.connect(open_dialog)
    outer = cap_manager.layout()
    if outer is None or not outer.count():
        return None
    first = outer.itemAt(0)
    if first is None:
        return None
    controls = first.layout()
    if not isinstance(controls, QHBoxLayout):
        return None
    controls.insertWidget(max(0, controls.count() - 3), button)
    return button
