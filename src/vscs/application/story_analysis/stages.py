"""Concrete stages for the VSCS story-analysis pipeline."""

from __future__ import annotations

from vscs.application.story_analysis.contracts import AnalysisContext, StageResult
from vscs.application.story_analysis.engine import DeterministicStoryAnalyzer
from vscs.application.story_analysis.knowledge_graph import StoryKnowledgeGraphBuilder
from vscs.domain.story_analysis import AnalysisResult

ANALYSIS_RESULT_ARTIFACT = "story.analysis.result"
KNOWLEDGE_GRAPH_ARTIFACT = "story.knowledge_graph"


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


class StoryKnowledgeGraphStage:
    """Build and publish the Story Knowledge Graph from AnalysisResult."""

    stage_id = "story.knowledge_graph"
    order = 200
    enabled = True

    def __init__(self, builder: StoryKnowledgeGraphBuilder | None = None) -> None:
        self._builder = builder or StoryKnowledgeGraphBuilder()

    def analyze(self, context: AnalysisContext) -> StageResult:
        analysis = context.artifacts.get(ANALYSIS_RESULT_ARTIFACT)
        if not isinstance(analysis, AnalysisResult):
            raise RuntimeError("Story Knowledge Graph requires story.analysis.result")
        graph = self._builder.build(analysis)
        return StageResult(
            stage_id=self.stage_id,
            artifacts={KNOWLEDGE_GRAPH_ARTIFACT: graph},
            diagnostics=(
                f"Built Story Knowledge Graph with {len(graph.nodes)} nodes "
                f"and {len(graph.edges)} edges",
            ),
        )
