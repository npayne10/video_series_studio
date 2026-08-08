"""Unit tests for the Phase 18.2.11.2.7 readiness domain contract."""

from vscs.domain.caps import (
    ReadinessAssessment,
    ReadinessDimension,
    ReadinessGap,
    ReadinessReport,
    ReadinessSeverity,
    ReadinessState,
)


def test_typed_readiness_report_exposes_blockers_and_warnings() -> None:
    blocker = ReadinessGap(
        code="references.front",
        dimension=ReadinessDimension.REFERENCES,
        severity=ReadinessSeverity.BLOCKING,
        message="Front reference is missing",
    )
    warning = ReadinessGap(
        code="production.guidance",
        dimension=ReadinessDimension.PRODUCTION,
        severity=ReadinessSeverity.WARNING,
        message="Production guidance is incomplete",
    )
    identity = ReadinessAssessment(
        dimension=ReadinessDimension.IDENTITY,
        state=ReadinessState.READY,
        score=100,
    )
    references = ReadinessAssessment(
        dimension=ReadinessDimension.REFERENCES,
        state=ReadinessState.PARTIAL,
        score=80,
        gaps=(blocker,),
    )
    generation = ReadinessAssessment(
        dimension=ReadinessDimension.GENERATION,
        state=ReadinessState.BLOCKED,
        score=67,
        gaps=(blocker,),
    )
    production = ReadinessAssessment(
        dimension=ReadinessDimension.PRODUCTION,
        state=ReadinessState.BLOCKED,
        score=50,
        gaps=(warning,),
    )

    report = ReadinessReport(
        asset_id="CAP-SHP-001",
        identity=identity,
        references=references,
        generation=generation,
        production=production,
        overall_score=75,
    )

    assert report.production_ready is False
    assert blocker in report.blocking_gaps
    assert warning in report.warnings
    assert report.assessments == (identity, references, generation, production)
