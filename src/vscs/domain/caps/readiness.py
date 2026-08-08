"""Deterministic Canonical Asset Profile readiness contracts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReadinessState(StrEnum):
    """Normalized state used by every readiness dimension."""

    NOT_READY = "not_ready"
    PARTIAL = "partial"
    READY = "ready"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class ReadinessDimension(StrEnum):
    """Independent readiness dimensions published to production consumers."""

    IDENTITY = "identity"
    REFERENCES = "references"
    GENERATION = "generation"
    PRODUCTION = "production"


class ReadinessSeverity(StrEnum):
    """Impact of one deterministic readiness gap."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class ReadinessGap(BaseModel):
    """One actionable reason why a CAP is not fully ready."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=96)
    dimension: ReadinessDimension
    severity: ReadinessSeverity
    message: str = Field(min_length=1)


class ReadinessAssessment(BaseModel):
    """One scored readiness dimension with its supporting gaps."""

    model_config = ConfigDict(frozen=True)

    dimension: ReadinessDimension
    state: ReadinessState
    score: int = Field(ge=0, le=100)
    gaps: tuple[ReadinessGap, ...] = ()

    @property
    def ready(self) -> bool:
        return self.state is ReadinessState.READY


class ReadinessReport(BaseModel):
    """Authoritative typed readiness report consumed by future production systems."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    identity: ReadinessAssessment
    references: ReadinessAssessment
    generation: ReadinessAssessment
    production: ReadinessAssessment
    overall_score: int = Field(ge=0, le=100)

    @property
    def assessments(self) -> tuple[ReadinessAssessment, ...]:
        return (self.identity, self.references, self.generation, self.production)

    @property
    def blocking_gaps(self) -> tuple[ReadinessGap, ...]:
        return tuple(
            gap
            for assessment in self.assessments
            for gap in assessment.gaps
            if gap.severity is ReadinessSeverity.BLOCKING
        )

    @property
    def warnings(self) -> tuple[ReadinessGap, ...]:
        return tuple(
            gap
            for assessment in self.assessments
            for gap in assessment.gaps
            if gap.severity is ReadinessSeverity.WARNING
        )

    @property
    def generation_ready(self) -> bool:
        return self.generation.ready

    @property
    def production_ready(self) -> bool:
        return self.production.ready


# Public alias retained for consumers that prefer the earlier specification name.
ReadinessResult = ReadinessReport
