from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ProposalAcceptanceService,
    ProposalAutoCompilationOrchestrator,
)
from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    EpisodePlanStatus,
    GovernedShotPlanningService,
    ScenePlanningService,
    ScenePlanStatus,
    ShotPlanStatus,
    StoryLifecycleService,
)
from vscs.infrastructure.configuration import ConfigurationService


def _provenance() -> AutomationProvenance:
    return AutomationProvenance(
        source_kind=AutomationSourceKind.AI_INFERENCE,
        source_story_id="STORY-001",
        source_revision="rev-1",
        source_scope="Phase 19.5 test",
        provider="test",
        model="test",
    )


def _services(tmp_path: Path):
    configuration = ConfigurationService(tmp_path / "settings.toml")
    projects = ProjectService(configuration)
    projects.create(tmp_path / "Project", name="Project")
    lifecycle = StoryLifecycleService(projects)
    lifecycle.create_story(title="The Silent Relay")
    episodes = EpisodePlanningService(projects, lifecycle)
    scenes = ScenePlanningService(projects, episodes)
    shots = GovernedShotPlanningService(projects, scenes, ShotPlanningService(projects))
    store = AutomationProposalService(projects)
    acceptance = ProposalAcceptanceService(store)
    orchestrator = ProposalAutoCompilationOrchestrator(
        projects,
        store,
        episodes,
        scenes,
        shots,
    )
    return store, acceptance, orchestrator, episodes, scenes, shots


def _save_structure(store: AutomationProposalService) -> None:
    provenance = _provenance()
    for proposal in (
        AutomationProposal(
            proposal_id="AUT-EPISODE-1",
            proposal_type=AutomationProposalType.EPISODE,
            target_id="EP-001",
            payload={
                "story_id": "STORY-001",
                "sequence_number": 1,
                "title": "The Silent Relay",
                "story_scope": "Test story scope",
                "production_objective": "Produce one test scene",
                "target_runtime_seconds": 60,
                "continuity_in": "",
                "continuity_out": "",
                "production_constraints": [],
            },
            provenance=provenance,
        ),
        AutomationProposal(
            proposal_id="AUT-SCENE-1",
            proposal_type=AutomationProposalType.SCENE,
            target_id="EP-001-SC-001",
            payload={
                "episode_id": "EP-001",
                "sequence_number": 1,
                "title": "Signal",
                "story_scope": "The signal is detected",
                "production_objective": "Present the detection",
                "target_runtime_seconds": 60,
                "setting_requirement": "Bridge interior",
                "required_events": ["Signal detected"],
                "continuity_in": "",
                "continuity_out": "Signal remains active",
                "scene_constraints": [],
            },
            provenance=provenance,
        ),
        AutomationProposal(
            proposal_id="AUT-SHOT-1",
            proposal_type=AutomationProposalType.SHOT,
            target_id="EP-001-SC-001-SHT-001",
            payload={
                "scene_id": "EP-001-SC-001",
                "sequence_number": 1,
                "title": "Detection",
                "narrative_purpose": "Reveal the signal",
                "production_objective": "Show the signal detection clearly",
                "target_runtime_seconds": 60,
                "required_action": "Sandra detects the signal",
                "dialogue_requirement": "",
                "continuity_in": "",
                "continuity_out": "Signal remains active",
                "shot_constraints": [],
            },
            provenance=provenance,
        ),
    ):
        store.save(proposal)


def test_bulk_acceptance_leaves_unresolved_assets_and_conflicts_blocked(tmp_path: Path) -> None:
    store, acceptance, _orchestrator, _episodes, _scenes, _shots = _services(tmp_path)
    _save_structure(store)
    provenance = _provenance()
    store.save(
        AutomationProposal(
            proposal_id="AUT-ASSET-UNRESOLVED",
            proposal_type=AutomationProposalType.ASSET,
            target_id="AUTO-CHARACTER-UNKNOWN",
            payload={
                "canonical_status": "new_asset_required",
                "human_resolution_required": True,
            },
            provenance=provenance,
        )
    )
    store.save(
        AutomationProposal(
            proposal_id="AUT-CONTINUITY-CONFLICT",
            proposal_type=AutomationProposalType.CONTINUITY,
            target_id="EP-001-SC-001-SHT-001",
            payload={"continuity_conflicts": ["Human review required"]},
            provenance=provenance,
        )
    )

    summary = acceptance.accept_eligible_current(
        story_id="STORY-001",
        source_revision="rev-1",
        reviewed_by="Neill",
    )

    assert summary.accepted_now == 3
    assert summary.blocked == 2
    assert store.proposal("AUT-EPISODE-1").status is AutomationProposalStatus.ACCEPTED
    assert store.proposal("AUT-ASSET-UNRESOLVED").status is AutomationProposalStatus.PROPOSED
    assert store.proposal("AUT-CONTINUITY-CONFLICT").status is AutomationProposalStatus.PROPOSED


def test_auto_compilation_materializes_accepted_structure_with_canonical_id_mapping(
    tmp_path: Path,
) -> None:
    store, acceptance, orchestrator, episodes, scenes, shots = _services(tmp_path)
    _save_structure(store)
    acceptance.accept_eligible_current(
        story_id="STORY-001",
        source_revision="rev-1",
        reviewed_by="Neill",
    )

    report = orchestrator.compile_current(
        story_id="STORY-001",
        source_revision="rev-1",
        compiled_by="Neill",
    )

    assert report.episodes_created == 1
    assert report.scenes_created == 1
    assert report.shots_created == 1
    assert report.blocked_proposals == 0
    assert report.authority_map["EP-001-SC-001"] == "EP-001-SCN-001"
    assert report.authority_map["EP-001-SC-001-SHT-001"] == "EP-001-SCN-001-SHT-001"
    assert episodes.plan("EP-001").status is EpisodePlanStatus.READY
    assert scenes.plan("EP-001-SCN-001").status is ScenePlanStatus.READY
    assert shots.plan("EP-001-SCN-001-SHT-001").status is ShotPlanStatus.READY

    second = orchestrator.compile_current(
        story_id="STORY-001",
        source_revision="rev-1",
        compiled_by="Neill",
    )
    assert second.episodes_created == 0 and second.episodes_reused == 1
    assert second.scenes_created == 0 and second.scenes_reused == 1
    assert second.shots_created == 0 and second.shots_reused == 1
    assert second.ready_promotions == 0
