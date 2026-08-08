"""Unit coverage for Phase 18.2.9 Story Analysis cache and revision control."""

from __future__ import annotations

from pathlib import Path

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    ANALYSIS_RESULT_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    AnalysisStatus,
    CachedStoryAnalysisEngine,
    StoryAnalysisCacheService,
    StoryAnalysisCacheState,
    StoryAnalysisReport,
)
from vscs.domain.story_analysis import AnalysisResult, EntityResolutionResult, StoryKnowledgeGraph


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Assets:
    def __init__(self, root: Path) -> None:
        self.projects = _Projects(root)


class _CountingEngine:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, request):
        self.calls += 1
        return StoryAnalysisReport(
            story_id=request.story_id,
            status=AnalysisStatus.COMPLETED,
            stage_results=(),
            artifacts={
                ANALYSIS_RESULT_ARTIFACT: AnalysisResult(
                    story_id=request.story_id,
                    source_revision=request.source_revision,
                ),
                AI_ENTITY_RESOLUTION_ARTIFACT: EntityResolutionResult(
                    story_id=request.story_id,
                    source_revision=request.source_revision,
                ),
                KNOWLEDGE_GRAPH_ARTIFACT: StoryKnowledgeGraph(
                    story_id=request.story_id,
                    source_revision=request.source_revision,
                ),
            },
            diagnostics=("OpenAI Story Analysis provider used",),
        )


def _story() -> StoryRecord:
    return StoryRecord(
        story_id="STORY-001",
        title="Xorix Short",
        source_type=StorySourceType.PLAIN_TEXT,
        source_path="xorix.txt",
    )


def test_analysis_runs_once_then_cached_engine_never_calls_provider(tmp_path: Path) -> None:
    engine = _CountingEngine()
    cache = StoryAnalysisCacheService(_Assets(tmp_path), engine)
    story = _story()
    source = "Iron Horizon entered Xorix orbit."

    cache.analyze(story, source)
    cached_engine = CachedStoryAnalysisEngine(cache, story)
    report = cached_engine.analyze(
        type(
            "Request",
            (),
            {"story_id": story.story_id, "source_text": source},
        )()
    )
    report_again = cached_engine.analyze(
        type(
            "Request",
            (),
            {"story_id": story.story_id, "source_text": source},
        )()
    )

    assert engine.calls == 1
    assert report.status is AnalysisStatus.COMPLETED
    assert report_again.status is AnalysisStatus.COMPLETED
    assert cache.status(story, source).state is StoryAnalysisCacheState.CURRENT
    assert cache.status(story, source).provider == "OpenAI"


def test_source_change_marks_cache_stale_without_rerunning_analysis(tmp_path: Path) -> None:
    engine = _CountingEngine()
    cache = StoryAnalysisCacheService(_Assets(tmp_path), engine)
    story = _story()

    cache.analyze(story, "Version one")
    status = cache.status(story, "Version two")

    assert status.state is StoryAnalysisCacheState.STALE
    assert status.analysis_version == 1
    assert engine.calls == 1


def test_explicit_reanalysis_advances_version_and_revision(tmp_path: Path) -> None:
    engine = _CountingEngine()
    cache = StoryAnalysisCacheService(_Assets(tmp_path), engine)
    story = _story()

    cache.analyze(story, "Version one")
    cache.analyze(story, "Version two")
    status = cache.status(story, "Version two")

    assert engine.calls == 2
    assert status.state is StoryAnalysisCacheState.CURRENT
    assert status.analysis_version == 2
    assert status.duration_seconds is not None
    assert status.analyzed_at is not None
