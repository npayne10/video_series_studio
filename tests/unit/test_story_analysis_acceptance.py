"""Unit coverage for Phase 18.2.10 Story Analysis integration acceptance."""

from __future__ import annotations

from pathlib import Path

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    ANALYSIS_RESULT_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    AcceptanceLevel,
    AnalysisStatus,
    ApprovedStoryIntelligenceService,
    StoryAnalysisAcceptanceService,
    StoryAnalysisCacheService,
    StoryAnalysisCacheState,
    StoryAnalysisReport,
    StoryIntelligenceDashboardService,
)
from vscs.domain.story_analysis import AnalysisResult, EntityResolutionResult, StoryKnowledgeGraph


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Assets:
    def __init__(self, root: Path) -> None:
        self.projects = _Projects(root)

    def list(self, **_kwargs):
        return ()


class _Engine:
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


def _story(path: Path) -> StoryRecord:
    return StoryRecord(
        story_id="STORY-001",
        title="Xorix Acceptance",
        source_type=StorySourceType.PLAIN_TEXT,
        source_path=str(path),
    )


def _service(tmp_path: Path, engine: _Engine):
    assets = _Assets(tmp_path)
    cache = StoryAnalysisCacheService(assets, engine)
    intelligence = ApprovedStoryIntelligenceService(assets)
    dashboard = StoryIntelligenceDashboardService(assets, intelligence)
    return cache, StoryAnalysisAcceptanceService(cache, intelligence, dashboard)


def test_acceptance_reads_cached_artifacts_without_rerunning_engine(tmp_path: Path) -> None:
    source = tmp_path / "story.txt"
    source.write_text("Iron Horizon entered Xorix orbit.", encoding="utf-8")
    story = _story(source)
    engine = _Engine()
    cache, acceptance = _service(tmp_path, engine)

    cache.analyze(story, source.read_text(encoding="utf-8"))
    report = acceptance.evaluate(story)
    report_again = acceptance.evaluate(story)

    assert engine.calls == 1
    assert report.passed is True
    assert report_again.passed is True
    assert report.cache_state is StoryAnalysisCacheState.CURRENT
    assert report.provider == "OpenAI"
    assert not report.failed


def test_acceptance_marks_stale_revision_as_warning_not_integrity_failure(tmp_path: Path) -> None:
    source = tmp_path / "story.txt"
    source.write_text("Version one", encoding="utf-8")
    story = _story(source)
    engine = _Engine()
    cache, acceptance = _service(tmp_path, engine)

    cache.analyze(story, "Version one")
    source.write_text("Version two", encoding="utf-8")
    report = acceptance.evaluate(story)

    assert engine.calls == 1
    assert report.cache_state is StoryAnalysisCacheState.STALE
    assert report.passed is True
    assert any(check.level is AcceptanceLevel.WARNING for check in report.checks)


def test_acceptance_fails_cleanly_when_analysis_cache_is_missing(tmp_path: Path) -> None:
    source = tmp_path / "story.txt"
    source.write_text("Unanalysed Story", encoding="utf-8")
    story = _story(source)
    engine = _Engine()
    _cache, acceptance = _service(tmp_path, engine)

    report = acceptance.evaluate(story)

    assert engine.calls == 0
    assert report.passed is False
    assert report.cache_state is StoryAnalysisCacheState.MISSING
    assert any(check.check_id == "cache" for check in report.failed)
