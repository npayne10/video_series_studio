from __future__ import annotations

from vscs.application.automation import (
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationSourceKind,
    SemanticStoryInterpretationService,
)
from vscs.application.story_analysis.ai_analysis import EntityResolutionService
from vscs.domain.story_analysis import AnalysisResult
from vscs.infrastructure.ai import TemplateStoryAIAnalysisProvider


class _ProposalStore:
    def __init__(self) -> None:
        self.saved = []

    def save(self, proposal):
        self.saved.append(proposal)
        return proposal


def _service() -> tuple[SemanticStoryInterpretationService, _ProposalStore]:
    store = _ProposalStore()
    resolution = EntityResolutionService(TemplateStoryAIAnalysisProvider())
    return SemanticStoryInterpretationService(resolution, store), store  # type: ignore[arg-type]


def test_semantic_interpretation_creates_reviewable_story_proposal() -> None:
    service, store = _service()
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-1")

    result = service.interpret(
        story_id="STORY-001",
        source_revision="rev-1",
        source_text="James enters the bridge of the Iron Horizon.",
        baseline=baseline,
    )

    assert result.proposal.proposal_type is AutomationProposalType.STORY_INTERPRETATION
    assert result.proposal.status is AutomationProposalStatus.PROPOSED
    assert result.proposal.provenance.source_kind is AutomationSourceKind.DETERMINISTIC_RESOLUTION
    assert not result.proposal.consumable
    assert store.saved == [result.proposal]


def test_semantic_interpretation_rejects_stale_baseline() -> None:
    service, _store = _service()
    baseline = AnalysisResult(story_id="STORY-001", source_revision="old-revision")

    try:
        service.interpret(
            story_id="STORY-001",
            source_revision="rev-2",
            source_text="James enters the bridge.",
            baseline=baseline,
        )
    except ValueError as exc:
        assert "stale" in str(exc).casefold()
    else:
        raise AssertionError("Expected stale Story Analysis baseline to be rejected")


def test_semantic_interpretation_is_deterministic_for_same_revision() -> None:
    service, _store = _service()
    baseline = AnalysisResult(story_id="STORY-001", source_revision="rev-1")
    kwargs = {
        "story_id": "STORY-001",
        "source_revision": "rev-1",
        "source_text": "James enters the bridge.",
        "baseline": baseline,
        "persist": False,
    }

    first = service.interpret(**kwargs)
    second = service.interpret(**kwargs)

    assert first.proposal.proposal_id == second.proposal.proposal_id
    assert first.proposal.metadata["source_sha256"] == second.proposal.metadata["source_sha256"]
