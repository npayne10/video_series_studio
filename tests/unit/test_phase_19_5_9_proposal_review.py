from __future__ import annotations

from typing import cast

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from vscs.presentation.dialogs.automation_proposal_review_dialog import (
    AutomationProposalReviewDialog,
)


class _ProposalStore:
    def __init__(self, proposals: tuple[AutomationProposal, ...]) -> None:
        self.proposals = proposals

    def list_proposals(self) -> tuple[AutomationProposal, ...]:
        return self.proposals


def test_continuity_proposal_appears_beneath_shot_in_shared_review(qtbot) -> None:
    provenance = AutomationProvenance(
        source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
        source_story_id="STORY-001",
        source_revision="rev-1",
        source_scope="test",
        provider="vscs",
        model="deterministic-continuity-resolution",
    )
    shot = AutomationProposal(
        proposal_id="SHOT",
        proposal_type=AutomationProposalType.SHOT,
        target_id="EP-001-SC-001-SHT-001",
        payload={"scene_id": "EP-001-SC-001", "sequence_number": 1},
        provenance=provenance,
    )
    continuity = AutomationProposal(
        proposal_id="CONT",
        proposal_type=AutomationProposalType.CONTINUITY,
        target_id=shot.target_id,
        payload={
            "previous_shot_id": "",
            "effective_opening_state": "Bridge entry",
            "current_closing_state": "At console",
            "continuity_conflicts": [],
        },
        provenance=provenance,
    )
    store = _ProposalStore((shot, continuity))
    dialog = AutomationProposalReviewDialog(
        cast(AutomationProposalService, store),
        story_id="STORY-001",
        source_revision="rev-1",
    )
    qtbot.addWidget(dialog)
    shot_item = dialog.tree.topLevelItem(0)
    assert shot_item is not None
    assert shot_item.childCount() == 1
    continuity_item = shot_item.child(0)
    assert continuity_item.text(0) == "Continuity Awareness"
    dialog.tree.setCurrentItem(continuity_item)
    details = dialog.details.toPlainText()
    assert "continuity" in details.lower()
    assert "Bridge entry" in details
    assert dialog.details.isReadOnly()
