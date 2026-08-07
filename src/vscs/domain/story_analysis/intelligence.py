"""Persistent approved Story Intelligence domain contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from vscs.domain.story_analysis.entity_resolution import (
    AINarrativeMetadata,
    CandidateReviewStatus,
    EntityResolutionCategory,
)
from vscs.domain.story_analysis.models import SourceSpan


class StoryEntityDecision(BaseModel):
    """Persisted human decision for one AI-proposed production entity."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    category: EntityResolutionCategory
    review_status: CandidateReviewStatus
    canonical_asset_id: str | None = None
    canonical_asset_name: str | None = None
    description: str = ""
    aliases: tuple[str, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)
    evidence: tuple[SourceSpan, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_revision: str | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovedStoryIntelligence(BaseModel):
    """Project-persistent narrative intelligence and entity review decisions."""

    model_config = ConfigDict(frozen=True)

    story_id: str = Field(min_length=1)
    source_revision: str | None = None
    narrative_metadata: AINarrativeMetadata = Field(default_factory=AINarrativeMetadata)
    decisions: tuple[StoryEntityDecision, ...] = ()
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def decision(self, candidate_id: str) -> StoryEntityDecision | None:
        return next(
            (item for item in self.decisions if item.candidate_id == candidate_id),
            None,
        )
