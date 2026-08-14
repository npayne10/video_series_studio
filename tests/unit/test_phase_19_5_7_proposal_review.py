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


def _proposal(
    proposal_id: str,
    proposal_type: AutomationProposalType,
    payload: dict[str, object],
) -> AutomationProposal:
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


def test_environment_and_performance_proposals_appear_under_shot(qtbot) -> None:
    shot = _proposal(
        "AUT-SHOT-1",
        AutomationProposalType.SHOT,
        {"scene_id": "EP-001-SC-001", "sequence_number": 1, "title": "Arrival"},
    )
    performance = _proposal(
        "AUT-ACTION-1",
        AutomationProposalType.ACTION_PERFORMANCE,
        {"temporal_narrative": "James enters."},
    )
    environment = _proposal(
        "AUT-ENVIRONMENT-1",
        AutomationProposalType.ENVIRONMENT,
        {"surface_state": "Engineered bridge deck", "atmosphere_state": "controlled"},
    )
    store = _ProposalStore((shot, performance, environment))
    dialog = AutomationProposalReviewDialog(
        cast(AutomationProposalService, store),
        story_id="STORY-001",
        source_revision="rev-1",
    )
    qtbot.addWidget(dialog)

    shot_item = dialog.tree.topLevelItem(0)
    assert "SHT-001" in shot_item.text(0)
    assert shot_item.childCount() == 2
    assert "Action / Dialogue / Performance" in shot_item.child(0).text(0)
    assert "Environment Production" in shot_item.child(1).text(0)

    dialog.tree.setCurrentItem(shot_item.child(1))
    details = dialog.details.toPlainText()
    assert "AUT-ENVIRONMENT-1" in details
    assert "Engineered bridge deck" in details
    assert dialog.details.isReadOnly()
