from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.automation import (
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    TemplateSemanticProductionProvider,
)


def test_ai_provenance_requires_provider_and_model() -> None:
    with pytest.raises(ValueError, match="provider and model"):
        AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="chapter 1",
            confidence=0.8,
        )


def test_template_provider_returns_proposal_not_authority() -> None:
    provider = TemplateSemanticProductionProvider()
    proposal = provider.propose(
        story_id="story-001",
        source_revision="rev-1",
        source_text="James enters the bridge.",
        proposal_type=AutomationProposalType.SCENE,
        target_id="scene-001",
    )

    assert proposal.status is AutomationProposalStatus.PROPOSED
    assert proposal.target_id == "SCENE-001"
    assert proposal.provenance.source_kind is AutomationSourceKind.STORY
    assert not proposal.consumable


def test_only_human_accepted_proposal_is_consumable() -> None:
    proposal = TemplateSemanticProductionProvider().propose(
        story_id="STORY-001",
        source_revision="rev-1",
        source_text="James enters the bridge.",
        proposal_type=AutomationProposalType.SHOT,
        target_id="SHOT-001",
    )
    reviewed = replace(
        proposal,
        status=AutomationProposalStatus.REVIEWED,
        reviewed_by="Neill",
    )
    accepted = replace(
        reviewed,
        status=AutomationProposalStatus.ACCEPTED,
        accepted_by="Neill",
    )

    assert not reviewed.consumable
    assert accepted.consumable
