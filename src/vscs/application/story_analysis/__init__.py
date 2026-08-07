"""Public API for the VSCS story-analysis framework."""

from vscs.application.story_analysis.bootstrap import register_story_analysis
from vscs.application.story_analysis.contracts import (
    AnalysisContext,
    AnalysisStatus,
    StageResult,
    StoryAnalysisEngine,
    StoryAnalysisReport,
    StoryAnalysisRequest,
    StoryAnalysisStage,
)
from vscs.application.story_analysis.engine import (
    DeterministicStoryAnalyzer,
    StorySection,
    StoryStructureParser,
    StoryTokenizer,
    TextSpan,
)
from vscs.application.story_analysis.knowledge_graph import StoryKnowledgeGraphBuilder
from vscs.application.story_analysis.pipeline import StoryAnalysisPipeline
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.application.story_analysis.source_reader import StorySourceReader, StorySourceReadError
from vscs.application.story_analysis.stages import (
    ANALYSIS_RESULT_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    StoryAnalysisEngineStage,
    StoryKnowledgeGraphStage,
)

STORY_KNOWLEDGE_GRAPH_ARTIFACT = KNOWLEDGE_GRAPH_ARTIFACT

__all__ = [
    "ANALYSIS_RESULT_ARTIFACT",
    "KNOWLEDGE_GRAPH_ARTIFACT",
    "STORY_KNOWLEDGE_GRAPH_ARTIFACT",
    "AnalysisContext",
    "AnalysisStatus",
    "DeterministicStoryAnalyzer",
    "StageResult",
    "StoryAnalysisEngine",
    "StoryAnalysisEngineStage",
    "StoryAnalysisPipeline",
    "StoryAnalysisReport",
    "StoryAnalysisRequest",
    "StoryAnalysisStage",
    "StoryAnalysisStageRegistry",
    "StoryKnowledgeGraphBuilder",
    "StoryKnowledgeGraphStage",
    "StorySection",
    "StorySourceReadError",
    "StorySourceReader",
    "StoryStructureParser",
    "StoryTokenizer",
    "TextSpan",
    "register_story_analysis",
]