"""Integrated B.5.26 CAP image Candidate review: CIEE + consented SIEE."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
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
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.reference_service import CanonicalReferenceService
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
        dialog.resize(800, 610)
        layout = QVBoxLayout(dialog)

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
        roi.setPlaceholderText("Optional normalized ROI: x,y,width,height (e.g. 0.1,0.2,0.3,0.4)")
        layout.addWidget(roi)
        propose = QPushButton("Inspect Stage B Evidence / ROI (No Generation)", dialog)
        propose.setObjectName("spatialEvidenceInspect")
        layout.addWidget(propose)

        def inspect_spatial_evidence() -> None:
            try:
                state = VisualEvidenceStatus(str(evidence_status.currentData()))
                values = roi.text().strip()
                region = None
                if values:
                    components = values.split(",")
                    if len(components) != 4:
                        raise GeometryCorrectionError("ROI requires four normalized coordinates")
                    try:
                        region = NormalizedRegion(*(float(v.strip()) for v in components))
                    except ValueError as exc:
                        raise GeometryCorrectionError("ROI coordinates must be numeric") from exc
                evidence = propose_spatial_evidence(
                    baseline,
                    field=str(fields.currentData()),
                    status=state,
                    observation=reason.toPlainText(),
                    defect=(
                        GeometryDefect(str(defect.currentData()))
                        if state is VisualEvidenceStatus.FAILED else None
                    ),
                    region=region,
                    expected_source_sha256=report.snapshot.image_sha256,
                )
            except (GeometryCorrectionError, ValueError) as exc:
                QMessageBox.warning(dialog, "Stage B Evidence Blocked", str(exc))
                return
            details.setPlainText(evidence.describe())

        propose.clicked.connect(inspect_spatial_evidence)
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
        self.candidate_correction_button = QPushButton("Correct From Saved Review…")
        self.candidate_correction_button.setObjectName("correctFromSavedCandidateReview")
        self.candidate_correction_button.setToolTip(
            "Reopen the latest persisted semantic review; no new Terra request"
        )
        self.candidate_correction_button.clicked.connect(lambda: _correct_from_saved_report(self))
        self.layout().insertWidget(3, self.candidate_correction_button)
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
        self.layout().insertWidget(4, self.candidate_human_correction_button)
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
