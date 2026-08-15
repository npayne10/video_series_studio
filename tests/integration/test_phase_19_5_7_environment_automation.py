from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    EnvironmentProposalAutomationService,
)
from vscs.application.projects import ProjectService
from vscs.application.story import GovernedEnvironmentPlanningService
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


def _provenance() -> AutomationProvenance:
    return AutomationProvenance(
        source_kind=AutomationSourceKind.AI_INFERENCE,
        source_story_id="STORY-001",
        source_revision="rev-1",
        source_scope="test",
        provider="test",
        model="test",
    )


def test_environment_automation_is_registered_with_story_workspace(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        service = application.services.get(EnvironmentProposalAutomationService)
        workspace = window.story_browser

        assert isinstance(service, EnvironmentProposalAutomationService)
        # Phase 19.5.12A relocates these actions into hierarchical navigation.
        assert workspace.environment_proposals_button.isHidden()
        assert workspace.environment_proposals_button.text() == "Environment Proposals…"
        assert workspace.review_proposals_button.isHidden()


def test_environment_proposals_do_not_create_governed_environment_plans(
    tmp_path: Path,
    qtbot,
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        store = application.services.require(AutomationProposalService)
        store.save(
            AutomationProposal(
                proposal_id="AUT-SHOT-1",
                proposal_type=AutomationProposalType.SHOT,
                target_id="EP-001-SC-001-SHT-001",
                payload={"required_action": "James crosses the bridge."},
                provenance=_provenance(),
            )
        )
        store.save(
            AutomationProposal(
                proposal_id="AUT-ACTION-1",
                proposal_type=AutomationProposalType.ACTION_PERFORMANCE,
                target_id="EP-001-SC-001-SHT-001",
                payload={"temporal_narrative": "James crosses the bridge."},
                provenance=_provenance(),
            )
        )
        governed = application.services.require(GovernedEnvironmentPlanningService)
        before = governed.list_plans()

        generated = application.services.require(EnvironmentProposalAutomationService).generate(
            story_id="STORY-001",
            source_text="James crosses the bridge.",
            source_revision="rev-1",
        )

        assert len(generated) == 1
        assert generated[0].proposal_type is AutomationProposalType.ENVIRONMENT
        assert governed.list_plans() == before
