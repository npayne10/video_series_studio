"""Tests for Phase 18.2.1 story-analysis framework contracts."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from vscs.application.story_analysis import (
    AnalysisContext,
    AnalysisStatus,
    StageResult,
    StoryAnalysisEngine,
    StoryAnalysisPipeline,
    StoryAnalysisRequest,
    StoryAnalysisStageRegistry,
    register_story_analysis,
)
from vscs.infrastructure.services import ApplicationServices


@dataclass(slots=True)
class FakeStage:
    stage_id: str
    order: int
    output_key: str
    enabled: bool = True
    fail: bool = False

    def analyze(self, context: AnalysisContext) -> StageResult:
        if self.fail:
            raise RuntimeError("test failure")
        return StageResult(
            stage_id=self.stage_id,
            artifacts={self.output_key: len(context.artifacts)},
        )


def test_request_rejects_blank_identity_and_source() -> None:
    with pytest.raises(ValueError, match="story_id"):
        StoryAnalysisRequest(story_id=" ", source_text="Story")
    with pytest.raises(ValueError, match="source_text"):
        StoryAnalysisRequest(story_id="story-1", source_text=" ")


def test_registry_orders_enabled_stages_deterministically() -> None:
    registry = StoryAnalysisStageRegistry(
        [
            FakeStage("third", 30, "third"),
            FakeStage("second-b", 20, "second-b"),
            FakeStage("disabled", 10, "disabled", enabled=False),
            FakeStage("second-a", 20, "second-a"),
        ]
    )

    assert [stage.stage_id for stage in registry.enabled_stages()] == [
        "second-a",
        "second-b",
        "third",
    ]


def test_registry_rejects_duplicate_stage_ids() -> None:
    registry = StoryAnalysisStageRegistry([FakeStage("parse", 10, "parse")])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeStage("parse", 20, "duplicate"))


def test_pipeline_passes_accumulated_artifacts_between_stages() -> None:
    registry = StoryAnalysisStageRegistry(
        [FakeStage("parse", 10, "document"), FakeStage("extract", 20, "entities")]
    )
    pipeline = StoryAnalysisPipeline(registry)

    report = pipeline.analyze(
        StoryAnalysisRequest(story_id="story-1", source_text="A short story.")
    )

    assert report.status is AnalysisStatus.COMPLETED
    assert report.artifacts == {"document": 0, "entities": 1}
    assert [result.stage_id for result in report.stage_results] == ["parse", "extract"]


def test_pipeline_stops_and_reports_stage_exception() -> None:
    registry = StoryAnalysisStageRegistry(
        [
            FakeStage("parse", 10, "document"),
            FakeStage("extract", 20, "entities", fail=True),
            FakeStage("graph", 30, "graph"),
        ]
    )

    report = StoryAnalysisPipeline(registry).analyze(
        StoryAnalysisRequest(story_id="story-1", source_text="A short story.")
    )

    assert report.status is AnalysisStatus.FAILED
    assert report.artifacts == {"document": 0}
    assert [result.stage_id for result in report.stage_results] == ["parse"]
    assert "extract" in report.diagnostics[0]
    assert "RuntimeError" in report.diagnostics[0]


def test_framework_registers_public_and_concrete_services() -> None:
    services = ApplicationServices()

    pipeline = register_story_analysis(services)

    assert services.require(StoryAnalysisStageRegistry) is pipeline.registry
    assert services.require(StoryAnalysisPipeline) is pipeline
    assert services.require(StoryAnalysisEngine) is pipeline
