"""Composition helpers for the story-analysis framework."""

from __future__ import annotations

from vscs.application.story_analysis.contracts import StoryAnalysisEngine
from vscs.application.story_analysis.pipeline import StoryAnalysisPipeline
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.infrastructure.services import ApplicationServices


def register_story_analysis(
    services: ApplicationServices,
    registry: StoryAnalysisStageRegistry | None = None,
) -> StoryAnalysisPipeline:
    """Register the Phase 18.2 story-analysis framework in the service graph.

    The empty registry is intentional in Phase 18.2.1. Later increments register
    parsing, extraction, knowledge-graph, and persistence stages without changing
    consumers of the StoryAnalysisEngine contract.
    """

    selected_registry = registry or StoryAnalysisStageRegistry()
    services.register(StoryAnalysisStageRegistry, selected_registry)
    pipeline = StoryAnalysisPipeline(selected_registry)
    services.register(StoryAnalysisPipeline, pipeline)
    services.register(StoryAnalysisEngine, pipeline)
    return pipeline
