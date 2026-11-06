"""B.5.26D controlled local correction from a persisted visual quality report."""

from __future__ import annotations

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
        layout.addWidget(self.generate_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _generate(self) -> None:
        plan = self.plan
        choice = QMessageBox.question(
            self,
            "Confirm Controlled Local Regeneration",
            f"Generate exactly ONE corrected Candidate using local ComfyUI?\n"
            f"Correction {plan.attempt} of {plan.max_attempts}.\n"
            "This creates a new image and provenance, retains the original, "
            "and performs FREE offline technical re-evaluation. "
            "It does not make a paid OpenAI call, re-approve Canon, "
            "or automatically retry on failure.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice is not QMessageBox.StandardButton.Yes:
            return
        try:
            # Validate the audit, operator budget and CAP before starting a GPU job.
            self.service.verify_current(plan)
            generator = self.service.generator
            image = AutomationProgressRunner(self).run(
                "Controlled Candidate Regeneration",
                plan.source.asset_id,
                lambda: generator.render(
                    plan.preparation, plan.source.project_root, plan.request
                ),
                may_charge=False,
            )
            # Thread-bound project and reference operations remain on the UI thread.
            self.service.verify_current(plan)
            new_id = generator.persist_candidate(
                plan.preparation,
                plan.source.project_root,
                plan.request,
                image,
                regeneration=plan.lineage,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "Corrective Candidate Failed", str(exc))
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
        except (OSError, RuntimeError, ValueError) as exc:
            report_note = (
                f"Offline technical re-evaluation was unavailable: {exc}. "
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
