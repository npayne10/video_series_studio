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
from vscs.application.story_analysis.pipeline import StoryAnalysisPipeline
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.application.story_analysis.stages import (
    ANALYSIS_RESULT_ARTIFACT,
    StoryAnalysisEngineStage,
)

__all__ = [
    "ANALYSIS_RESULT_ARTIFACT",
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
    "StorySection",
    "StoryStructureParser",
    "StoryTokenizer",
    "TextSpan",
    "register_story_analysis",
]
