"""Provider-neutral capability validation domain for Phase 20.17."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum


class ValidationOutcome(StrEnum):
    """Human-observed outcome for one validation scenario."""

    NOT_RUN = "not_run"
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class CapabilityRecommendation(StrEnum):
    """Computed recommendation; never a governance decision."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONDITIONAL = "conditional"
    NOT_RECOMMENDED = "not_recommended"
    RECOMMENDED = "recommended"


class HumanDecision(StrEnum):
    """Explicit human authority over a capability-validation session."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ValidationCriterion:
    criterion_id: str
    label: str
    description: str
    required: bool = True

    def __post_init__(self) -> None:
        _require_text(self.criterion_id, "criterion_id")
        _require_text(self.label, "label")
        _require_text(self.description, "description")


@dataclass(frozen=True, slots=True)
class ValidationScenario:
    scenario_id: str
    label: str
    description: str
    criteria: tuple[ValidationCriterion, ...]
    required: bool = True

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        _require_text(self.label, "label")
        _require_text(self.description, "description")
        if not self.criteria:
            raise ValueError("validation scenario requires at least one criterion")
        criterion_ids = [criterion.criterion_id for criterion in self.criteria]
        if len(set(criterion_ids)) != len(criterion_ids):
            raise ValueError("validation scenario criterion IDs must be unique")


@dataclass(frozen=True, slots=True)
class ProviderCapabilityValidationPack:
    pack_id: str
    provider_family: str
    capability_id: str
    version: str
    scenarios: tuple[ValidationScenario, ...]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("pack_id", self.pack_id),
            ("provider_family", self.provider_family),
            ("capability_id", self.capability_id),
            ("version", self.version),
        ):
            _require_text(value, field_name)
        if not self.scenarios:
            raise ValueError("validation pack requires at least one scenario")
        scenario_ids = [scenario.scenario_id for scenario in self.scenarios]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("validation pack scenario IDs must be unique")


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_id: str
    outcome: ValidationOutcome
    notes: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.criterion_id, "criterion_id")
        _optional_text(self.notes, "notes")


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    outcome: ValidationOutcome
    criterion_results: tuple[CriterionResult, ...]
    evidence_media_ids: tuple[str, ...] = ()
    notes: str | None = None
    recorded_by: str | None = None
    recorded_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_text(self.scenario_id, "scenario_id")
        _optional_text(self.notes, "notes")
        _optional_text(self.recorded_by, "recorded_by")
        for media_id in self.evidence_media_ids:
            _require_text(media_id, "evidence_media_id")
        if len(set(self.evidence_media_ids)) != len(self.evidence_media_ids):
            raise ValueError("evidence_media_ids must be unique")
        criterion_ids = [result.criterion_id for result in self.criterion_results]
        if len(set(criterion_ids)) != len(criterion_ids):
            raise ValueError("criterion result IDs must be unique")
        if self.outcome is not ValidationOutcome.NOT_RUN:
            if not self.recorded_by or self.recorded_at is None:
                raise ValueError("recorded result requires recorded_by and recorded_at")


@dataclass(frozen=True, slots=True)
class CapabilityValidationSession:
    session_id: str
    provider_id: str
    pack_id: str
    capability_id: str
    scenario_results: tuple[ScenarioResult, ...]
    recommendation: CapabilityRecommendation = CapabilityRecommendation.INSUFFICIENT_EVIDENCE
    human_decision: HumanDecision = HumanDecision.PENDING
    decision_actor: str | None = None
    decision_reason: str | None = None
    decided_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for field_name, value in (
            ("session_id", self.session_id),
            ("provider_id", self.provider_id),
            ("pack_id", self.pack_id),
            ("capability_id", self.capability_id),
        ):
            _require_text(value, field_name)
        scenario_ids = [result.scenario_id for result in self.scenario_results]
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("scenario result IDs must be unique")
        if self.human_decision is HumanDecision.PENDING:
            if self.decision_actor or self.decision_reason or self.decided_at:
                raise ValueError("pending decision cannot contain decision authority metadata")
        else:
            if not self.decision_actor or not self.decision_reason or self.decided_at is None:
                raise ValueError("human decision requires actor, reason and decided_at")

    def with_result(
        self, result: ScenarioResult, recommendation: CapabilityRecommendation
    ) -> CapabilityValidationSession:
        results = tuple(
            result if current.scenario_id == result.scenario_id else current
            for current in self.scenario_results
        )
        return replace(
            self,
            scenario_results=results,
            recommendation=recommendation,
            human_decision=HumanDecision.PENDING,
            decision_actor=None,
            decision_reason=None,
            decided_at=None,
            updated_at=datetime.now(UTC),
        )

    def with_decision(
        self, decision: HumanDecision, actor: str, reason: str
    ) -> CapabilityValidationSession:
        if decision is HumanDecision.PENDING:
            raise ValueError("explicit decision must be approved or rejected")
        _require_text(actor, "actor")
        _require_text(reason, "reason")
        now = datetime.now(UTC)
        return replace(
            self,
            human_decision=decision,
            decision_actor=actor.strip(),
            decision_reason=reason.strip(),
            decided_at=now,
            updated_at=now,
        )


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")


def _optional_text(value: str | None, field_name: str) -> None:
    if value is not None and not value.strip():
        raise ValueError(f"{field_name} cannot be blank when supplied")
