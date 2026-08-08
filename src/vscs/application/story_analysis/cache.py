"""Persisted Story Analysis build artifacts with revision-aware invalidation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from time import perf_counter

from vscs.application.assets import AssetService
from vscs.application.story import StoryRecord
from vscs.domain.story_analysis import AnalysisResult, EntityResolutionResult, StoryKnowledgeGraph

from .contracts import AnalysisStatus, StageResult, StoryAnalysisEngine, StoryAnalysisReport, StoryAnalysisRequest
from .stages import AI_ENTITY_RESOLUTION_ARTIFACT, ANALYSIS_RESULT_ARTIFACT, KNOWLEDGE_GRAPH_ARTIFACT


class StoryAnalysisCacheError(RuntimeError):
    """Raised when a persisted Story Analysis artifact cannot be used."""


class StoryAnalysisCacheState(StrEnum):
    """Revision relationship between the current Story and cached analysis."""

    MISSING = "missing"
    CURRENT = "current"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class StoryAnalysisCacheStatus:
    story_id: str
    state: StoryAnalysisCacheState
    current_revision: str
    analysis_revision: str | None = None
    analysis_version: int = 0
    analyzed_at: str | None = None
    duration_seconds: float | None = None
    provider: str = "Unknown"

    @property
    def current(self) -> bool:
        return self.state is StoryAnalysisCacheState.CURRENT


class StoryAnalysisCacheService:
    """Execute Story Analysis explicitly and reuse its artifacts until inputs change."""

    DIRECTORY = "story_analysis_cache"
    SCHEMA_VERSION = 1

    def __init__(self, assets: AssetService, engine: StoryAnalysisEngine) -> None:
        self.assets = assets
        self.engine = engine

    def revision(self, story: StoryRecord, source_text: str) -> str:
        """Return a stable revision hash for every analysis-relevant Story input."""
        payload = "\n".join(
            (
                story.story_id,
                story.title,
                story.description,
                str(story.source_type),
                story.source_path,
                source_text,
            )
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    def status(self, story: StoryRecord, source_text: str) -> StoryAnalysisCacheStatus:
        current_revision = self.revision(story, source_text)
        payload = self._load_payload(story.story_id)
        if payload is None:
            return StoryAnalysisCacheStatus(
                story_id=story.story_id,
                state=StoryAnalysisCacheState.MISSING,
                current_revision=current_revision,
            )
        analysis_revision = str(payload.get("analysis_revision", "")) or None
        state = (
            StoryAnalysisCacheState.CURRENT
            if analysis_revision == current_revision
            else StoryAnalysisCacheState.STALE
        )
        return StoryAnalysisCacheStatus(
            story_id=story.story_id,
            state=state,
            current_revision=current_revision,
            analysis_revision=analysis_revision,
            analysis_version=int(payload.get("analysis_version", 0)),
            analyzed_at=str(payload.get("analyzed_at", "")) or None,
            duration_seconds=float(payload.get("duration_seconds", 0.0)),
            provider=str(payload.get("provider", "Unknown")),
        )

    def analyze(self, story: StoryRecord, source_text: str) -> StoryAnalysisReport:
        """Run the expensive pipeline once and atomically replace the cached build artifact."""
        revision = self.revision(story, source_text)
        previous = self._load_payload(story.story_id) or {}
        started = perf_counter()
        report = self.engine.analyze(
            StoryAnalysisRequest(
                story_id=story.story_id,
                source_text=source_text,
                source_revision=revision,
                metadata={"title": story.title, "source_path": story.source_path},
            )
        )
        duration = perf_counter() - started
        if report.status is not AnalysisStatus.COMPLETED:
            return report
        self._save_report(
            story,
            report,
            revision=revision,
            analysis_version=int(previous.get("analysis_version", 0)) + 1,
            duration_seconds=duration,
        )
        return report

    def load(self, story: StoryRecord, source_text: str, *, allow_stale: bool = True) -> StoryAnalysisReport:
        """Load cached artifacts without executing any analysis stage or AI provider."""
        payload = self._load_payload(story.story_id)
        if payload is None:
            raise StoryAnalysisCacheError("Story has not been analysed yet. Choose Analyse Story first.")
        current_revision = self.revision(story, source_text)
        cached_revision = str(payload.get("analysis_revision", ""))
        if not allow_stale and current_revision != cached_revision:
            raise StoryAnalysisCacheError("Story Analysis is out of date. Choose Reanalyse Story.")
        try:
            artifacts: dict[str, object] = {}
            if raw := payload.get("analysis_result"):
                artifacts[ANALYSIS_RESULT_ARTIFACT] = AnalysisResult.model_validate(raw)
            if raw := payload.get("ai_entity_resolution"):
                artifacts[AI_ENTITY_RESOLUTION_ARTIFACT] = EntityResolutionResult.model_validate(raw)
            if raw := payload.get("knowledge_graph"):
                artifacts[KNOWLEDGE_GRAPH_ARTIFACT] = StoryKnowledgeGraph.model_validate(raw)
            stage_results = tuple(
                StageResult(
                    stage_id=str(item["stage_id"]),
                    status=AnalysisStatus(str(item["status"])),
                    diagnostics=tuple(str(value) for value in item.get("diagnostics", [])),
                )
                for item in payload.get("stage_results", [])
            )
            return StoryAnalysisReport(
                story_id=story.story_id,
                status=AnalysisStatus(str(payload.get("status", AnalysisStatus.COMPLETED.value))),
                stage_results=stage_results,
                artifacts=artifacts,
                diagnostics=tuple(str(value) for value in payload.get("diagnostics", [])),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise StoryAnalysisCacheError(f"Cached Story Analysis is invalid: {exc}") from exc

    def _save_report(
        self,
        story: StoryRecord,
        report: StoryAnalysisReport,
        *,
        revision: str,
        analysis_version: int,
        duration_seconds: float,
    ) -> None:
        analysis = report.artifacts.get(ANALYSIS_RESULT_ARTIFACT)
        resolution = report.artifacts.get(AI_ENTITY_RESOLUTION_ARTIFACT)
        graph = report.artifacts.get(KNOWLEDGE_GRAPH_ARTIFACT)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "story_id": story.story_id,
            "analysis_revision": revision,
            "analysis_version": analysis_version,
            "analyzed_at": datetime.now(UTC).isoformat(),
            "duration_seconds": round(duration_seconds, 3),
            "provider": self._provider(report),
            "status": report.status.value,
            "diagnostics": list(report.diagnostics),
            "stage_results": [
                {
                    "stage_id": item.stage_id,
                    "status": item.status.value,
                    "diagnostics": list(item.diagnostics),
                }
                for item in report.stage_results
            ],
            "analysis_result": (
                analysis.model_dump(mode="json") if isinstance(analysis, AnalysisResult) else None
            ),
            "ai_entity_resolution": (
                resolution.model_dump(mode="json")
                if isinstance(resolution, EntityResolutionResult)
                else None
            ),
            "knowledge_graph": (
                graph.model_dump(mode="json") if isinstance(graph, StoryKnowledgeGraph) else None
            ),
        }
        path = self._path(story.story_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StoryAnalysisCacheError(f"Unable to persist Story Analysis cache: {exc}") from exc

    @staticmethod
    def _provider(report: StoryAnalysisReport) -> str:
        for diagnostic in report.diagnostics:
            if "OpenAI Story Analysis provider used" in diagnostic:
                return "OpenAI"
            if "Template AI Story Analysis provider used" in diagnostic:
                return "Template"
        return "Unknown"

    def _load_payload(self, story_id: str) -> dict[str, object] | None:
        path = self._path(story_id)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoryAnalysisCacheError(f"Unable to read Story Analysis cache: {exc}") from exc
        if not isinstance(value, dict):
            raise StoryAnalysisCacheError("Story Analysis cache must contain a JSON object")
        return value

    def _path(self, story_id: str):
        project = self.assets.projects.project_directory
        if project is None:
            raise StoryAnalysisCacheError("Open a VSCS project before using Story Analysis")
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", story_id).strip("._") or "story"
        return project / ".vscs" / self.DIRECTORY / f"{safe_id}.json"
