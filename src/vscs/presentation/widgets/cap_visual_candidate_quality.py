"""Integrated B.5.26 CAP image Candidate review: CIEE + consented SIEE."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.visual_candidate_quality import (
    CandidateQualityResult,
    CandidateQualityReviewService,
)
from vscs.presentation.widgets.cap_visual_candidate_regeneration import (
    ControlledCandidateRegenerationDialog,
)
from vscs.infrastructure.ai import AICredentialStore
from vscs.infrastructure.ai.openai_semantic_evaluator import OpenAISemanticImageEvaluator
from vscs.infrastructure.configuration import ConfigurationService
from vscs.presentation.widgets import cap_manager
from vscs.presentation.widgets.automation_progress import AutomationProgressRunner


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
                        f"{report.current_design_consistency_score}"
                        if report.semantic is not None
                        else "NOT RUN"
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
                "Regenerate a fresh local Candidate through Prepare Visual Identity. "
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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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


def _update_button(dialog: Any) -> None:
    button = getattr(dialog, "candidate_quality_button", None)
    gallery = getattr(dialog, "reference_gallery", None)
    selected = None if gallery is None else gallery.selected_reference()
    if button is not None:
        from vscs.domain.caps import (
            CanonicalReferenceRole,
            CanonicalReferenceStatus,
            CanonicalReferenceType,
        )

        button.setEnabled(
            selected is not None
            and selected.reference_type is CanonicalReferenceType.IMAGE
            and selected.role is CanonicalReferenceRole.SUPPLEMENTARY
            and selected.status is CanonicalReferenceStatus.CANDIDATE
            and not selected.locked
        )


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
