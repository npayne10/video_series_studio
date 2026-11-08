"""B.5.26D controlled local correction from a persisted visual quality report."""

from __future__ import annotations

import logging
from pathlib import Path

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
from vscs.application.caps.visual_candidate_quality import CandidateQualityReviewService
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)
from vscs.presentation.widgets.automation_progress import AutomationProgressRunner

_LOGGER = logging.getLogger(__name__)


class ControlledCandidateRegenerationDialog(QDialog):
    """Human review/consent before ONE local corrected Candidate is generated."""

    def __init__(
        self,
        references: CanonicalReferenceService,
        asset_id: str,
        reference_id: int,
        report_path: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("controlledCandidateRegeneration")
        self.setWindowTitle("B.5.26D — Corrected Local Candidate (Review First)")
        self.setMinimumSize(780, 600)
        self.service = CandidateRegenerationService(references)
        self.plan: CandidateRegenerationPlan = self.service.prepare(
            asset_id, reference_id, report_path
        )

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Source Candidate: {reference_id}  |  "
                f"Attempt {self.plan.attempt}/{self.plan.max_attempts}  |  "
                "Local XCIC/ComfyUI only — no OpenAI charge."
            )
        )
        label = QLabel(
            "Only accepted Draft CAP fields become corrective instructions. "
            "Terra's findings are advisory evidence, not Canon. "
            "No source image, approval, or CAP data will be overwritten. "
            "New image is a supplementary Candidate, not a MASTER."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        if self.plan.effectiveness_warnings:
            warning = QLabel(
                "B.5.26E — Previous correction effectiveness warning:\n"
                + "\n".join(self.plan.effectiveness_warnings)
                + "\nReview these findings before consuming another local attempt."
            )
            warning.setWordWrap(True)
            warning.setObjectName("correctionEffectivenessWarning")
            layout.addWidget(warning)

        def readonly(title: str, value: str, object_name: str) -> QPlainTextEdit:
            layout.addWidget(QLabel(title))
            view = QPlainTextEdit()
            view.setObjectName(object_name)
            view.setReadOnly(True)
            view.setPlainText(value)
            layout.addWidget(view, 1)
            return view

        readonly(
            "Accepted design constraints (authoritative for this Draft only)",
            "\n".join(self.plan.correction_rules),
            "correctionAcceptedRules",
        )
        readonly(
            "Source quality findings (advisory, not copied into prompt)",
            "\n".join(self.plan.review_findings) or "(none)",
            "correctionSourceFindings",
        )
        self.corrected_prompt = readonly(
            "Automatically prepared corrected prompt — inspect before generation",
            self.plan.request.prompt,
            "correctedVisualCandidatePrompt",
        )
        self.generate_button = QPushButton("Generate ONE Corrected Local Candidate")
        self.generate_button.setObjectName("confirmControlledCandidateRegeneration")
        self.generate_button.clicked.connect(self._generate)
        self._generation_active = False
        layout.addWidget(self.generate_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _generate(self) -> None:
        if self._generation_active:
            return
        plan = self.plan
        choice = QMessageBox.question(
            self,
            "Confirm Controlled Local Regeneration",
            f"Generate exactly ONE corrected Candidate using local ComfyUI?\n"
            f"Correction {plan.attempt} of {plan.max_attempts}.\n"
            "This creates a new image and provenance, retains the original, "
            "and performs FREE offline technical re-evaluation. "
            "It does not make a paid OpenAI call, re-approve Canon, "
            "or automatically retry on failure.\n" + "\n".join(plan.effectiveness_warnings),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self._generation_active = True
        self.generate_button.setEnabled(False)
        stage = "preflight (no GPU request submitted)"
        try:
            # Validate source authority before ANY render attempt. Unexpected
            # exceptions must be visible; Qt otherwise prints and swallows them.
            self.service.verify_current(plan)
            generator = self.service.generator
            stage = "local ComfyUI rendering (check provider queue before retrying)"
            image = AutomationProgressRunner(self).run(
                "Controlled Candidate Regeneration",
                plan.source.asset_id,
                lambda: generator.render(plan.preparation, plan.source.project_root, plan.request),
                may_charge=False,
            )
            # GUI-thread reference operations, including a second authority
            # check, remain outside the worker thread.
            stage = "post-render authority check (image may already have rendered)"
            self.service.verify_current(plan)
            stage = "Candidate registration (check gallery before retrying)"
            new_id = generator.persist_candidate(
                plan.preparation,
                plan.source.project_root,
                plan.request,
                image,
                regeneration=plan.lineage,
            )
        except Exception as exc:
            _LOGGER.exception(
                "B.5.26D controlled regeneration failed at %s for %s",
                stage,
                plan.source.asset_id,
            )
            QMessageBox.critical(
                self,
                "Corrective Candidate Failed",
                f"Stage: {stage}\n{type(exc).__name__}: {exc}\n\n"
                "No successful Candidate registration was confirmed. "
                "If rendering started, inspect the gallery and ComfyUI queue "
                "before attempting another GPU request.",
            )
            self.generate_button.setEnabled(True)
            self._generation_active = False
            return

        # Offline re-evaluation is free and never promotes the image; if the
        # local evaluation fails, the generated Candidate remains reviewable.
        report_note = ""
        try:
            quality = CandidateQualityReviewService(generator.references)
            snapshot = quality.snapshot(plan.source.asset_id, new_id)
            result = AutomationProgressRunner(self).run(
                "Offline Corrected Candidate Check",
                plan.source.asset_id,
                lambda: quality.evaluate(snapshot),
                may_charge=False,
            )
            quality.save(result)
            delta = result.technical.overall_score - plan.previous_technical_score
            report_note = (
                f"Offline technical quality: {result.technical.overall_score}/100 "
                f"(previous {plan.previous_technical_score}/100; delta {delta:+d}).\n"
                "Visual design consistency: NOT re-evaluated. "
                "Use Review Visual Candidate… with separate consent for "
                "semantic comparison against the previous result."
            )
        except Exception as exc:
            _LOGGER.exception(
                "B.5.26D Candidate %s was saved but its offline review failed",
                new_id,
            )
            report_note = (
                f"Offline technical re-evaluation was unavailable: "
                f"{type(exc).__name__}: {exc}. "
                "The new Candidate remains unapproved; review it in the gallery."
            )

        QMessageBox.information(
            self,
            "Corrected Candidate Created",
            f"New supplementary Candidate reference: {new_id}\n"
            f"Parent reference: {plan.source.reference_id}\n"
            f"Correction attempt: {plan.attempt}/{plan.max_attempts}\n"
            f"{report_note}\n"
            "No MASTER, Canon or Production Approval was granted.",
        )
        self.accept()
