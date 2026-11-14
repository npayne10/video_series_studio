"""Integrated B.5.26 CAP image Candidate review: CIEE + consented SIEE."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.general_visual_correction_triage import (
    candidate_visual_triage,
)
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
    prepare_governed_correction_proposal,
)
from vscs.application.caps.human_reviewed_mask_evidence import (
    ReviewedMaskEvidence,
    inspect_reviewed_mask,
    prepare_reviewed_mask,
    preview_mask_bounds,
    save_reviewed_mask_once,
)
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.saved_candidate_review import reopen_saved_candidate_review
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    SpatialEvidenceReview,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import (
    CandidateQualityResult,
    CandidateQualityReviewService,
)
from vscs.application.caps.visual_candidate_regeneration import CandidateRegenerationService
from vscs.infrastructure.ai import AICredentialStore
from vscs.infrastructure.ai.openai_semantic_evaluator import OpenAISemanticImageEvaluator
from vscs.infrastructure.configuration import ConfigurationService
from vscs.presentation.dialogs.human_correction_disposition_dialog import (
    HumanCorrectionDispositionDialog,
)
from vscs.presentation.dialogs.source_image_roi_dialog import SourceImageRoiDialog
from vscs.presentation.widgets import cap_manager
from vscs.presentation.widgets.automation_progress import AutomationProgressRunner
from vscs.presentation.widgets.cap_visual_candidate_regeneration import (
    ControlledCandidateRegenerationDialog,
)


class CandidateQualityReportDialog(QDialog):
    """Non-authoritative, read-only report for a single evaluated Candidate."""

    def __init__(
        self,
        report: CandidateQualityResult,
        relative_report_path: str,
        parent: QWidget | None = None,
        references: CanonicalReferenceService | None = None,
    ) -> None:
        super().__init__(parent)
        self.references = references
        self.setWindowTitle("Visual Candidate Quality Review — Advisory")
        self.setObjectName("visualCandidateQualityReport")
        self.resize(900, 660)
        layout = QVBoxLayout(self)
        status = QLabel(
            f"Decision: {report.decision} — "
            f"Technical: {report.technical.overall_score}/100 — "
            f"Semantic: {report.semantic.overall_score if report.semantic else 'not run'}"
        )
        status.setObjectName("visualCandidateQualityDecision")
        status.setWordWrap(True)
        layout.addWidget(status)
        details = QPlainTextEdit()
        details.setObjectName("visualCandidateQualityDetails")
        details.setReadOnly(True)
        sections = [
            "NON-AUTHORITATIVE: No image, MASTER, Canon or Production Approval.",
            f"Asset: {report.snapshot.asset_id}",
            f"Candidate reference: {report.snapshot.reference_id}",
            f"Image SHA256: {report.snapshot.image_sha256}",
            "Accepted Draft design:",
            *[f"  {name}: {value}" for name, value in report.snapshot.accepted_fields],
            "Deferred / not-established design: "
            + (", ".join(report.snapshot.deferred_fields) or "(none)"),
            "Continuity relationships (advisory, not implied geometry):",
            *[f"  {item}" for item in report.snapshot.continuity],
            "TECHNICAL CHECKS",
            *[
                f"  {item.name}: {item.score}/100 — {item.summary}"
                for item in report.technical.metrics
            ],
        ]
        if report.semantic is None:
            sections.append(
                "SEMANTIC IMAGE ANALYSIS NOT RUN. "
                "Offline technical tests cannot establish whether a console, door, "
                "blue display or other physical feature is actually present."
            )
        else:
            sections.extend(
                (
                    f"SEMANTIC FINDINGS ({report.semantic.provider}, "
                    f"{report.semantic.model}) — advisory",
                    *[
                        f"  {item.name}: {item.score}/100 "
                        f"{'[BLOCKING]' if item.blocking else ''} — "
                        f"{item.summary}"
                        for item in report.semantic.metrics
                    ],
                    "Visible features:",
                    *[f"  {item}" for item in report.semantic.detected_features],
                    "Violations:",
                    *[f"  {item}" for item in report.semantic.violations],
                )
            )
        if report.snapshot.correction_attempt is not None:
            previous = report.snapshot
            sections.extend(
                (
                    "B.5.26D CORRECTIVE GENERATION COMPARISON",
                    f"Correction attempt: {previous.correction_attempt}",
                    f"Source Candidate: {previous.parent_reference_id}",
                    (
                        "Technical: "
                        f"{previous.previous_technical_score} -> "
                        f"{report.technical.overall_score}"
                    ),
                    (
                        "Semantic: "
                        f"{previous.previous_semantic_score} -> "
                        f"{report.semantic.overall_score if report.semantic else 'NOT RUN'}"
                    ),
                    (
                        "Design consistency: "
                        f"{previous.previous_design_consistency_score} -> "
                        + (
                            str(report.current_design_consistency_score)
                            if report.semantic is not None
                            else "NOT RUN"
                        )
                    ),
                    "Improvement in technical score does not establish visual "
                    "continuity. A new consented semantic evaluation is required.",
                )
            )
        sections.extend(
            (
                "SUGGESTED CORRECTIONS / HUMAN CHECKS",
                *[f"  {item}" for item in report.recommendations],
                f"Report stored in: {relative_report_path}",
                "Use the existing gallery's Archive action for an unsuitable Candidate. "
                "If a failed semantic report recommends regeneration, use "
                "Prepare Corrected Local Candidate to review a grounded correction. "
                "An evaluator PASS never triggers Approve or Set as Primary.",
            )
        )
        details.setPlainText("\n".join(sections))
        layout.addWidget(details, 1)
        self.correction_button = QPushButton("Prepare Corrected Local Candidate…")
        self.correction_button.setObjectName("prepareControlledCandidateRegeneration")
        self.correction_button.setEnabled(
            references is not None
            and report.semantic is not None
            and report.semantic.decision.value == "regenerate"
            and report.decision == "REGENERATE_RECOMMENDED"
        )
        self.correction_button.clicked.connect(
            lambda: self._prepare_correction(report, relative_report_path)
        )
        layout.addWidget(self.correction_button)
        self.human_disposition_button = QPushButton(
            "Record Human Correction Finding (No Generation)"
        )
        self.human_disposition_button.setObjectName("recordHumanCandidateCorrection")
        self.human_disposition_button.setEnabled(
            references is not None
            and report.semantic is not None
            and report.decision == "HUMAN_REVIEW_REQUIRED"
            and bool(report.snapshot.accepted_fields)
        )
        self.human_disposition_button.clicked.connect(
            lambda: self._record_human_disposition(report, relative_report_path)
        )
        layout.addWidget(self.human_disposition_button)
        self.general_triage_button = QPushButton(
            "F5.4.2 Review General Visual Correction (No Generation)…"
        )
        self.general_triage_button.setObjectName("generalVisualCorrectionTriage")
        self.general_triage_button.setEnabled(
            report.semantic is not None and bool(report.snapshot.accepted_fields)
        )
        self.general_triage_button.clicked.connect(
            lambda: self._open_general_correction_triage(report)
        )
        layout.addWidget(self.general_triage_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_general_correction_triage(self, report: CandidateQualityResult) -> None:
        """Review a typed defect in the current saved result; do not persist or generate."""
        dialog = QDialog(self)
        dialog.setWindowTitle("F5.4.2 — General Visual Correction Review (Advisory)")
        dialog.setObjectName("generalVisualCorrectionTriageDialog")
        dialog.resize(900, 760)
        outer = QVBoxLayout(dialog)
        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setObjectName("generalVisualCorrectionScrollableForm")
        outer.addWidget(scroll)
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        scroll.setWidget(content)

        try:
            baseline = candidate_visual_triage(report)
        except GeometryCorrectionError as exc:
            QMessageBox.warning(self, "General Correction Triage Blocked", str(exc))
            return

        fields = QComboBox(dialog)
        fields.setObjectName("generalTriageReviewedField")
        for check in baseline.mandatory_checks:
            fields.addItem(check.field, check.field)
        layout.addWidget(QLabel("Reviewed Draft CAP field (operator selection):"))
        layout.addWidget(fields)

        defect = QComboBox(dialog)
        defect.setObjectName("generalTriageDefectType")
        for kind in GeometryDefect:
            defect.addItem(kind.value.replace("_", " "), kind.value)
        layout.addWidget(QLabel("Observed defect type (operator selection):"))
        layout.addWidget(defect)

        reason = QPlainTextEdit(dialog)
        reason.setObjectName("generalTriageObservedFailure")
        reason.setPlaceholderText(
            "Describe what is visibly wrong with the chosen reviewed field. "
            "Do not invent or change accepted CAP requirements."
        )
        reason.setMaximumBlockCount(40)
        layout.addWidget(QLabel("Observed discrepancy (required for classification):"))
        layout.addWidget(reason)

        details = QPlainTextEdit(dialog)
        details.setObjectName("generalTriageAssessment")
        details.setReadOnly(True)
        details.setMinimumHeight(230)
        details.setPlainText(baseline.describe())
        layout.addWidget(details, 1)

        classify = QPushButton("Classify and Inspect (No Generation)", dialog)
        classify.setObjectName("generalTriageClassify")
        layout.addWidget(classify)

        def inspect() -> None:
            try:
                assessment = candidate_visual_triage(
                    report,
                    selected_field=str(fields.currentData()),
                    selected_defect=GeometryDefect(str(defect.currentData())),
                    observed_failure=reason.toPlainText(),
                )
            except (GeometryCorrectionError, ValueError) as exc:
                QMessageBox.warning(dialog, "Correction Assessment Blocked", str(exc))
                return
            details.setPlainText(assessment.describe())

        classify.clicked.connect(inspect)

        layout.addWidget(QLabel("Stage B: operator field status and optional spatial proposal:"))
        evidence_status = QComboBox(dialog)
        evidence_status.setObjectName("spatialEvidenceStatus")
        for state in VisualEvidenceStatus:
            evidence_status.addItem(state.value.replace("_", " "), state.value)
        layout.addWidget(evidence_status)
        roi = QLineEdit(dialog)
        roi.setObjectName("spatialEvidenceROI")
        roi.setReadOnly(True)
        roi.setPlaceholderText("No ROI selected — use the source-image rectangle selector")
        layout.addWidget(roi)
        select_roi = QPushButton("Select ROI on Source Image (No Generation)", dialog)
        select_roi.setObjectName("stageC2SelectSourceROI")
        layout.addWidget(select_roi)
        propose = QPushButton("Inspect Stage B Evidence / ROI (No Generation)", dialog)
        propose.setObjectName("spatialEvidenceInspect")
        layout.addWidget(propose)

        current_evidence: SpatialEvidenceReview | None = None
        current_proposal: GovernedCorrectionProposal | None = None
        current_mask: ReviewedMaskEvidence | None = None
        mask_previewed = False
        selected_region: NormalizedRegion | None = None
        review_progress = QLabel("0 of " + str(len(baseline.mandatory_checks)) + " fields reviewed")
        review_progress.setObjectName("spatialEvidenceReviewProgress")
        layout.addWidget(review_progress)

        def restore_selected_field() -> None:
            nonlocal selected_region
            roi_confirmation.setChecked(False)
            selected_region = None
            roi.clear()
            if current_evidence is None:
                evidence_status.setCurrentIndex(0)
                reason.clear()
                return
            name = str(fields.currentData())
            item = next((i for i in current_evidence.reviewed_fields if i.field == name), None)
            if item is None:
                return
            evidence_status.setCurrentIndex(evidence_status.findData(item.status.value))
            reason.setPlainText(item.observation)
            if item.defect is not None:
                defect.setCurrentIndex(defect.findData(item.defect.value))
            selected_region = item.proposed_region
            if selected_region is not None:
                area = selected_region
                roi.setText(f"{area.x:.8f},{area.y:.8f},{area.width:.8f},{area.height:.8f}")
            else:
                roi.clear()

        fields.currentIndexChanged.connect(lambda _index: restore_selected_field())

        def open_source_roi_selector() -> None:
            nonlocal selected_region, current_proposal, current_mask, mask_previewed
            if str(evidence_status.currentData()) != VisualEvidenceStatus.FAILED.value:
                QMessageBox.warning(
                    dialog, "ROI Selection Blocked", "Select FAILED for the reviewed field first."
                )
                return
            try:
                selector = SourceImageRoiDialog(
                    source_path=report.snapshot.image_path,
                    expected_source_sha256=report.snapshot.image_sha256,
                    parent=dialog,
                )
                if selector.exec() != QDialog.DialogCode.Accepted:
                    return
                if selector.selected_region is None:
                    raise GeometryCorrectionError("Source-image ROI was not selected")
            except (OSError, GeometryCorrectionError) as exc:
                QMessageBox.warning(dialog, "ROI Selection Blocked", str(exc))
                return
            selected_region = selector.selected_region
            area = selected_region
            roi.setText(f"{area.x:.8f},{area.y:.8f},{area.width:.8f},{area.height:.8f}")
            current_proposal = None
            current_mask = None
            mask_previewed = False
            roi_confirmation.setChecked(False)
            mask_confirmation.setChecked(False)
            details.setPlainText(
                "New ROI selected from the original Candidate image. "
                "Press Inspect Stage B Evidence / ROI to record it. "
                "This does not create a mask or authorize generation."
            )

        select_roi.clicked.connect(open_source_roi_selector)

        def inspect_spatial_evidence() -> None:
            nonlocal current_evidence, current_proposal, current_mask, mask_previewed
            try:
                state = VisualEvidenceStatus(str(evidence_status.currentData()))
                region = selected_region if state is VisualEvidenceStatus.FAILED else None
                evidence = propose_spatial_evidence(
                    baseline,
                    field=str(fields.currentData()),
                    status=state,
                    observation=reason.toPlainText(),
                    defect=(
                        GeometryDefect(str(defect.currentData()))
                        if state is VisualEvidenceStatus.FAILED
                        else None
                    ),
                    region=region,
                    expected_source_sha256=report.snapshot.image_sha256,
                    previous=current_evidence,
                )
            except (GeometryCorrectionError, ValueError) as exc:
                QMessageBox.warning(dialog, "Stage B Evidence Blocked", str(exc))
                return
            current_evidence = evidence
            current_proposal = None
            current_mask = None
            mask_previewed = False
            roi_confirmation.setChecked(False)
            mask_confirmation.setChecked(False)
            reviewed = len(evidence.reviewed_fields) - evidence.outstanding_fields
            review_progress.setText(
                f"{reviewed} of {len(evidence.reviewed_fields)} fields reviewed"
            )
            details.setPlainText(evidence.describe())

        propose.clicked.connect(inspect_spatial_evidence)

        roi_confirmation = QCheckBox(
            "I inspected the ROI against the source image (not a mask or execution consent).",
            dialog,
        )
        roi_confirmation.setObjectName("stageCReviewedROIConfirmation")
        layout.addWidget(roi_confirmation)
        stage_c = QPushButton("Inspect Stage C Governed Handoff (No Generation)", dialog)
        stage_c.setObjectName("stageCGovernedCorrectionInspect")
        layout.addWidget(stage_c)

        def inspect_governed_handoff() -> None:
            nonlocal current_proposal, current_mask, mask_previewed
            if current_evidence is None:
                QMessageBox.warning(
                    dialog, "Stage C Handoff Blocked", "Complete Stage B field review first."
                )
                return
            try:
                proposal = prepare_governed_correction_proposal(
                    current_evidence,
                    target_field=str(fields.currentData()),
                    expected_source_sha256=report.snapshot.image_sha256,
                    reviewer_confirmed_roi=roi_confirmation.isChecked(),
                )
            except GeometryCorrectionError as exc:
                QMessageBox.warning(dialog, "Stage C Handoff Blocked", str(exc))
                return
            current_proposal = proposal
            current_mask = None
            mask_previewed = False
            details.setPlainText(proposal.describe())

        stage_c.clicked.connect(inspect_governed_handoff)

        preview_button = QPushButton("Preview Stage C2 Editable Region (No Generation)", dialog)
        preview_button.setObjectName("stageC2PreviewMask")
        layout.addWidget(preview_button)

        mask_confirmation = QCheckBox(
            "I reviewed the mask preview against the source image; the white area is editable.",
            dialog,
        )
        mask_confirmation.setObjectName("stageC2MaskReviewConfirmation")
        layout.addWidget(mask_confirmation)
        inspect_mask_button = QPushButton("Inspect C2 Mask Evidence (No Generation)", dialog)
        inspect_mask_button.setObjectName("stageC2InspectMaskEvidence")
        layout.addWidget(inspect_mask_button)
        save_mask_button = QPushButton("Save C2 Mask Evidence (No Generation)", dialog)
        save_mask_button.setObjectName("stageC2SaveMaskEvidence")
        layout.addWidget(save_mask_button)

        def preview_mask() -> None:
            nonlocal mask_previewed, current_mask
            if current_proposal is None:
                QMessageBox.warning(dialog, "Stage C2 Blocked", "Inspect Stage C1 handoff first.")
                return
            try:
                _size, bounds = preview_mask_bounds(
                    current_proposal, source_path=report.snapshot.image_path
                )
                preview = QPixmap(str(report.snapshot.image_path))
                if preview.isNull():
                    raise GeometryCorrectionError("Source preview could not be loaded")
            except (GeometryCorrectionError, OSError) as exc:
                QMessageBox.warning(dialog, "Stage C2 Preview Blocked", str(exc))
                return
            left, top, right, bottom = bounds
            painter = QPainter(preview)
            try:
                painter.fillRect(left, top, right - left, bottom - top, QColor(255, 0, 0, 75))
                painter.setPen(QPen(QColor(255, 40, 40), 3))
                painter.drawRect(left, top, right - left - 1, bottom - top - 1)
            finally:
                painter.end()
            window = QDialog(dialog)
            window.setWindowTitle("C2 Source-bound editable area preview (red overlay)")
            window.setObjectName("stageC2MaskPreviewDialog")
            window_layout = QVBoxLayout(window)
            label = QLabel(window)
            label.setPixmap(
                preview.scaled(
                    760,
                    520,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            window_layout.addWidget(label)
            window_layout.addWidget(
                QLabel("Red overlay = proposed editable pixels; all other pixels protected.")
            )
            mask_previewed = True
            current_mask = None
            mask_confirmation.setChecked(False)
            window.exec()

        preview_button.clicked.connect(preview_mask)

        def inspect_mask() -> None:
            nonlocal current_mask
            if current_proposal is None or not mask_previewed:
                QMessageBox.warning(
                    dialog, "Stage C2 Blocked", "Preview the source-bound mask first."
                )
                return
            try:
                evidence = prepare_reviewed_mask(
                    current_proposal,
                    source_path=report.snapshot.image_path,
                    reviewer_confirmed_mask=mask_confirmation.isChecked(),
                )
                inspect_reviewed_mask(
                    evidence,
                    proposal=current_proposal,
                    source_path=report.snapshot.image_path,
                )
            except (GeometryCorrectionError, OSError) as exc:
                QMessageBox.warning(dialog, "Stage C2 Evidence Blocked", str(exc))
                return
            current_mask = evidence
            details.setPlainText(evidence.describe())

        inspect_mask_button.clicked.connect(inspect_mask)

        def save_mask() -> None:
            if current_mask is None or current_proposal is None:
                QMessageBox.warning(
                    dialog, "Stage C2 Save Blocked", "Inspect reviewed mask evidence first."
                )
                return
            if not mask_confirmation.isChecked():
                QMessageBox.warning(
                    dialog, "Stage C2 Save Blocked", "Mask review confirmation is required."
                )
                return
            directory = (
                report.snapshot.project_root
                / "Canonical Assets"
                / report.snapshot.asset_id
                / ".metadata"
                / "spatial_masks"
            )
            try:
                if not directory.exists():
                    if not directory.parent.is_dir() or directory.parent.is_symlink():
                        raise GeometryCorrectionError("Canonical metadata directory unavailable")
                    directory.mkdir()
                path = save_reviewed_mask_once(
                    current_mask,
                    proposal=current_proposal,
                    source_path=report.snapshot.image_path,
                    destination_directory=directory,
                )
            except (GeometryCorrectionError, OSError) as exc:
                QMessageBox.warning(dialog, "Stage C2 Save Blocked", str(exc))
                return
            details.setPlainText(
                current_mask.describe()
                + f"\\nSaved exclusive non-authoritative mask evidence: {path}"
            )

        save_mask_button.clicked.connect(save_mask)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()

    def _record_human_disposition(
        self, report: CandidateQualityResult, relative_report_path: str
    ) -> None:
        if self.references is None:
            return
        source = report.snapshot.project_root / relative_report_path
        editor = HumanCorrectionDispositionDialog(report.snapshot, source, self)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        self.human_disposition_button.setEnabled(False)
        QMessageBox.information(
            self,
            "Human Review Decision Saved",
            "A separate, immutable reviewer finding was recorded. "
            "The original semantic report remains unchanged. "
            "Use Correct From Saved Review to inspect the governed correction "
            "attempt; no image has been generated.",
        )

    def _prepare_correction(
        self, report: CandidateQualityResult, relative_report_path: str
    ) -> None:
        if self.references is None:
            return
        path = report.snapshot.project_root / relative_report_path
        try:
            dialog = ControlledCandidateRegenerationDialog(
                self.references,
                report.snapshot.asset_id,
                report.snapshot.reference_id,
                path,
                self,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(self, "Corrective Candidate Blocked", str(exc))
            return
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.accept()


def _review_selected(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    selected = None if gallery is None else gallery.selected_reference()
    profile = getattr(dialog, "profile", None)
    refs = getattr(dialog, "reference_service", None)
    if selected is None or profile is None or refs is None:
        QMessageBox.information(dialog, "Candidate Quality", "Select a local Candidate first.")
        return
    service = CandidateQualityReviewService(refs)
    try:
        snapshot = service.snapshot(profile.asset_id, selected.id)
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.warning(dialog, "Candidate Quality", str(exc))
        return
    choice = QMessageBox.question(
        dialog,
        "Candidate Quality Review",
        "Run offline technical checks only (No), or include ONE billable "
        "OpenAI vision-based semantic evaluation (Yes)?\n\n"
        "Semantic review can assess visible CAP design adherence, invented "
        "features and continuity, but is advisory and does not approve images. "
        "Exact cost is unavailable. Cancel performs no operation.",
        QMessageBox.StandardButton.Yes
        | QMessageBox.StandardButton.No
        | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    if choice == QMessageBox.StandardButton.Cancel:
        return
    provider = None
    if choice == QMessageBox.StandardButton.Yes:
        try:
            config = ConfigurationService()
            config.load()
            key = AICredentialStore().get_openai_api_key()
            if not key:
                raise ValueError("OpenAI API key is not configured in VSCS Settings")
            provider = OpenAISemanticImageEvaluator(
                api_key=key, model=config.settings.ai.openai_model
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(dialog, "Candidate Quality", str(exc))
            return
    try:
        result = AutomationProgressRunner(dialog).run(
            "Candidate Quality Review",
            snapshot.asset_id,
            lambda: service.evaluate(snapshot, semantic_provider=provider),
            may_charge=provider is not None,
        )
        report_path = service.save(result)
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.critical(dialog, "Candidate Quality", str(exc))
        return
    report_dialog = CandidateQualityReportDialog(
        result, str(report_path.relative_to(snapshot.project_root)), dialog, refs
    )
    if report_dialog.exec() == QDialog.DialogCode.Accepted:
        dialog._refresh_references()


def _reopen_saved_candidate_review(dialog: Any) -> None:
    """Open saved semantic evidence directly without any provider request."""
    gallery = getattr(dialog, "reference_gallery", None)
    selected = None if gallery is None else gallery.selected_reference()
    profile = getattr(dialog, "profile", None)
    refs = getattr(dialog, "reference_service", None)
    if selected is None or profile is None or refs is None:
        QMessageBox.information(dialog, "Saved Candidate Review", "Select a Candidate first.")
        return
    try:
        service = CandidateQualityReviewService(refs)
        result, path = reopen_saved_candidate_review(service, profile.asset_id, selected.id)
        relative = str(path.relative_to(result.snapshot.project_root))
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.warning(dialog, "Saved Candidate Review Unavailable", str(exc))
        return
    window = CandidateQualityReportDialog(result, relative, dialog, refs)
    if window.exec() == QDialog.DialogCode.Accepted:
        dialog._refresh_references()


def _correct_from_saved_report(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    selected = None if gallery is None else gallery.selected_reference()
    profile = getattr(dialog, "profile", None)
    refs = getattr(dialog, "reference_service", None)
    if selected is None or profile is None or refs is None:
        QMessageBox.information(dialog, "Controlled Correction", "Select a local Candidate.")
        return
    try:
        service = CandidateRegenerationService(refs)
        path = service.latest_semantic_report(profile.asset_id, selected.id)
        window = ControlledCandidateRegenerationDialog(
            refs, profile.asset_id, selected.id, path, dialog
        )
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.warning(dialog, "Controlled Correction Unavailable", str(exc))
        return
    if window.exec() == QDialog.DialogCode.Accepted:
        dialog._refresh_references()


def _record_human_from_saved_report(dialog: Any) -> None:
    """Use previously billed semantic evidence; no new AI provider call."""
    gallery = getattr(dialog, "reference_gallery", None)
    selected = None if gallery is None else gallery.selected_reference()
    profile = getattr(dialog, "profile", None)
    refs = getattr(dialog, "reference_service", None)
    if selected is None or profile is None or refs is None:
        QMessageBox.information(dialog, "Human Review", "Select a local Candidate first.")
        return
    try:
        service = CandidateRegenerationService(refs)
        saved_report = service.latest_semantic_report(profile.asset_id, selected.id)
        snapshot = service.quality.snapshot(profile.asset_id, selected.id)
        editor = HumanCorrectionDispositionDialog(snapshot, saved_report, dialog)
    except (OSError, RuntimeError, ValueError) as exc:
        QMessageBox.warning(dialog, "Human Correction Unavailable", str(exc))
        return
    if editor.exec() == QDialog.DialogCode.Accepted:
        QMessageBox.information(
            dialog,
            "Human Correction Recorded",
            "Review finding saved separately from the semantic report. "
            "Now select 'Correct From Saved Review…' to inspect attempt "
            "eligibility and the proposed source-conditioned edit. "
            "No generation has occurred.",
        )


def _update_button(dialog: Any) -> None:
    button = getattr(dialog, "candidate_quality_button", None)
    saved_button = getattr(dialog, "candidate_saved_review_button", None)
    correction_button = getattr(dialog, "candidate_correction_button", None)
    human_button = getattr(dialog, "candidate_human_correction_button", None)
    gallery = getattr(dialog, "reference_gallery", None)
    selected = None if gallery is None else gallery.selected_reference()
    from vscs.domain.caps import (
        CanonicalReferenceRole,
        CanonicalReferenceStatus,
        CanonicalReferenceType,
    )

    enabled = (
        selected is not None
        and selected.reference_type is CanonicalReferenceType.IMAGE
        and selected.role is CanonicalReferenceRole.SUPPLEMENTARY
        and selected.status is CanonicalReferenceStatus.CANDIDATE
        and not selected.locked
    )
    if button is not None:
        button.setEnabled(enabled)
    if saved_button is not None:
        saved_button.setEnabled(enabled)
    if correction_button is not None:
        correction_button.setEnabled(enabled)
    if human_button is not None:
        human_button.setEnabled(enabled)


def install_visual_candidate_quality_review() -> None:
    """Extend the existing editor, leaving legacy evaluation controls intact."""
    editor = cap_manager.CAPEditorDialog
    if getattr(editor, "_candidate_quality_installed", False):
        return
    original_init = editor.__init__
    original_refresh = editor._refresh_references

    def quality_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.candidate_quality_button = QPushButton("Review Visual Candidate…")
        self.candidate_quality_button.setObjectName("reviewVisualCandidateQuality")
        self.candidate_quality_button.setToolTip(
            "CIEE technical inspection plus optional paid SIEE grounded in reviewed CAP design"
        )
        self.candidate_quality_button.clicked.connect(lambda: _review_selected(self))
        self.layout().insertWidget(2, self.candidate_quality_button)
        self.candidate_saved_review_button = QPushButton("Open Saved Candidate Review…")
        self.candidate_saved_review_button.setObjectName("openSavedCandidateQualityReview")
        self.candidate_saved_review_button.setToolTip(
            "Reopen the latest saved semantic quality report for Stage B/C1/C2; "
            "never runs a new API evaluation, correction or generation."
        )
        self.candidate_saved_review_button.clicked.connect(
            lambda: _reopen_saved_candidate_review(self)
        )
        self.layout().insertWidget(3, self.candidate_saved_review_button)
        self.candidate_correction_button = QPushButton("Correct From Saved Review…")
        self.candidate_correction_button.setObjectName("correctFromSavedCandidateReview")
        self.candidate_correction_button.setToolTip(
            "Reopen the latest persisted semantic review; no new Terra request"
        )
        self.candidate_correction_button.clicked.connect(lambda: _correct_from_saved_report(self))
        self.layout().insertWidget(4, self.candidate_correction_button)
        self.candidate_human_correction_button = QPushButton(
            "Record Human Correction From Saved Review…"
        )
        self.candidate_human_correction_button.setObjectName("recordHumanCorrectionFromSavedReview")
        self.candidate_human_correction_button.setToolTip(
            "Use saved semantic evidence, no repeat OpenAI charge; "
            "record a separately attributable correction finding."
        )
        self.candidate_human_correction_button.clicked.connect(
            lambda: _record_human_from_saved_report(self)
        )
        self.layout().insertWidget(5, self.candidate_human_correction_button)
        if hasattr(self, "reference_gallery"):
            self.reference_gallery.gallery.currentItemChanged.connect(
                lambda *_: _update_button(self)
            )
        _update_button(self)

    def quality_refresh(self: Any) -> None:
        original_refresh(self)
        _update_button(self)

    editor.__init__ = quality_init  # type: ignore[method-assign]
    editor._refresh_references = quality_refresh  # type: ignore[method-assign]
    editor._candidate_quality_installed = True  # type: ignore[attr-defined]
