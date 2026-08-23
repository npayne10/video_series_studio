from __future__ import annotations

from datetime import UTC, datetime

from vscs.domain.provider_capability_validation import (
    CapabilityRecommendation,
    CapabilityValidationSession,
    CriterionResult,
    HumanDecision,
    ScenarioResult,
    ValidationOutcome,
)
from vscs.infrastructure.provider_capability_validation import (
    JsonCapabilityValidationRepository,
)


def test_phase_20_17_json_repository_round_trip(tmp_path) -> None:
    repository = JsonCapabilityValidationRepository(tmp_path / "capability_validation")
    recorded_at = datetime(2026, 8, 23, 8, 0, tzinfo=UTC)
    session = CapabilityValidationSession(
        session_id="WAN22-VAL-PERSIST",
        provider_id="wan22-local",
        pack_id="wan-2.2-video-v1",
        capability_id="video-generation.wan-2.2",
        scenario_results=(
            ScenarioResult(
                scenario_id="text-to-video-baseline",
                outcome=ValidationOutcome.PASS,
                criterion_results=(CriterionResult("prompt-adherence", ValidationOutcome.PASS),),
                evidence_media_ids=("GM-001",),
                recorded_by="validator-1",
                recorded_at=recorded_at,
            ),
        ),
        recommendation=CapabilityRecommendation.RECOMMENDED,
        human_decision=HumanDecision.APPROVED,
        decision_actor="human-authority",
        decision_reason="Accepted after evidence review.",
        decided_at=recorded_at,
        created_at=recorded_at,
        updated_at=recorded_at,
    )

    repository.save(session)
    loaded = repository.get(session.session_id)

    assert loaded == session
    assert repository.list_all() == (session,)
    assert repository.list_for_provider("wan22-local") == (session,)
    assert repository.list_for_provider("other") == ()
