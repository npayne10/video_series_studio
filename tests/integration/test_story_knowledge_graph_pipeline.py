"""Integration tests for Phase 18.2.4 Story Knowledge Graph pipeline wiring."""

from vscs.application.story_analysis import (
    ANALYSIS_RESULT_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    StoryAnalysisRequest,
    StoryKnowledgeGraphStage,
    register_story_analysis,
)
from vscs.domain.story_analysis import AnalysisResult, StoryKnowledgeGraph
from vscs.infrastructure.services import ApplicationServices


STORY = """# Arrival

Commander James Spence stood beside Captain Cheryl Draker on the bridge.
\"Confirmed visual,\" Cheryl Draker said.
James frowned as the ship entered orbit.

# Discovery

Commander James Spence stared at the circular doorway in the mountain.
"""


def test_default_pipeline_publishes_analysis_and_knowledge_graph() -> None:
    services = ApplicationServices()
    pipeline = register_story_analysis(services)

    report = pipeline.analyze(
        StoryAnalysisRequest(story_id="xorix-trailer", source_text=STORY)
    )

    analysis = report.artifacts[ANALYSIS_RESULT_ARTIFACT]
    graph = report.artifacts[KNOWLEDGE_GRAPH_ARTIFACT]
    assert isinstance(analysis, AnalysisResult)
    assert isinstance(graph, StoryKnowledgeGraph)
    assert graph.story_id == analysis.story_id
    assert graph.nodes
    assert [result.stage_id for result in report.stage_results] == [
        "story.analysis.engine",
        "story.knowledge_graph",
    ]


def test_default_registry_contains_graph_stage_after_analysis_stage() -> None:
    services = ApplicationServices()
    pipeline = register_story_analysis(services)

    stages = pipeline.registry.enabled_stages()

    assert [stage.order for stage in stages] == sorted(stage.order for stage in stages)
    assert any(isinstance(stage, StoryKnowledgeGraphStage) for stage in stages)
    assert stages[-1].stage_id == "story.knowledge_graph"
