"""Integration tests for the concrete Story Analysis Engine stage."""

from vscs.application.story_analysis import (
    ANALYSIS_RESULT_ARTIFACT,
    StoryAnalysisRequest,
    StoryAnalysisStageRegistry,
    register_story_analysis,
)
from vscs.domain.story_analysis import AnalysisResult
from vscs.infrastructure.services import ApplicationServices


def test_default_story_analysis_registration_executes_engine_stage() -> None:
    services = ApplicationServices()
    pipeline = register_story_analysis(services)

    report = pipeline.analyze(
        StoryAnalysisRequest(
            story_id="trailer",
            source_text=(
                "# Arrival\n\n"
                "Commander James Spence stood on the bridge.\n"
                "Captain Cheryl Draker watched the planet.\n"
            ),
        )
    )

    assert report.status.value == "completed"
    assert ANALYSIS_RESULT_ARTIFACT in report.artifacts
    result = report.artifacts[ANALYSIS_RESULT_ARTIFACT]
    assert isinstance(result, AnalysisResult)
    assert result.story_id == "trailer"
    assert result.entities
    assert result.timeline_events


def test_custom_registry_keeps_registry_and_adds_default_stages() -> None:
    services = ApplicationServices()
    registry = StoryAnalysisStageRegistry()

    register_story_analysis(services, registry)

    stage_ids = tuple(stage.stage_id for stage in registry.enabled_stages())
    assert stage_ids == (
        "story.analysis.engine",
        "story.knowledge_graph",
    )
