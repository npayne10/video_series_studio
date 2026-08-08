"""UI contract tests for the Phase 18.2.11.2.7 CAP readiness report."""

from PySide6.QtWidgets import QApplication, QProgressBar

from vscs.domain.caps import (
    ReadinessAssessment,
    ReadinessDimension,
    ReadinessReport,
    ReadinessState,
)
from vscs.presentation.widgets.cap_readiness_widget import CAPReadinessDialog


def _assessment(dimension: ReadinessDimension, score: int) -> ReadinessAssessment:
    return ReadinessAssessment(
        dimension=dimension,
        state=ReadinessState.READY if score == 100 else ReadinessState.PARTIAL,
        score=score,
    )


def test_readiness_dialog_exposes_typed_dimension_scores(
    qtbot: object,
    qapp: QApplication,
) -> None:
    report = ReadinessReport(
        asset_id="CAP-CHR-001",
        identity=_assessment(ReadinessDimension.IDENTITY, 100),
        references=_assessment(ReadinessDimension.REFERENCES, 80),
        generation=_assessment(ReadinessDimension.GENERATION, 100),
        production=_assessment(ReadinessDimension.PRODUCTION, 60),
        overall_score=86,
    )
    dialog = CAPReadinessDialog(report)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    progress = dialog.findChild(QProgressBar, "overallReadinessProgress")
    assert dialog.windowTitle() == "CAP Readiness — CAP-CHR-001"
    assert dialog.report.overall_score == 86
    assert progress is not None
    assert progress.value() == 86
