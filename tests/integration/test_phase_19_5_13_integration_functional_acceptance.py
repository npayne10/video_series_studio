from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    FunctionalAcceptanceService,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.infrastructure.configuration import ConfigurationService


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _proposal(
    proposal_id: str, proposal_type: AutomationProposalType, target_id: str
) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        target_id=target_id,
        payload={},
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="Phase 19.5.13 persistence acceptance",
        ),
    )


def test_phase_19_5_13_action_is_available_in_story_navigation(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        action = window.story_navigation_actions.get("story.functional_acceptance")
        assert callable(action)


def test_acceptance_evidence_survives_project_close_and_reopen(tmp_path: Path) -> None:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration)
    project_path = tmp_path / "VSCS TSR"
    projects.create(project_path, name="VSCS TSR")
    store = AutomationProposalService(projects)
    store.save(_proposal("EP-1", AutomationProposalType.EPISODE, "EP-001"))

    before = FunctionalAcceptanceService(store).evaluate(
        story_id="STORY-001", source_revision="rev-1"
    )
    projects.close()
    projects.open(project_path)
    reloaded_store = AutomationProposalService(projects)
    after = FunctionalAcceptanceService(reloaded_store).evaluate(
        story_id="STORY-001", source_revision="rev-1"
    )

    assert before.criteria == after.criteria
    assert before.story_id == after.story_id
    assert before.source_revision == after.source_revision
