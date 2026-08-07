"""Concrete analysis stages introduced by Phase 18.2.3."""

from __future__ import annotations

from vscs.application.story_analysis.contracts import AnalysisContext, StageResult
from vscs.application.story_analysis.engine import DeterministicStoryAnalyzer

ANALYSIS_RESULT_ARTIFACT = "story.analysis.result"


class StoryAnalysisEngineStage:
    """Run deterministic source analysis and publish the structured Story Model."""

    stage_id = "story.analysis.engine"
    order = 100
    enabled = True

    def __init__(self, analyzer: DeterministicStoryAnalyzer | None = None) -> None:
        self._analyzer = analyzer or DeterministicStoryAnalyzer()

    def analyze(self, context: AnalysisContext) -> StageResult:
        result = self._analyzer.analyze(context.request)
        return StageResult(
            stage_id=self.stage_id,
            artifacts={ANALYSIS_RESULT_ARTIFACT: result},
            diagnostics=result.diagnostics,
        )
