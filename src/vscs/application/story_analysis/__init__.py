"""Public API for the VSCS story-analysis framework."""

from vscs.application.story_analysis.acceptance import (
    AcceptanceLevel,
    StoryAnalysisAcceptanceCheck,
    StoryAnalysisAcceptanceReport,
    StoryAnalysisAcceptanceService,
)
from vscs.application.story_analysis.ai_analysis import (
    AssetServiceStoryEntityCatalog,
    EmptyStoryEntityCatalog,
    EntityResolutionService,
    ExistingAssetReference,
    StoryAIAnalysisProvider,
    StoryEntityCatalog,
)
from vscs.application.story_analysis.bootstrap import register_story_analysis
from vscs.application.story_analysis.cache import (
    StoryAnalysisCacheError,
    StoryAnalysisCacheService,
    StoryAnalysisCacheState,
    StoryAnalysisCacheStatus,
)
from vscs.application.story_analysis.cached_engine import CachedStoryAnalysisEngine
from vscs.application.story_analysis.contracts import (
    AnalysisContext,
    AnalysisStatus,
    StageResult,
    StoryAnalysisEngine,
    StoryAnalysisReport,
    StoryAnalysisRequest,
    StoryAnalysisStage,
)
from vscs.application.story_analysis.dashboard import (
    StoryIntelligenceDashboardService,
    StoryIntelligenceDashboardSnapshot,
    StoryIntelligenceEntityRow,
    StoryProductionReadiness,
)
from vscs.application.story_analysis.engine import (
    DeterministicStoryAnalyzer,
    StorySection,
    StoryStructureParser,
    StoryTokenizer,
    TextSpan,
)
from vscs.application.story_analysis.intelligence import (
    ApprovedStoryIntelligenceService,
    ApprovedStoryIntelligenceStore,
    StoryIntelligenceError,
)
from vscs.application.story_analysis.knowledge_graph import StoryKnowledgeGraphBuilder
from vscs.application.story_analysis.pipeline import StoryAnalysisPipeline
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.application.story_analysis.source_reader import StorySourceReader, StorySourceReadError
from vscs.application.story_analysis.stages import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    ANALYSIS_RESULT_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    AIStoryAnalysisStage,
    StoryAnalysisEngineStage,
    StoryKnowledgeGraphStage,
)

STORY_KNOWLEDGE_GRAPH_ARTIFACT = KNOWLEDGE_GRAPH_ARTIFACT

__all__ = [
    "AI_ENTITY_RESOLUTION_ARTIFACT",
    "ANALYSIS_RESULT_ARTIFACT",
    "KNOWLEDGE_GRAPH_ARTIFACT",
    "STORY_KNOWLEDGE_GRAPH_ARTIFACT",
    "AIStoryAnalysisStage",
    "AcceptanceLevel",
    "AnalysisContext",
    "AnalysisStatus",
    "ApprovedStoryIntelligenceService",
    "ApprovedStoryIntelligenceStore",
    "AssetServiceStoryEntityCatalog",
    "CachedStoryAnalysisEngine",
    "DeterministicStoryAnalyzer",
    "EmptyStoryEntityCatalog",
    "EntityResolutionService",
    "ExistingAssetReference",
    "StageResult",
    "StoryAIAnalysisProvider",
    "StoryAnalysisAcceptanceCheck",
    "StoryAnalysisAcceptanceReport",
    "StoryAnalysisAcceptanceService",
    "StoryAnalysisCacheError",
    "StoryAnalysisCacheService",
    "StoryAnalysisCacheState",
    "StoryAnalysisCacheStatus",
    "StoryAnalysisEngine",
    "StoryAnalysisEngineStage",
    "StoryAnalysisPipeline",
    "StoryAnalysisReport",
    "StoryAnalysisRequest",
    "StoryAnalysisStage",
    "StoryAnalysisStageRegistry",
    "StoryEntityCatalog",
    "StoryIntelligenceDashboardService",
    "StoryIntelligenceDashboardSnapshot",
    "StoryIntelligenceEntityRow",
    "StoryIntelligenceError",
    "StoryKnowledgeGraphBuilder",
    "StoryKnowledgeGraphStage",
    "StoryProductionReadiness",
    "StorySection",
    "StorySourceReadError",
    "StorySourceReader",
    "StoryStructureParser",
    "StoryTokenizer",
    "TextSpan",
    "register_story_analysis",
]
