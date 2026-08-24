from __future__ import annotations

from dataclasses import dataclass, field

from vscs.application.provider_capability_validation import ProviderCapabilityValidationService
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
from vscs.infrastructure.provider_capability_validation import (
    JsonCapabilityValidationRepository,
    ltx23_video_validation_pack,
    wan22_video_validation_pack,
)
from vscs.presentation.widgets.provider_capability_validation_workspace import (
    ProviderCapabilityValidationWorkspace,
)


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


def _media(media_id: str, provider_id: str = "ltx23-local") -> GeneratedMedia:
    return GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="PROVIDER-VALIDATION",
            episode_id="LTX23-VAL-001",
            production_task_id="provider-capability-validation",
            scene_id="provider-validation",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id=f"VAL-{media_id}",
            provider_id=provider_id,
            provider_job_id=f"EXTERNAL-{media_id}",
        ),
        file=GeneratedMediaFile(relative_path=f"generated/{media_id}.mp4"),
    )


def _pass_results(scenario_id: str) -> tuple[CriterionResult, ...]:
    scenario = next(
        item for item in ltx23_video_validation_pack().scenarios if item.scenario_id == scenario_id
    )
    return tuple(
        CriterionResult(criterion.criterion_id, ValidationOutcome.PASS)
        for criterion in scenario.criteria
    )


def _service() -> ProviderCapabilityValidationService:
    return ProviderCapabilityValidationService(
        _SessionRepository(),
        _MediaRepository(),
        (wan22_video_validation_pack(), ltx23_video_validation_pack()),
    )


def test_phase_20_18_registers_comparable_wan22_and_ltx23_packs() -> None:
    wan = wan22_video_validation_pack()
    ltx = ltx23_video_validation_pack()

    assert ltx.pack_id == "ltx-2.3-video-v1"
    assert ltx.provider_family == "ltx"
    assert ltx.capability_id == "video-generation.ltx-2.3"
    assert ltx.version == "1.0"
    assert len(ltx.scenarios) == 5
    assert sum(len(scenario.criteria) for scenario in ltx.scenarios) == 15
    assert tuple(scenario.scenario_id for scenario in ltx.scenarios) == tuple(
        scenario.scenario_id for scenario in wan.scenarios
    )
    assert tuple(
        tuple(criterion.criterion_id for criterion in scenario.criteria)
        for scenario in ltx.scenarios
    ) == tuple(
        tuple(criterion.criterion_id for criterion in scenario.criteria)
        for scenario in wan.scenarios
    )


def test_phase_20_18_service_exposes_both_provider_validation_packs() -> None:
    packs = _service().available_packs()

    assert {pack.pack_id for pack in packs} == {"wan-2.2-video-v1", "ltx-2.3-video-v1"}


def test_phase_20_18_workspace_lists_and_starts_ltx23_pack(qtbot) -> None:
    service = _service()
    workspace = ProviderCapabilityValidationWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    labels = {workspace.pack.itemText(index) for index in range(workspace.pack.count())}
    assert labels == {
        "wan / video-generation.wan-2.2 / 1.0",
        "ltx / video-generation.ltx-2.3 / 1.0",
    }

    workspace.pack.setCurrentIndex(workspace.pack.findData("ltx-2.3-video-v1"))
    workspace.provider_id.setEditText("ltx23-local")
    workspace.session_id.setEditText("LTX23-VAL-UI")
    workspace.start_button.click()

    assert workspace.table.rowCount() == 15
    assert "Session LTX23-VAL-UI" in workspace.summary.text()
    assert service.get("LTX23-VAL-UI") is not None


def test_phase_20_18_workspace_discovers_existing_sessions_by_pack_and_provider(qtbot) -> None:
    service = _service()
    service.start_session(
        session_id="LTX23-VAL-001",
        provider_id="ltx23-local",
        pack_id="ltx-2.3-video-v1",
    )
    service.start_session(
        session_id="LTX23-VAL-002",
        provider_id="ltx23-lab",
        pack_id="ltx-2.3-video-v1",
    )
    service.start_session(
        session_id="WAN22-VAL-001",
        provider_id="wan22-local",
        pack_id="wan-2.2-video-v1",
    )
    workspace = ProviderCapabilityValidationWorkspace(lambda: service)
    qtbot.addWidget(workspace)

    workspace.pack.setCurrentIndex(workspace.pack.findData("ltx-2.3-video-v1"))

    providers = {
        workspace.provider_id.itemText(index) for index in range(workspace.provider_id.count())
    }
    assert providers == {"ltx23-local", "ltx23-lab"}
    assert "wan22-local" not in providers

    workspace.provider_id.setCurrentText("ltx23-local")
    sessions = {
        workspace.session_id.itemText(index) for index in range(workspace.session_id.count())
    }
    assert sessions == {"LTX23-VAL-001"}

    workspace.session_id.setCurrentText("LTX23-VAL-001")
    workspace.start_button.click()

    assert workspace.table.rowCount() == 15
    assert "Session LTX23-VAL-001" in workspace.summary.text()


def test_phase_20_18_ltx23_session_can_be_completed_and_approved() -> None:
    media = _MediaRepository()
    service = ProviderCapabilityValidationService(
        _SessionRepository(),
        media,
        (wan22_video_validation_pack(), ltx23_video_validation_pack()),
    )
    pack = ltx23_video_validation_pack()
    session = service.start_session(
        session_id="LTX23-VAL-001",
        provider_id="ltx23-local",
        pack_id=pack.pack_id,
    )

    assert session.capability_id == "video-generation.ltx-2.3"
    assert len(session.scenario_results) == 5
    assert session.recommendation is CapabilityRecommendation.INSUFFICIENT_EVIDENCE

    for index, scenario in enumerate(pack.scenarios, start=1):
        media_id = f"GM-LTX23-{index}"
        media.save(_media(media_id))
        session = service.record_scenario(
            session_id=session.session_id,
            scenario_id=scenario.scenario_id,
            criterion_results=_pass_results(scenario.scenario_id),
            evidence_media_ids=(media_id,),
            actor="validator-1",
            notes=f"LTX 2.3 validation evidence for {scenario.label}",
        )

    assert session.recommendation is CapabilityRecommendation.RECOMMENDED
    assert session.human_decision is HumanDecision.PENDING

    approved = service.decide(
        session_id=session.session_id,
        decision=HumanDecision.APPROVED,
        actor="human-authority",
        reason="All required LTX 2.3 scenarios were reviewed and accepted.",
    )

    assert approved.human_decision is HumanDecision.APPROVED
    assert approved.decision_actor == "human-authority"
    assert approved.decision_reason == "All required LTX 2.3 scenarios were reviewed and accepted."


def test_phase_20_18_ltx23_session_persists_and_reloads(tmp_path) -> None:
    repository = JsonCapabilityValidationRepository(tmp_path / "provider_capability_validation")
    service = ProviderCapabilityValidationService(
        repository,
        _MediaRepository(),
        (wan22_video_validation_pack(), ltx23_video_validation_pack()),
    )
    created = service.start_session(
        session_id="LTX23-VAL-PERSIST",
        provider_id="ltx23-local",
        pack_id=ltx23_video_validation_pack().pack_id,
    )

    reloaded = ProviderCapabilityValidationService(
        JsonCapabilityValidationRepository(tmp_path / "provider_capability_validation"),
        _MediaRepository(),
        (wan22_video_validation_pack(), ltx23_video_validation_pack()),
    ).get(created.session_id)

    assert reloaded == created
    assert reloaded is not None
    assert reloaded.pack_id == "ltx-2.3-video-v1"
    assert reloaded.capability_id == "video-generation.ltx-2.3"
