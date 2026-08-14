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


def test_asset_resolution_proposals_appear_in_shared_review_surface(qtbot) -> None:
    proposal = AutomationProposal(
        proposal_id="AUT-ASSET-001",
        proposal_type=AutomationProposalType.ASSET,
        target_id="CHR-JAMES",
        payload={
            "name": "Commander James Spence",
            "expected_asset_category": "character",
            "resolution_kind": "existing_canonical_asset",
            "canonical_status": "resolved",
            "matched_asset_id": "CHR-JAMES",
        },
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="Story entity plus XPD/CAP",
            provider="vscs",
            model="deterministic-canonical-resolution",
            confidence=0.99,
        ),
    )
    store = _ProposalStore((proposal,))
    dialog = AutomationProposalReviewDialog(
        cast(AutomationProposalService, store),
        story_id="STORY-001",
        source_revision="rev-1",
    )
    qtbot.addWidget(dialog)

    assert dialog.tree.topLevelItemCount() == 1
    root = dialog.tree.topLevelItem(0)
    assert root.text(0) == "Canonical Entity & Asset Resolution"
    assert root.childCount() == 1
    asset_item = root.child(0)
    assert "Commander James Spence" in asset_item.text(0)

    dialog.tree.setCurrentItem(asset_item)
    details = dialog.details.toPlainText()
    assert "AUT-ASSET-001" in details
    assert "existing_canonical_asset" in details
    assert "CHR-JAMES" in details
    assert dialog.details.isReadOnly()
