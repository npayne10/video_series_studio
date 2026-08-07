"""Unit tests for Phase 18.2.6 AI Story Analysis and Entity Resolution."""

from vscs.application.story_analysis.ai_analysis import (
    EntityResolutionService,
    ExistingAssetReference,
)
from vscs.domain.assets import AssetCategory
from vscs.domain.story_analysis import (
    AIEntityDraft,
    AINarrativeMetadata,
    AIStoryAnalysisDraft,
    AnalysisResult,
    CandidateReviewStatus,
    EntityResolutionCategory,
    ResolutionMatchKind,
)


class _Provider:
    def analyze_story(self, *, story_id, source_text, baseline):
        del story_id, source_text, baseline
        return AIStoryAnalysisDraft(
            entities=(
                AIEntityDraft(
                    name="Iron Horizon",
                    category=EntityResolutionCategory.SHIP,
                    description="Survey vessel",
                    evidence_text=("Iron Horizon entered orbit.",),
                    confidence=0.97,
                ),
                AIEntityDraft(
                    name="Xorix",
                    category=EntityResolutionCategory.PLANET,
                    evidence_text=("Xorix filled the viewport.",),
                    confidence=0.94,
                ),
            ),
            metadata=AINarrativeMetadata(themes=("Discovery",), confidence=0.9),
        )


class _Catalog:
    def assets(self):
        return (
            ExistingAssetReference(
                asset_id="CAP-SHP-IRON-HORIZON",
                name="Iron Horizon",
                category=AssetCategory.SHIP,
            ),
        )


class _CharacterProvider:
    def analyze_story(self, *, story_id, source_text, baseline):
        del story_id, source_text, baseline
        return AIStoryAnalysisDraft(
            entities=(
                AIEntityDraft(
                    name="James Spence",
                    category=EntityResolutionCategory.CHARACTER,
                    confidence=0.99,
                ),
            )
        )


class _CharacterCatalog:
    def assets(self):
        return (
            ExistingAssetReference(
                asset_id="CAP-CHR-001",
                name="Commander James Spence",
                category=AssetCategory.CHARACTER,
            ),
            ExistingAssetReference(
                asset_id="CAP-CHR-002",
                name="Captain Cheryl Draker",
                category=AssetCategory.CHARACTER,
            ),
        )


def test_entity_resolution_matches_existing_xpd_asset_and_keeps_new_entity() -> None:
    source = "Iron Horizon entered orbit. Xorix filled the viewport."
    result = EntityResolutionService(_Provider(), _Catalog()).analyze(
        story_id="STORY-001",
        source_text=source,
        baseline=AnalysisResult(story_id="STORY-001"),
    )

    ship, planet = result.candidates
    assert ship.match_kind is ResolutionMatchKind.EXISTING
    assert ship.matched_asset_id == "CAP-SHP-IRON-HORIZON"
    assert planet.match_kind is ResolutionMatchKind.NEW
    assert ship.evidence[0].excerpt == "Iron Horizon entered orbit."
    assert result.metadata.themes == ("Discovery",)


def test_character_rank_variant_matches_existing_xpd_identity() -> None:
    result = EntityResolutionService(_CharacterProvider(), _CharacterCatalog()).analyze(
        story_id="STORY-001",
        source_text="James Spence entered the bridge.",
        baseline=AnalysisResult(story_id="STORY-001"),
    )

    candidate = result.candidates[0]
    assert candidate.match_kind is ResolutionMatchKind.EXISTING
    assert candidate.matched_asset_id == "CAP-CHR-001"
    assert candidate.matched_asset_name == "Commander James Spence"


def test_candidate_review_state_is_explicit_and_immutable() -> None:
    result = EntityResolutionService(_Provider(), _Catalog()).analyze(
        story_id="STORY-001",
        source_text="Iron Horizon entered orbit. Xorix filled the viewport.",
        baseline=AnalysisResult(story_id="STORY-001"),
    )
    candidate = result.candidates[0]

    assert candidate.review_status is CandidateReviewStatus.PROPOSED
    assert candidate.approve().review_status is CandidateReviewStatus.APPROVED
    assert candidate.reject().review_status is CandidateReviewStatus.REJECTED
    assert candidate.review_status is CandidateReviewStatus.PROPOSED
