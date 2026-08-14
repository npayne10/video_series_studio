from __future__ import annotations

from typing import cast

import pytest

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    SceneShotProposalAutomationService,
    SceneShotProposalDraft,
    ShotProposalDraft,
    TemplateSceneShotProposalProvider,
)
from vscs.domain.story_analysis import AnalysisResult


class _ProposalStore:
    def __init__(self, proposals: tuple[AutomationProposal, ...]) -> None:
        self.proposals = list(proposals)

    def list_proposals(self) -> tuple[AutomationProposal, ...]:
        return tuple(self.proposals)

    def save(self, proposal: AutomationProposal) -> AutomationProposal:
        self.proposals = [
            item for item in self.proposals if item.proposal_id != proposal.proposal_id
        ]
        self.proposals.append(proposal)
        return proposal


def _scene(*, runtime: int = 60, revision: str = "rev-1") -> AutomationProposal:
    return AutomationProposal(
        proposal_id="AUT-SCENE-001",
        proposal_type=AutomationProposalType.SCENE,
        target_id="EP-001-SC-001",
        payload={
            "episode_id": "EP-001",
            "sequence_number": 1,
            "title": "The Signal",
            "story_scope": "Sandra detects a repeating emergency transmission.",
            "production_objective": "Reveal the anomalous transmission.",
            "target_runtime_seconds": runtime,
            "setting_requirement": "Iron Horizon bridge",
            "required_events": ["Sandra detects the signal", "James orders it played"],
            "continuity_in": "Iron Horizon remains in Xorix orbit",
            "continuity_out": "The crew decides to investigate",
            "scene_constraints": ["Preserve Iron Horizon bridge continuity"],
        },
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.AI_INFERENCE,
            source_story_id="STORY-001",
            source_revision=revision,
            source_scope="Story revision",
            provider="openai",
            model="test-model",
            confidence=0.9,
        ),
    )


def _service(
    provider: TemplateSceneShotProposalProvider | object | None = None,
    *,
    scene: AutomationProposal | None = None,
) -> tuple[SceneShotProposalAutomationService, _ProposalStore]:
    store = _ProposalStore((scene or _scene(),))
    selected = provider or TemplateSceneShotProposalProvider()
    return (
        SceneShotProposalAutomationService(
            selected,  # type: ignore[arg-type]
            cast(AutomationProposalService, store),
        ),
        store,
    )


def test_scene_shot_automation_creates_reviewable_shot_proposals() -> None:
    service, _store = _service()
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-1")

    proposals = service.generate(
        story_id="STORY-001",
        source_text="Sandra detects a signal and James orders it played.",
        source_revision="rev-1",
        baseline=baseline,
    )

    assert len(proposals) == 2
    assert all(item.proposal_type is AutomationProposalType.SHOT for item in proposals)
    assert all(item.status is AutomationProposalStatus.PROPOSED for item in proposals)
    assert all(not item.consumable for item in proposals)
    assert [item.target_id for item in proposals] == [
        "EP-001-SC-001-SHT-001",
        "EP-001-SC-001-SHT-002",
    ]
    assert sum(int(item.payload["target_runtime_seconds"]) for item in proposals) == 60
    assert all(item.metadata["parent_scene_proposal_id"] == "AUT-SCENE-001" for item in proposals)


def test_scene_shot_automation_rejects_stale_scene_proposals() -> None:
    service, _store = _service(scene=_scene(revision="old-revision"))
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-2")

    with pytest.raises(ValueError, match="Episode/Scene proposals"):
        service.generate(
            story_id="STORY-001",
            source_text="Current Story revision.",
            source_revision="rev-2",
            baseline=baseline,
        )


def test_scene_shot_automation_rejects_runtime_overflow() -> None:
    class _OverflowProvider:
        provider_name = "test"
        model_name = "overflow"

        def propose_scene_shots(self, **_kwargs: object) -> SceneShotProposalDraft:
            return SceneShotProposalDraft(
                shots=(
                    ShotProposalDraft(
                        sequence_number=1,
                        title="Shot 1",
                        narrative_purpose="Event one",
                        production_objective="Show event one",
                        target_runtime_seconds=40,
                        required_action="Event one",
                    ),
                    ShotProposalDraft(
                        sequence_number=2,
                        title="Shot 2",
                        narrative_purpose="Event two",
                        production_objective="Show event two",
                        target_runtime_seconds=30,
                        required_action="Event two",
                    ),
                )
            )

    service, _store = _service(_OverflowProvider())
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-1")

    with pytest.raises(ValueError, match="exceed the Scene runtime budget"):
        service.generate(
            story_id="STORY-001",
            source_text="Story source.",
            source_revision="rev-1",
            baseline=baseline,
        )
