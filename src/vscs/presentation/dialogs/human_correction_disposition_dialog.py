"""F5.4 GUI: deliberate human correction disposition, no implicit generation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.human_review_disposition import (
    save_human_correction_disposition,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot


class HumanCorrectionDispositionDialog(QDialog):
    """Record a separate reviewer decision against one already accepted field."""

    def __init__(
        self, snapshot: CandidateQualitySnapshot, report_path: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.snapshot = snapshot
        self.report_path = report_path
        self.saved_path: Path | None = None
        self.setWindowTitle("F5.4 — Human-Reviewed Candidate Correction")
        self.setObjectName("humanCandidateCorrectionDisposition")
        self.resize(750, 460)
        layout = QVBoxLayout(self)
        heading = QLabel(
            f"Candidate {snapshot.reference_id} — {snapshot.asset_id}\n"
            "This records a human correction finding. It does NOT rewrite the "
            "semantic report, approve Canon, or start image generation."
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(QLabel("Accepted Draft field requiring correction"))
        self.field = QComboBox()
        self.field.setObjectName("humanCorrectionAcceptedField")
        for key, value in snapshot.accepted_fields:
            self.field.addItem(f"{key}: {value[:115]}", key)
        layout.addWidget(self.field)
        layout.addWidget(QLabel("Reviewer identity (required)"))
        self.reviewer = QLineEdit()
        self.reviewer.setObjectName("humanCorrectionReviewer")
        layout.addWidget(self.reviewer)
        layout.addWidget(QLabel("Observed visual discrepancy (15–2000 characters)"))
        self.reason = QPlainTextEdit()
        self.reason.setObjectName("humanCorrectionObservedDiscrepancy")
        self.reason.setPlaceholderText(
            "Describe what is visibly wrong compared with this reviewed CAP field. "
            "Do not invent or amend the accepted design."
        )
        layout.addWidget(self.reason)
        controls = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        controls.accepted.connect(self._save)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def _save(self) -> None:
        field = self.field.currentData()
        try:
            if not isinstance(field, str):
                raise ValueError("Choose one accepted CAP field")
            saved = save_human_correction_disposition(
                self.snapshot,
                self.report_path,
                reviewer=self.reviewer.text(),
                accepted_field=field,
                observed_discrepancy=self.reason.toPlainText(),
            )
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(self, "Human Correction Not Recorded", str(exc))
            return
        self.saved_path = saved
        self.accept()
