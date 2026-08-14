from __future__ import annotations

from vscs.application.automation import (
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    TemplateSemanticProductionProvider,
)


def test_automation_service_is_registered(application_context) -> None:
    service = application_context.services.get(AutomationProposalService)
    assert isinstance(service, AutomationProposalService)


def test_automation_proposal_requires_human_review_before_consumption(tmp_path, project_service) -> None:
    project_service._project_directory = tmp_path
    service = AutomationProposalService(project_service)
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
