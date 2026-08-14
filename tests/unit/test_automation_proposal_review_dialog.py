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


def _provenance() -> AutomationProvenance:
    return AutomationProvenance(
        source_kind=AutomationSourceKind.AI_INFERENCE,
        source_story_id="STORY-001",
        source_revision="rev-1",
        source_scope="Story revision",
        provider="openai",
        model="test-model",
        confidence=0.9,
    )


def _proposal(
    proposal_id: str,
    proposal_type: AutomationProposalType,
    target_id: str,
    payload: dict[str, object],
) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        target_id=target_id,
        payload=payload,
        provenance=_provenance(),
    )


def test_proposal_review_dialog_builds_episode_scene_shot_hierarchy(qtbot) -> None:
    episode = _proposal(
        "AUT-EPISODE-001",
        AutomationProposalType.EPISODE,
        "EP-001",
        {
            "sequence_number": 1,
            "title": "The Silent Relay",
            "target_runtime_seconds": 360,
        },
    )
    scene = _proposal(
        "AUT-SCENE-001",
        AutomationProposalType.SCENE,
        "EP-001-SC-001",
        {
            "episode_id": "EP-001",
            "sequence_number": 1,
            "title": "The Signal",
            "target_runtime_seconds": 60,
        },
    )
    shot_one = _proposal(
        "AUT-SHOT-001",
        AutomationProposalType.SHOT,
        "EP-001-SC-001-SHT-001",
        {
            "scene_id": "EP-001-SC-001",
            "sequence_number": 1,
            "title": "Detection",
            "target_runtime_seconds": 20,
            "required_action": "Sandra detects the signal",
        },
    )
    shot_two = _proposal(
        "AUT-SHOT-002",
        AutomationProposalType.SHOT,
        "EP-001-SC-001-SHT-002",
        {
            "scene_id": "EP-001-SC-001",
            "sequence_number": 2,
            "title": "Reaction",
            "target_runtime_seconds": 40,
            "required_action": "James orders it played",
        },
    )
    store = _ProposalStore((episode, scene, shot_two, shot_one))
    dialog = AutomationProposalReviewDialog(
        cast(AutomationProposalService, store),
        story_id="STORY-001",
        source_revision="rev-1",
    )
    qtbot.addWidget(dialog)

    assert dialog.tree.topLevelItemCount() == 1
    episode_item = dialog.tree.topLevelItem(0)
    assert episode_item.text(0).startswith("EP-001")
    assert episode_item.childCount() == 1
    scene_item = episode_item.child(0)
    assert scene_item.text(0).startswith("EP-001-SC-001")
    assert scene_item.childCount() == 2
    assert scene_item.child(0).text(0).startswith("EP-001-SC-001-SHT-001")
    assert scene_item.child(1).text(0).startswith("EP-001-SC-001-SHT-002")

    dialog.tree.setCurrentItem(scene_item.child(0))
    assert "AUT-SHOT-001" in dialog.details.toPlainText()
    assert "Sandra detects the signal" in dialog.details.toPlainText()
    assert dialog.details.isReadOnly()


def test_proposal_review_dialog_filters_other_story_revisions(qtbot) -> None:
    current = _proposal(
        "AUT-EPISODE-CURRENT",
        AutomationProposalType.EPISODE,
        "EP-001",
        {"sequence_number": 1, "title": "Current"},
    )
    stale = AutomationProposal(
        proposal_id="AUT-EPISODE-STALE",
        proposal_type=AutomationProposalType.EPISODE,
        target_id="EP-099",
        payload={"sequence_number": 99, "title": "Stale"},
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision="old-revision",
            source_scope="Old Story revision",
            provider="openai",
            model="test-model",
            confidence=0.8,
        ),
    )
    store = _ProposalStore((current, stale))
    dialog = AutomationProposalReviewDialog(
        cast(AutomationProposalService, store),
        story_id="STORY-001",
        source_revision="rev-1",
    )
    qtbot.addWidget(dialog)

    assert dialog.tree.topLevelItemCount() == 1
    assert "Current" in dialog.tree.topLevelItem(0).text(0)
    assert "Stale" not in dialog.tree.topLevelItem(0).text(0)
