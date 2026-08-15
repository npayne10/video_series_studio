from __future__ import annotations

from typing import cast

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from vscs.presentation.dialogs.automation_proposal_review_dialog import AutomationProposalReviewDialog


class _ProposalStore:
    def __init__(self, proposals: tuple[AutomationProposal, ...]) -> None:
        self.proposals = proposals

    def list_proposals(self) -> tuple[AutomationProposal, ...]:
        return self.proposals


def _proposal(proposal_id: str, proposal_type: AutomationProposalType, payload: dict[str, object]) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        target_id="EP-001-SC-001-SHT-001",
        payload=payload,
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="test",
            provider="test",
            model="test",
        ),
    )


def test_camera_and_lighting_appear_under_shot_in_shared_review(qtbot) -> None:
    proposals = (
        _proposal("SHOT", AutomationProposalType.SHOT, {"scene_id": "SC-001", "sequence_number": 1}),
        _proposal("CAMERA", AutomationProposalType.CAMERA, {"shot_size": "medium", "movement": "static"}),
        _proposal("LIGHTING", AutomationProposalType.LIGHTING, {"lighting_intent": "naturalistic", "key_direction": "motivated"}),
    )
    dialog = AutomationProposalReviewDialog(
        cast(AutomationProposalService, _ProposalStore(proposals)),
        story_id="STORY-001",
        source_revision="rev-1",
    )
    qtbot.addWidget(dialog)
    shot_item = next(
        dialog.tree.topLevelItem(index)
        for index in range(dialog.tree.topLevelItemCount())
        if dialog.tree.topLevelItem(index) is not None
        and "SHT-001" in dialog.tree.topLevelItem(index).text(0)
    )
    labels = {shot_item.child(index).text(0) for index in range(shot_item.childCount())}
    assert "Camera Production" in labels
    assert "Lighting Production" in labels
    assert dialog.details.isReadOnly()
