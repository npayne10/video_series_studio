from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    EpisodeProposalDraft,
    EpisodeSceneProposalAutomationService,
    EpisodeSceneProposalDraft,
    SceneProposalDraft,
    SemanticStoryInterpretation,
)
from vscs.domain.story_analysis import AnalysisResult, EntityResolutionResult


class _ProposalStore:
    def __init__(self) -> None:
        self.saved: list[AutomationProposal] = []

    def save(self, proposal: AutomationProposal) -> AutomationProposal:
        self.saved.append(proposal)
        return proposal


class _Provider:
    provider_name = "test-semantic-provider"
    model_name = "test-model"

    def propose_episode_scenes(self, **_kwargs) -> EpisodeSceneProposalDraft:
        return EpisodeSceneProposalDraft(
            episodes=(
                EpisodeProposalDraft(
                    sequence_number=1,
                    title="The Silent Relay",
                    story_scope="Iron Horizon investigates the silent relay.",
                    production_objective="Produce the complete short story.",
                    target_runtime_seconds=600,
                    scenes=(
                        SceneProposalDraft(
                            sequence_number=1,
                            title="The Signal",
                            story_scope="A repeating signal is detected.",
                            production_objective="Introduce the mystery.",
                            target_runtime_seconds=120,
                            setting_requirement="Iron Horizon bridge in Xorix orbit",
                            required_events=("Sandra detects the repeating signal.",),
                            confidence=0.9,
                        ),
                        SceneProposalDraft(
                            sequence_number=2,
                            title="The Moon",
                            story_scope="The crew investigates the moon.",
                            production_objective="Escalate the investigation.",
                            target_runtime_seconds=180,
                            setting_requirement="Airless outer moon and Listening Post 17",
                            required_events=("Iron Horizon reaches the outer moon.",),
                            confidence=0.85,
                        ),
                    ),
                    confidence=0.9,
                ),
            ),
        )


def _semantic(revision: str = "rev-1") -> SemanticStoryInterpretation:
    proposal = AutomationProposal(
        proposal_id="AUT-SEMANTIC-001",
        proposal_type=AutomationProposalType.STORY_INTERPRETATION,
        target_id="STORY-001",
        payload={"summary": "A mysterious relay signal draws the crew to an abandoned station."},
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision=revision,
            source_scope="complete Story",
            provider="openai",
            model="test-model",
        ),
    )
    return SemanticStoryInterpretation(
        story_id="STORY-001",
        source_revision=revision,
        entity_resolution=EntityResolutionResult(story_id="STORY-001", source_revision=revision),
        proposal=proposal,
    )


def test_generate_creates_episode_and_scene_proposals_without_authority() -> None:
    store = _ProposalStore()
    service = EpisodeSceneProposalAutomationService(_Provider(), store)  # type: ignore[arg-type]
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-1")

    proposals = service.generate(
        story_id="STORY-001",
        source_text="The Iron Horizon detected a repeating signal.",
        source_revision="rev-1",
        baseline=baseline,
        semantic=_semantic(),
    )

    assert [proposal.proposal_type for proposal in proposals] == [
        AutomationProposalType.EPISODE,
        AutomationProposalType.SCENE,
        AutomationProposalType.SCENE,
    ]
    assert all(proposal.status is AutomationProposalStatus.PROPOSED for proposal in proposals)
    assert all(not proposal.consumable for proposal in proposals)
    assert proposals[0].target_id == "EP-001"
    assert proposals[1].target_id == "EP-001-SC-001"
    assert proposals[1].payload["setting_requirement"] == "Iron Horizon bridge in Xorix orbit"
    assert len(store.saved) == 3


def test_generate_rejects_stale_semantic_interpretation() -> None:
    service = EpisodeSceneProposalAutomationService(_Provider(), _ProposalStore())  # type: ignore[arg-type]
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-2")

    with pytest.raises(ValueError, match="Semantic interpretation is stale"):
        service.generate(
            story_id="STORY-001",
            source_text="Story text",
            source_revision="rev-2",
            baseline=baseline,
            semantic=_semantic("rev-1"),
        )


def test_episode_scene_proposals_are_deterministic_for_same_story_revision() -> None:
    service = EpisodeSceneProposalAutomationService(_Provider(), _ProposalStore())  # type: ignore[arg-type]
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-1")
    kwargs = {
        "story_id": "STORY-001",
        "source_text": "Story text",
        "source_revision": "rev-1",
        "baseline": baseline,
        "semantic": _semantic(),
    }

    first = service.generate(**kwargs)
    second = service.generate(**kwargs)

    assert [item.proposal_id for item in first] == [item.proposal_id for item in second]
    accepted = replace(first[0], status=AutomationProposalStatus.ACCEPTED, accepted_by="Neill")
    assert accepted.consumable
    assert first[0].status is AutomationProposalStatus.PROPOSED
