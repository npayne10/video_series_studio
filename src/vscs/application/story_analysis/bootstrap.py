"""Composition helpers for the story-analysis framework."""

from __future__ import annotations

from vscs.application.story_analysis.ai_analysis import EntityResolutionService
from vscs.application.story_analysis.contracts import StoryAnalysisEngine
from vscs.application.story_analysis.pipeline import StoryAnalysisPipeline
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.application.story_analysis.stages import (
    AIStoryAnalysisStage,
    StoryAnalysisEngineStage,
    StoryKnowledgeGraphStage,
)
from vscs.infrastructure.services import ApplicationServices


def register_story_analysis(
    services: ApplicationServices,
    registry: StoryAnalysisStageRegistry | None = None,
    entity_resolution: EntityResolutionService | None = None,
) -> StoryAnalysisPipeline:
    """Register deterministic, optional AI, and knowledge-graph analysis stages."""

    selected_registry = registry if registry is not None else StoryAnalysisStageRegistry()
    defaults = [StoryAnalysisEngineStage()]
    if entity_resolution is not None:
        defaults.append(AIStoryAnalysisStage(entity_resolution))
    defaults.append(StoryKnowledgeGraphStage())
    for stage in defaults:
        if not selected_registry.contains(stage.stage_id):
            selected_registry.register(stage)
    services.register(StoryAnalysisStageRegistry, selected_registry)
    pipeline = StoryAnalysisPipeline(selected_registry)
    services.register(StoryAnalysisPipeline, pipeline)
    services.register(StoryAnalysisEngine, pipeline)
    if entity_resolution is not None:
        services.register(EntityResolutionService, entity_resolution)
    return pipeline
