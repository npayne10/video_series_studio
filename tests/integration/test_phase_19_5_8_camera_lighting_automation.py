from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    CameraLightingProposalAutomationService,
)
from vscs.application.projects import ProjectService
from vscs.application.story import GovernedCameraPlanningService, GovernedLightingPlanningService
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


def test_camera_lighting_automation_is_registered_with_story_workspace(
    tmp_path: Path, qtbot
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        service = application.services.get(CameraLightingProposalAutomationService)
        assert isinstance(service, CameraLightingProposalAutomationService)
        # Phase 19.5.12A relocates this action into hierarchical navigation.
        assert window.story_browser.camera_lighting_proposals_button.isHidden()
        assert (
            window.story_browser.camera_lighting_proposals_button.text()
            == "Camera & Lighting Proposals…"
        )


def test_camera_lighting_proposals_do_not_create_governed_authority(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        store = application.services.require(AutomationProposalService)
        provenance = AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="integration",
            provider="vscs-template",
            model="deterministic",
        )
        for proposal in (
            AutomationProposal(
                proposal_id="SHOT",
                proposal_type=AutomationProposalType.SHOT,
                target_id="EP-001-SC-001-SHT-001",
                payload={
                    "required_action": "James crosses the bridge.",
                    "dialogue_requirement": "",
                },
                provenance=provenance,
            ),
            AutomationProposal(
                proposal_id="PERF",
                proposal_type=AutomationProposalType.ACTION_PERFORMANCE,
                target_id="EP-001-SC-001-SHT-001",
                payload={"temporal_narrative": "James crosses the bridge."},
                provenance=provenance,
            ),
            AutomationProposal(
                proposal_id="ENV",
                proposal_type=AutomationProposalType.ENVIRONMENT,
                target_id="EP-001-SC-001-SHT-001",
                payload={"environment_context": "interior", "continuity_notes": "Bridge"},
                provenance=provenance,
            ),
        ):
            store.save(proposal)
        camera_authority = application.services.require(GovernedCameraPlanningService)
        lighting_authority = application.services.require(GovernedLightingPlanningService)
        before_camera = camera_authority.list_plans()
        before_lighting = lighting_authority.list_plans()
        generated = application.services.require(CameraLightingProposalAutomationService).generate(
            story_id="STORY-001", source_text="James crosses the bridge.", source_revision="rev-1"
        )
        assert len(generated) == 2
        assert camera_authority.list_plans() == before_camera
        assert lighting_authority.list_plans() == before_lighting
