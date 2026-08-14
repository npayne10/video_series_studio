from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    TemplateSemanticProductionProvider,
)
from vscs.application.projects import ProjectService
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


def test_automation_service_is_registered(tmp_path: Path) -> None:
    with build_application_context(_options(tmp_path)) as application:
        service = application.services.get(AutomationProposalService)
        assert isinstance(service, AutomationProposalService)


def test_automation_proposal_requires_human_review_before_consumption(tmp_path: Path) -> None:
    with build_application_context(_options(tmp_path)) as application:
        projects = application.services.get(ProjectService)
        projects.create(tmp_path / "project", name="Automation Test Project")
        service = application.services.get(AutomationProposalService)
        proposal = TemplateSemanticProductionProvider().propose(
            story_id="STORY-001",
            source_revision="rev-1",
            source_text="James enters the bridge.",
            proposal_type=AutomationProposalType.SCENE,
            target_id="SCENE-001",
        )
        stored = service.save(proposal)
        assert stored.status is AutomationProposalStatus.PROPOSED
        assert not stored.consumable

        reviewed = service.mark_reviewed(stored.proposal_id, reviewed_by="operator")
        assert reviewed.status is AutomationProposalStatus.REVIEWED
        assert not reviewed.consumable

        accepted = service.accept(stored.proposal_id, accepted_by="operator")
        assert accepted.status is AutomationProposalStatus.ACCEPTED
        assert accepted.consumable
        assert service.proposal(stored.proposal_id) == accepted
