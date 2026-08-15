from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ProposalAutoCompilationOrchestrator,
)
from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    GovernedShotPlanningService,
    ScenePlanningService,
    StoryLifecycleService,
)
from vscs.infrastructure.configuration import ConfigurationService


def test_auto_compilation_does_not_overwrite_differing_episode_authority(tmp_path: Path) -> None:
    configuration = ConfigurationService(tmp_path / "settings.toml")
    projects = ProjectService(configuration)
    projects.create(tmp_path / "Project", name="Project")
    lifecycle = StoryLifecycleService(projects)
    lifecycle.create_story(title="The Silent Relay")
    episodes = EpisodePlanningService(projects, lifecycle)
    scenes = ScenePlanningService(projects, episodes)
    shots = GovernedShotPlanningService(projects, scenes, ShotPlanningService(projects))
    store = AutomationProposalService(projects)

    existing = episodes.create(
        story_id="STORY-001",
        sequence_number=1,
        title="Human Episode Title",
        story_scope="Human-authored scope",
        production_objective="Human-authored objective",
        target_runtime_seconds=90,
    )

    store.save(
        AutomationProposal(
            proposal_id="AUT-EPISODE-1",
            proposal_type=AutomationProposalType.EPISODE,
            target_id="EP-001",
            payload={
                "story_id": "STORY-001",
                "sequence_number": 1,
                "title": "Automation Episode Title",
                "story_scope": "Automation scope",
                "production_objective": "Automation objective",
                "target_runtime_seconds": 60,
                "continuity_in": "",
                "continuity_out": "",
                "production_constraints": [],
            },
            provenance=AutomationProvenance(
                source_kind=AutomationSourceKind.AI_INFERENCE,
                source_story_id="STORY-001",
                source_revision="rev-1",
                source_scope="test",
                provider="test",
                model="test",
            ),
            status=AutomationProposalStatus.ACCEPTED,
            reviewed_by="Neill",
            accepted_by="Neill",
        )
    )

    report = ProposalAutoCompilationOrchestrator(
        projects,
        store,
        episodes,
        scenes,
        shots,
    ).compile_current(
        story_id="STORY-001",
        source_revision="rev-1",
        compiled_by="Neill",
    )

    assert report.episodes_created == 0
    assert report.episodes_reused == 0
    assert report.blocked_proposals == 1
    unchanged = episodes.plan(existing.episode_id)
    assert unchanged == existing
    assert "will not overwrite human-governed authority" in report.blockers[0]
