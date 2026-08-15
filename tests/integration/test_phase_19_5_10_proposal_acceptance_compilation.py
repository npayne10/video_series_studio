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
from vscs.application.story import (
    GovernedCameraPlanningService,
    GovernedEnvironmentPlanningService,
    GovernedLightingPlanningService,
    StoryLifecycleService,
)
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


def _accepted_proposal(
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
            source_scope="integration",
            provider="test",
            model="test",
        ),
        status=AutomationProposalStatus.ACCEPTED,
        reviewed_by="Neill",
        accepted_by="Neill",
    )


def test_phase_19_5_10_services_are_registered_with_story_workspace(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        acceptance = application.services.get(ProposalAcceptanceService)
        orchestrator = application.services.get(ProposalAutoCompilationOrchestrator)
        assert isinstance(acceptance, ProposalAcceptanceService)
        assert isinstance(orchestrator, ProposalAutoCompilationOrchestrator)
        assert window.story_browser.proposal_acceptance_service is acceptance
        assert window.story_browser.auto_compilation_orchestrator is orchestrator


def test_accepted_structure_compiles_without_creating_specialist_or_final_authority(
    tmp_path: Path, qtbot
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        application.services.require(StoryLifecycleService).create_story(title="The Silent Relay")
        store = application.services.require(AutomationProposalService)

        for proposal in (
            _accepted_proposal(
                "AUT-EPISODE-1",
                AutomationProposalType.EPISODE,
                "EP-001",
                {
                    "story_id": "STORY-001",
                    "sequence_number": 1,
                    "title": "The Silent Relay",
                    "story_scope": "Test story scope",
                    "production_objective": "Produce the test sequence",
                    "target_runtime_seconds": 60,
                    "continuity_in": "",
                    "continuity_out": "",
                    "production_constraints": [],
                },
            ),
            _accepted_proposal(
                "AUT-SCENE-1",
                AutomationProposalType.SCENE,
                "EP-001-SC-001",
                {
                    "episode_id": "EP-001",
                    "sequence_number": 1,
                    "title": "Signal",
                    "story_scope": "Signal is detected",
                    "production_objective": "Present the signal",
                    "target_runtime_seconds": 60,
                    "setting_requirement": "Bridge interior",
                    "required_events": ["Signal detected"],
                    "continuity_in": "",
                    "continuity_out": "Signal remains active",
                    "scene_constraints": [],
                },
            ),
            _accepted_proposal(
                "AUT-SHOT-1",
                AutomationProposalType.SHOT,
                "EP-001-SC-001-SHT-001",
                {
                    "scene_id": "EP-001-SC-001",
                    "sequence_number": 1,
                    "title": "Detection",
                    "narrative_purpose": "Reveal the signal",
                    "production_objective": "Show detection clearly",
                    "target_runtime_seconds": 60,
                    "required_action": "Sandra detects the signal",
                    "dialogue_requirement": "",
                    "continuity_in": "",
                    "continuity_out": "Signal remains active",
                    "shot_constraints": [],
                },
            ),
        ):
            store.save(proposal)

        camera_authority = application.services.require(GovernedCameraPlanningService)
        lighting_authority = application.services.require(GovernedLightingPlanningService)
        environment_authority = application.services.require(GovernedEnvironmentPlanningService)
        before_camera = camera_authority.list_plans()
        before_lighting = lighting_authority.list_plans()
        before_environment = environment_authority.list_plans()

        report = application.services.require(ProposalAutoCompilationOrchestrator).compile_current(
            story_id="STORY-001",
            source_revision="rev-1",
            compiled_by="Neill",
        )

        assert report.episodes_created == 1
        assert report.scenes_created == 1
        assert report.shots_created == 1
        assert report.blocked_proposals == 0
        assert camera_authority.list_plans() == before_camera
        assert lighting_authority.list_plans() == before_lighting
        assert environment_authority.list_plans() == before_environment
