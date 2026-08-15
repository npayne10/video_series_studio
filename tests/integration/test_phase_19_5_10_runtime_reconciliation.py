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
from vscs.application.story import GovernedShotPlanningService, StoryLifecycleService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _accepted(
    proposal_id: str,
    proposal_type: AutomationProposalType,
    target_id: str,
    payload: dict[str, object],
) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        target_id=target_id,
        payload=payload,
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="runtime-reconciliation-test",
            provider="test",
            model="test",
        ),
        status=AutomationProposalStatus.ACCEPTED,
        reviewed_by="Neill",
        accepted_by="Neill",
    )


def _shot(sequence: int, runtime: int) -> AutomationProposal:
    return _accepted(
        f"AUT-SHOT-{sequence}",
        AutomationProposalType.SHOT,
        f"EP-001-SC-001-SHT-{sequence:03d}",
        {
            "scene_id": "EP-001-SC-001",
            "sequence_number": sequence,
            "title": f"Shot {sequence}",
            "narrative_purpose": f"Purpose {sequence}",
            "production_objective": f"Objective {sequence}",
            "target_runtime_seconds": runtime,
            "required_action": f"Action {sequence}",
            "dialogue_requirement": "",
            "continuity_in": "",
            "continuity_out": "",
            "shot_constraints": [],
        },
    )


def test_recompile_fits_complete_accepted_shot_set_and_repairs_prior_automation_authority(
    tmp_path: Path, qtbot
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        application.services.require(StoryLifecycleService).create_story(title="The Silent Relay")
        store = application.services.require(AutomationProposalService)

        store.save(
            _accepted(
                "AUT-EPISODE-1",
                AutomationProposalType.EPISODE,
                "EP-001",
                {
                    "story_id": "STORY-001",
                    "sequence_number": 1,
                    "title": "The Silent Relay",
                    "story_scope": "Test scope",
                    "production_objective": "Produce test",
                    "target_runtime_seconds": 60,
                    "continuity_in": "",
                    "continuity_out": "",
                    "production_constraints": [],
                },
            )
        )
        store.save(
            _accepted(
                "AUT-SCENE-1",
                AutomationProposalType.SCENE,
                "EP-001-SC-001",
                {
                    "episode_id": "EP-001",
                    "sequence_number": 1,
                    "title": "Scene",
                    "story_scope": "Scene scope",
                    "production_objective": "Scene objective",
                    "target_runtime_seconds": 60,
                    "setting_requirement": "Bridge",
                    "required_events": ["Event"],
                    "continuity_in": "",
                    "continuity_out": "",
                    "scene_constraints": [],
                },
            )
        )
        store.save(_shot(1, 40))
        store.save(_shot(2, 20))

        orchestrator = application.services.require(ProposalAutoCompilationOrchestrator)
        first = orchestrator.compile_current(
            story_id="STORY-001", source_revision="rev-1", compiled_by="Neill"
        )
        assert first.shots_created == 2

        # Simulate the early Phase 19.5 proposal-store case: a later accepted Shot
        # appears in the same Story revision after an earlier structural compilation.
        store.save(_shot(3, 30))
        second = orchestrator.compile_current(
            story_id="STORY-001", source_revision="rev-1", compiled_by="Neill"
        )

        plans = application.services.require(GovernedShotPlanningService).list_plans(
            scene_id="EP-001-SCN-001"
        )
        assert second.shots_created == 1
        assert second.shots_reused == 2
        assert second.blocked_proposals == 0
        assert len(plans) == 3
        assert sum(plan.target_runtime_seconds for plan in plans) == 60
        assert all(plan.status.value == "ready" for plan in plans)
