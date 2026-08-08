"""Phase 18.2.10 Story Analysis integration and acceptance health checks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.story import StoryRecord
from vscs.domain.story_analysis import CandidateReviewStatus, EntityResolutionResult

from .cache import StoryAnalysisCacheService, StoryAnalysisCacheState
from .dashboard import StoryIntelligenceDashboardService
from .intelligence import ApprovedStoryIntelligenceService, StoryIntelligenceError
from .source_reader import StorySourceReader, StorySourceReadError
from .stages import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    ANALYSIS_RESULT_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
)


class AcceptanceLevel(StrEnum):
    """Severity level for one integration acceptance check."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass(frozen=True, slots=True)
class StoryAnalysisAcceptanceCheck:
    """One deterministic subsystem acceptance result."""

    check_id: str
    title: str
    level: AcceptanceLevel
    detail: str


@dataclass(frozen=True, slots=True)
class StoryAnalysisAcceptanceReport:
    """End-to-end integration health and production readiness for one Story."""

    story_id: str
    checks: tuple[StoryAnalysisAcceptanceCheck, ...]
    cache_state: StoryAnalysisCacheState
    analysis_version: int
    provider: str
    ready_for_shot_planning: bool
    ready_for_generation: bool

    @property
    def failed(self) -> tuple[StoryAnalysisAcceptanceCheck, ...]:
        return tuple(check for check in self.checks if check.level is AcceptanceLevel.FAIL)

    @property
    def warnings(self) -> tuple[StoryAnalysisAcceptanceCheck, ...]:
        return tuple(check for check in self.checks if check.level is AcceptanceLevel.WARNING)

    @property
    def passed(self) -> bool:
        return not self.failed


class StoryAnalysisAcceptanceService:
    """Validate the integrated Story Analysis subsystem without executing AI."""

    def __init__(
        self,
        cache: StoryAnalysisCacheService,
        intelligence: ApprovedStoryIntelligenceService,
        dashboard: StoryIntelligenceDashboardService,
        *,
        source_reader: StorySourceReader | None = None,
    ) -> None:
        self.cache = cache
        self.intelligence = intelligence
        self.dashboard = dashboard
        self.source_reader = source_reader or StorySourceReader()

    def evaluate(self, story: StoryRecord) -> StoryAnalysisAcceptanceReport:
        """Run read-only integration checks against persisted Story Analysis artifacts."""
        checks: list[StoryAnalysisAcceptanceCheck] = []
        try:
            source_text = self.source_reader.read(story)
        except StorySourceReadError as exc:
            checks.append(
                self._check(
                    "source",
                    "Story source readable",
                    AcceptanceLevel.FAIL,
                    str(exc),
                )
            )
            return StoryAnalysisAcceptanceReport(
                story_id=story.story_id,
                checks=tuple(checks),
                cache_state=StoryAnalysisCacheState.MISSING,
                analysis_version=0,
                provider="Unknown",
                ready_for_shot_planning=False,
                ready_for_generation=False,
            )

        checks.append(
            self._check(
                "source",
                "Story source readable",
                AcceptanceLevel.PASS,
                "Story source loaded successfully.",
            )
        )
        status = self.cache.status(story, source_text)
        if status.state is StoryAnalysisCacheState.MISSING:
            checks.append(
                self._check(
                    "cache",
                    "Persisted analysis cache",
                    AcceptanceLevel.FAIL,
                    "No persisted Story Analysis exists. Choose Analyse Story.",
                )
            )
            return StoryAnalysisAcceptanceReport(
                story_id=story.story_id,
                checks=tuple(checks),
                cache_state=status.state,
                analysis_version=status.analysis_version,
                provider=status.provider,
                ready_for_shot_planning=False,
                ready_for_generation=False,
            )

        cache_level = (
            AcceptanceLevel.PASS
            if status.state is StoryAnalysisCacheState.CURRENT
            else AcceptanceLevel.WARNING
        )
        cache_detail = (
            "Cached analysis matches the current Story revision."
            if status.state is StoryAnalysisCacheState.CURRENT
            else "Cached analysis is stale; explicitly reanalyse before relying on it for production."
        )
        checks.append(self._check("cache", "Analysis revision", cache_level, cache_detail))

        try:
            report = self.cache.load(story, source_text, allow_stale=True)
        except Exception as exc:
            checks.append(
                self._check(
                    "cache-integrity",
                    "Cached artifact integrity",
                    AcceptanceLevel.FAIL,
                    str(exc),
                )
            )
            return StoryAnalysisAcceptanceReport(
                story_id=story.story_id,
                checks=tuple(checks),
                cache_state=status.state,
                analysis_version=status.analysis_version,
                provider=status.provider,
                ready_for_shot_planning=False,
                ready_for_generation=False,
            )

        required_artifacts = (
            (ANALYSIS_RESULT_ARTIFACT, "Deterministic analysis artifact"),
            (AI_ENTITY_RESOLUTION_ARTIFACT, "AI entity-resolution artifact"),
            (KNOWLEDGE_GRAPH_ARTIFACT, "Story Knowledge Graph artifact"),
        )
        for artifact_id, title in required_artifacts:
            present = artifact_id in report.artifacts
            checks.append(
                self._check(
                    f"artifact:{artifact_id}",
                    title,
                    AcceptanceLevel.PASS if present else AcceptanceLevel.FAIL,
                    "Persisted and readable." if present else "Required cached artifact is missing.",
                )
            )

        provider_level = AcceptanceLevel.PASS if status.provider != "Unknown" else AcceptanceLevel.WARNING
        checks.append(
            self._check(
                "provider",
                "Analysis provider recorded",
                provider_level,
                f"Provider: {status.provider}",
            )
        )

        resolution = report.artifacts.get(AI_ENTITY_RESOLUTION_ARTIFACT)
        if isinstance(resolution, EntityResolutionResult):
            try:
                restored = self.intelligence.restore(resolution)
                persisted = self.intelligence.load(story.story_id)
            except StoryIntelligenceError as exc:
                checks.append(
                    self._check(
                        "intelligence",
                        "Approved Story Intelligence readable",
                        AcceptanceLevel.FAIL,
                        str(exc),
                    )
                )
            else:
                checks.append(
                    self._check(
                        "intelligence",
                        "Approved Story Intelligence readable",
                        AcceptanceLevel.PASS,
                        f"{len(persisted.decisions)} persisted entity decision(s).",
                    )
                )
                assets = {asset.asset_id for asset in self.intelligence.assets.list()}
                broken_links = tuple(
                    candidate
                    for candidate in restored.candidates
                    if candidate.review_status is CandidateReviewStatus.APPROVED
                    and (
                        candidate.matched_asset_id is None
                        or candidate.matched_asset_id not in assets
                    )
                )
                checks.append(
                    self._check(
                        "canonical-links",
                        "Approved canonical links",
                        AcceptanceLevel.FAIL if broken_links else AcceptanceLevel.PASS,
                        (
                            f"{len(broken_links)} approved entity link(s) are missing from the Asset registry."
                            if broken_links
                            else "Every approved entity resolves to a canonical Asset registry identity."
                        ),
                    )
                )

        snapshot = self.dashboard.build(report)
        review_level = AcceptanceLevel.PASS if snapshot.proposed_entities == 0 else AcceptanceLevel.WARNING
        checks.append(
            self._check(
                "entity-review",
                "Human entity review",
                review_level,
                (
                    "All AI entity proposals have been reviewed."
                    if snapshot.proposed_entities == 0
                    else f"{snapshot.proposed_entities} AI entity proposal(s) still await review."
                ),
            )
        )
        checks.append(
            self._check(
                "shot-planning",
                "Shot Planning readiness",
                AcceptanceLevel.PASS if snapshot.ready_for_shot_planning else AcceptanceLevel.WARNING,
                "Ready." if snapshot.ready_for_shot_planning else "; ".join(snapshot.readiness_reasons),
            )
        )
        checks.append(
            self._check(
                "generation",
                "Generation Asset readiness",
                AcceptanceLevel.PASS if snapshot.ready_for_generation else AcceptanceLevel.WARNING,
                (
                    "Ready."
                    if snapshot.ready_for_generation
                    else f"{snapshot.cap_required_assets} approved canonical asset(s) still require CAP readiness."
                ),
            )
        )

        return StoryAnalysisAcceptanceReport(
            story_id=story.story_id,
            checks=tuple(checks),
            cache_state=status.state,
            analysis_version=status.analysis_version,
            provider=status.provider,
            ready_for_shot_planning=snapshot.ready_for_shot_planning,
            ready_for_generation=snapshot.ready_for_generation,
        )

    @staticmethod
    def _check(
        check_id: str,
        title: str,
        level: AcceptanceLevel,
        detail: str,
    ) -> StoryAnalysisAcceptanceCheck:
        return StoryAnalysisAcceptanceCheck(
            check_id=check_id,
            title=title,
            level=level,
            detail=detail or "No additional detail.",
        )
