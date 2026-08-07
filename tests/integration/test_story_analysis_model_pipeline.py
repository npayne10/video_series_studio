"""Integration tests connecting the Phase 18.2.2 model to the analysis framework."""

from vscs.application.story_analysis import (
    AnalysisContext,
    StageResult,
    StoryAnalysisPipeline,
    StoryAnalysisRequest,
    StoryAnalysisStageRegistry,
)
from vscs.domain.story_analysis import AnalysisResult, Character, SourceSpan


class ModelStage:
    """Small analysis stage that emits the Phase 18.2.2 aggregate."""

    stage_id = "story-model"
    order = 100
    enabled = True

    def analyze(self, context: AnalysisContext) -> StageResult:
        span = SourceSpan(
            story_id=context.request.story_id,
            source_revision=context.request.source_revision,
            start_offset=0,
            end_offset=len(context.request.source_text),
            excerpt=context.request.source_text,
        )
        result = AnalysisResult(
            story_id=context.request.story_id,
            source_revision=context.request.source_revision,
            entities=(
                Character(
                    entity_id="char-james",
                    name="James",
                    sources=(span,),
                ),
            ),
        )
        return StageResult(stage_id=self.stage_id, artifacts={"analysis_result": result})


def test_story_model_is_preserved_as_pipeline_artifact() -> None:
    """The framework can transport the typed story model without conversion."""
    registry = StoryAnalysisStageRegistry()
    registry.register(ModelStage())
    pipeline = StoryAnalysisPipeline(registry)

    report = pipeline.analyze(
        StoryAnalysisRequest(
            story_id="story-1",
            source_text="James entered the bridge.",
            source_revision="rev-4",
        )
    )

    result = report.artifacts["analysis_result"]
    assert isinstance(result, AnalysisResult)
    assert result.story_id == "story-1"
    assert result.entity("char-james") is not None
    assert result.entity("char-james").sources[0].source_revision == "rev-4"
