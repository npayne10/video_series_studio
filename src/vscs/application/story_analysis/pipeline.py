"""Deterministic orchestration for story-analysis stages."""

from __future__ import annotations

from vscs.application.story_analysis.contracts import (
    AnalysisContext,
    AnalysisStatus,
    StageResult,
    StoryAnalysisReport,
    StoryAnalysisRequest,
)
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry


class StoryAnalysisPipeline:
    """Runs registered stages while preserving traceable intermediate artifacts."""

    def __init__(self, registry: StoryAnalysisStageRegistry) -> None:
        self._registry = registry

    @property
    def registry(self) -> StoryAnalysisStageRegistry:
        return self._registry

    def analyze(self, request: StoryAnalysisRequest) -> StoryAnalysisReport:
        context = AnalysisContext(request=request)
        stage_results: list[StageResult] = []
        diagnostics: list[str] = []

        for stage in self._registry.enabled_stages():
            try:
                result = stage.analyze(context)
            except Exception as error:
                diagnostic = (
                    f"Story analysis stage '{stage.stage_id}' failed: "
                    f"{type(error).__name__}: {error}"
                )
                diagnostics.append(diagnostic)
                return StoryAnalysisReport(
                    story_id=request.story_id,
                    status=AnalysisStatus.FAILED,
                    stage_results=tuple(stage_results),
                    artifacts=context.artifacts,
                    diagnostics=tuple(diagnostics),
                )

            if result.stage_id != stage.stage_id:
                diagnostic = (
                    f"Story analysis stage '{stage.stage_id}' returned mismatched "
                    f"result id '{result.stage_id}'"
                )
                diagnostics.append(diagnostic)
                return StoryAnalysisReport(
                    story_id=request.story_id,
                    status=AnalysisStatus.FAILED,
                    stage_results=tuple(stage_results),
                    artifacts=context.artifacts,
                    diagnostics=tuple(diagnostics),
                )

            stage_results.append(result)
            diagnostics.extend(result.diagnostics)
            if result.status is AnalysisStatus.FAILED:
                return StoryAnalysisReport(
                    story_id=request.story_id,
                    status=AnalysisStatus.FAILED,
                    stage_results=tuple(stage_results),
                    artifacts=context.artifacts,
                    diagnostics=tuple(diagnostics),
                )
            if result.status is AnalysisStatus.COMPLETED:
                context = context.with_artifacts(result.artifacts)

        return StoryAnalysisReport(
            story_id=request.story_id,
            status=AnalysisStatus.COMPLETED,
            stage_results=tuple(stage_results),
            artifacts=context.artifacts,
            diagnostics=tuple(diagnostics),
        )
