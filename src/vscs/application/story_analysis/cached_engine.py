"""Cache-only Story Analysis engine used by read/review presentation surfaces."""

from __future__ import annotations

from vscs.application.story import StoryRecord

from .cache import StoryAnalysisCacheService
from .contracts import StoryAnalysisReport, StoryAnalysisRequest


class CachedStoryAnalysisEngine:
    """Satisfy the analysis engine contract without executing analysis or AI stages."""

    def __init__(self, cache: StoryAnalysisCacheService, story: StoryRecord) -> None:
        self.cache = cache
        self.story = story

    def analyze(self, request: StoryAnalysisRequest) -> StoryAnalysisReport:
        """Return persisted analysis for the owning Story, even when it is stale."""
        return self.cache.load(self.story, request.source_text, allow_stale=True)
