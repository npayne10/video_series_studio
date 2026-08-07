"""Integration coverage for the Phase 18.2.6 AI enrichment pipeline stage."""

from vscs.application.story_analysis import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    ANALYSIS_RESULT_ARTIFACT,
    AIStoryAnalysisStage,
    EntityResolutionService,
    StoryAnalysisEngineStage,
    StoryAnalysisPipeline,
    StoryAnalysisRequest,
    StoryAnalysisStageRegistry,
    StoryKnowledgeGraphStage,
)
from vscs.domain.story_analysis import EntityResolutionResult
from vscs.infrastructure.ai import TemplateStoryAIAnalysisProvider


def test_ai_stage_runs_between_baseline_and_knowledge_graph() -> None:
    registry = StoryAnalysisStageRegistry()
    registry.register(StoryAnalysisEngineStage())
    registry.register(
        AIStoryAnalysisStage(EntityResolutionService(TemplateStoryAIAnalysisProvider()))
    )
    registry.register(StoryKnowledgeGraphStage())
    pipeline = StoryAnalysisPipeline(registry)

    report = pipeline.analyze(
        StoryAnalysisRequest(
            story_id="STORY-001",
            source_text="Commander James Spence stood on the bridge.",
        )
    )

    assert [result.stage_id for result in report.stage_results] == [
        "story.analysis.engine",
        "story.analysis.ai_entity_resolution",
        "story.knowledge_graph",
    ]
    assert ANALYSIS_RESULT_ARTIFACT in report.artifacts
    enrichment = report.artifacts[AI_ENTITY_RESOLUTION_ARTIFACT]
    assert isinstance(enrichment, EntityResolutionResult)
    assert enrichment.candidates
