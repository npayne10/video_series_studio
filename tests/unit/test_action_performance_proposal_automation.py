from pathlib import Path

import pytest

from vscs.application.automation import (
    ActionPerformanceProposalAutomationService,
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    TemplateActionPerformanceProposalProvider,
)
from vscs.application.projects import ProjectService


def _service(tmp_path: Path) -> tuple[ActionPerformanceProposalAutomationService, AutomationProposalService]:
    projects = ProjectService(tmp_path)
    projects._project_directory = tmp_path
    store = AutomationProposalService(projects)
    store.save(AutomationProposal(
        proposal_id="AUT-SHOT-1", proposal_type=AutomationProposalType.SHOT,
        target_id="EP-001-SC-001-SHT-001",
        payload={"required_action": "James enters the bridge.", "dialogue_requirement": "Report.", "continuity_in": "Corridor", "continuity_out": "At console", "target_runtime_seconds": 12},
        provenance=AutomationProvenance(source_kind=AutomationSourceKind.AI_INFERENCE, source_story_id="STORY-001", source_revision="rev-1", source_scope="scene", provider="test", model="test"),
    ))
    return ActionPerformanceProposalAutomationService(TemplateActionPerformanceProposalProvider(), store), store


def test_performance_automation_creates_proposal_without_authority(tmp_path: Path) -> None:
    service, store = _service(tmp_path)
    proposals = service.generate(story_id="STORY-001", source_text="James enters the bridge and says, Report.", source_revision="rev-1")
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.proposal_type is AutomationProposalType.ACTION_PERFORMANCE
    assert proposal.status.value == "proposed"
    assert not proposal.consumable
    assert proposal.payload["temporal_narrative"] == "James enters the bridge."
    assert proposal.payload["spoken_content"] == "Report."
    assert proposal.metadata["parent_shot_proposal_id"] == "AUT-SHOT-1"
    assert len(store.list_proposals()) == 2


def test_performance_automation_requires_current_shot_proposals(tmp_path: Path) -> None:
    service, _store = _service(tmp_path)
    with pytest.raises(ValueError, match="Shot proposals"):
        service.generate(story_id="STORY-001", source_text="Story", source_revision="rev-2")
