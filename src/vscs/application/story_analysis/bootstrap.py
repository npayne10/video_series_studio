"""Composition helpers for the story-analysis framework."""

from __future__ import annotations

from vscs.application.story_analysis.contracts import StoryAnalysisEngine
from vscs.application.story_analysis.pipeline import StoryAnalysisPipeline
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.application.story_analysis.stages import StoryAnalysisEngineStage
from vscs.infrastructure.services import ApplicationServices


def register_story_analysis(
    services: ApplicationServices,
    registry: StoryAnalysisStageRegistry | None = None,
) -> StoryAnalysisPipeline:
    """Register the story-analysis framework and default analysis engine stage."""

    selected_registry = registry if registry is not None else StoryAnalysisStageRegistry()
    if not selected_registry.contains(StoryAnalysisEngineStage.stage_id):
        selected_registry.register(StoryAnalysisEngineStage())
    services.register(StoryAnalysisStageRegistry, selected_registry)
    pipeline = StoryAnalysisPipeline(selected_registry)
    services.register(StoryAnalysisPipeline, pipeline)
    services.register(StoryAnalysisEngine, pipeline)
    return pipeline
