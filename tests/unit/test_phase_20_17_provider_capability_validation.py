from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from vscs.application.provider_capability_validation import (
    ProviderCapabilityValidationService,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
)
from vscs.domain.provider_capability_validation import (
    CapabilityRecommendation,
    CapabilityValidationSession,
    CriterionResult,
    HumanDecision,
    ValidationOutcome,
)
from vscs.infrastructure.provider_capability_validation import wan22_video_validation_pack


@dataclass
class _SessionRepository:
    values: dict[str, CapabilityValidationSession] = field(default_factory=dict)

    def get(self, session_id: str) -> CapabilityValidationSession | None:
        return self.values.get(session_id)

    def save(self, session: CapabilityValidationSession) -> CapabilityValidationSession:
        self.values[session.session_id] = session
        return session

    def list_all(self) -> tuple[CapabilityValidationSession, ...]:
        return tuple(self.values[key] for key in sorted(self.values))

    def list_for_provider(self, provider_id: str) -> tuple[CapabilityValidationSession, ...]:
        return tuple(session for session in self.list_all() if session.provider_id == provider_id)


@dataclass
class _MediaRepository:
    values: dict[str, GeneratedMedia] = field(default_factory=dict)

    def get(self, media_id: str) -> GeneratedMedia | None:
        return self.values.get(media_id)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        self.values[media.media_id] = media
        return media

    def list_all(self) -> tuple[GeneratedMedia, ...]:
        return tuple(self.values.values())

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        return ()

    def list_for_episode(self, production_id: str, episode_id: str) -> tuple[GeneratedMedia, ...]:
        return ()

    def list_for_scene(
        self, production_id: str, episode_id: str, scene_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return ()

    def list_for_shot(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
        shot_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        return ()

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        return ()

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        return ()


def _media(media_id: str, provider_id: str = "wan22-local") -> GeneratedMedia:
    return GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="PROD-1",
            episode_id="E01",
            production_task_id="TASK-1",
            scene_id="S01",
            shot_id="SH01",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id=f"EXEC-{media_id}",
            provider_id=provider_id,
            provider_job_id=f"JOB-{media_id}",
        ),
        file=GeneratedMediaFile(relative_path=f"generated/{media_id}.mp4"),
    )


def _service() -> tuple[ProviderCapabilityValidationService, _MediaRepository]:
    media = _MediaRepository()
    service = ProviderCapabilityValidationService(
        _SessionRepository(),
        media,
        (wan22_video_validation_pack(),),
    )
    return service, media


def _pass_results(scenario_id: str) -> tuple[CriterionResult, ...]:
    pack = wan22_video_validation_pack()
    scenario = next(item for item in pack.scenarios if item.scenario_id == scenario_id)
    return tuple(
        CriterionResult(criterion.criterion_id, ValidationOutcome.PASS)
        for criterion in scenario.criteria
    )


def test_wan22_pack_defines_five_required_governed_scenarios() -> None:
    pack = wan22_video_validation_pack()

    assert pack.provider_family == "wan"
    assert pack.capability_id == "video-generation.wan-2.2"
    assert len(pack.scenarios) == 5
    assert all(scenario.required for scenario in pack.scenarios)
    assert {scenario.scenario_id for scenario in pack.scenarios} == {
        "text-to-video-baseline",
        "image-to-video-reference-fidelity",
        "camera-motion-control",
        "subject-continuity",
        "complex-production-shot",
    }


def test_recommendation_requires_all_required_scenarios_and_human_decision() -> None:
    service, media = _service()
    pack = wan22_video_validation_pack()
    session = service.start_session(
        session_id="WAN22-VAL-001",
        provider_id="wan22-local",
        pack_id=pack.pack_id,
    )

    assert session.recommendation is CapabilityRecommendation.INSUFFICIENT_EVIDENCE
    assert session.human_decision is HumanDecision.PENDING

    for index, scenario in enumerate(pack.scenarios, start=1):
        media_id = f"GM-WAN22-{index}"
        media.save(_media(media_id))
        session = service.record_scenario(
            session_id=session.session_id,
            scenario_id=scenario.scenario_id,
            criterion_results=_pass_results(scenario.scenario_id),
            evidence_media_ids=(media_id,),
            actor="validator-1",
        )

    assert session.recommendation is CapabilityRecommendation.RECOMMENDED
    assert session.human_decision is HumanDecision.PENDING

    approved = service.decide(
        session_id=session.session_id,
        decision=HumanDecision.APPROVED,
        actor="human-authority",
        reason="All required Wan 2.2 scenarios were reviewed and accepted.",
    )
    assert approved.human_decision is HumanDecision.APPROVED
    assert approved.recommendation is CapabilityRecommendation.RECOMMENDED


def test_failed_required_scenario_is_not_recommended_but_not_auto_rejected() -> None:
    service, media = _service()
    pack = wan22_video_validation_pack()
    session = service.start_session(
        session_id="WAN22-VAL-002",
        provider_id="wan22-local",
        pack_id=pack.pack_id,
    )

    for index, scenario in enumerate(pack.scenarios, start=1):
        media_id = f"GM-WAN22-F-{index}"
        media.save(_media(media_id))
        results = list(_pass_results(scenario.scenario_id))
        if scenario.scenario_id == "subject-continuity":
            results[0] = CriterionResult(results[0].criterion_id, ValidationOutcome.FAIL)
        session = service.record_scenario(
            session_id=session.session_id,
            scenario_id=scenario.scenario_id,
            criterion_results=tuple(results),
            evidence_media_ids=(media_id,),
            actor="validator-1",
        )

    assert session.recommendation is CapabilityRecommendation.NOT_RECOMMENDED
    assert session.human_decision is HumanDecision.PENDING


def test_evidence_must_be_owned_generated_media_from_session_provider() -> None:
    service, media = _service()
    pack = wan22_video_validation_pack()
    session = service.start_session(
        session_id="WAN22-VAL-003",
        provider_id="wan22-local",
        pack_id=pack.pack_id,
    )
    scenario = pack.scenarios[0]
    media.save(_media("GM-OTHER", provider_id="different-provider"))

    with pytest.raises(ValueError, match="not wan22-local"):
        service.record_scenario(
            session_id=session.session_id,
            scenario_id=scenario.scenario_id,
            criterion_results=_pass_results(scenario.scenario_id),
            evidence_media_ids=("GM-OTHER",),
            actor="validator-1",
        )


def test_decision_is_blocked_until_required_evidence_is_complete() -> None:
    service, _media_repository = _service()
    pack = wan22_video_validation_pack()
    session = service.start_session(
        session_id="WAN22-VAL-004",
        provider_id="wan22-local",
        pack_id=pack.pack_id,
    )

    with pytest.raises(ValueError, match="complete validation evidence"):
        service.decide(
            session_id=session.session_id,
            decision=HumanDecision.APPROVED,
            actor="human-authority",
            reason="Too early",
        )
