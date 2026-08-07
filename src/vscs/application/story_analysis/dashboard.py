"""Operational Story Intelligence dashboard read model for production readiness."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.assets import AssetService
from vscs.application.story import StoryMetadataService
from vscs.application.story_analysis.contracts import AnalysisStatus, StoryAnalysisReport
from vscs.application.story_analysis.intelligence import ApprovedStoryIntelligenceService
from vscs.application.story_analysis.stages import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
)
from vscs.domain.story_analysis import (
    CandidateReviewStatus,
    EntityResolutionResult,
    ResolutionMatchKind,
    StoryKnowledgeGraph,
)


class StoryProductionReadiness(StrEnum):
    """Operational readiness level exposed by the Story Intelligence dashboard."""

    READY = "ready"
    ATTENTION = "attention"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StoryIntelligenceEntityRow:
    """One reviewable production entity projected for dashboard display."""

    candidate_id: str
    name: str
    category: str
    review_status: str
    confidence: float
    resolution: str
    canonical_asset_id: str | None
    canonical_asset_name: str | None
    cap_status: str
    cap_ready: bool
    action: str


@dataclass(frozen=True, slots=True)
class StoryIntelligenceDashboardSnapshot:
    """Complete non-canonical production-readiness projection for one Story."""

    story_id: str
    analysis_status: AnalysisStatus
    stage_count: int
    story_completeness_percent: int | None
    missing_story_metadata: tuple[str, ...]
    ai_confidence: float
    entity_total: int
    approved_entities: int
    proposed_entities: int
    rejected_entities: int
    matched_entities: int
    unresolved_entities: int
    xpd_coverage_percent: int
    cap_ready_assets: int
    cap_required_assets: int
    graph_nodes: int
    graph_edges: int
    readiness: StoryProductionReadiness
    ready_for_shot_planning: bool
    ready_for_generation: bool
    readiness_reasons: tuple[str, ...]
    entity_rows: tuple[StoryIntelligenceEntityRow, ...]
    summary: str
    themes: tuple[str, ...]
    tone: tuple[str, ...]
    setting: tuple[str, ...]
    production_notes: tuple[str, ...]
    diagnostics: tuple[str, ...]


class StoryIntelligenceDashboardService:
    """Build an operational dashboard from analysis, Story Intelligence and XPD canon."""

    _CAP_READY_VALUES = frozenset({"approved", "locked"})

    def __init__(
        self,
        assets: AssetService,
        intelligence: ApprovedStoryIntelligenceService,
        metadata: StoryMetadataService | None = None,
    ) -> None:
        self.assets = assets
        self.intelligence = intelligence
        self.metadata = metadata

    def build(self, report: StoryAnalysisReport) -> StoryIntelligenceDashboardSnapshot:
        resolution = report.artifacts.get(AI_ENTITY_RESOLUTION_ARTIFACT)
        graph = report.artifacts.get(KNOWLEDGE_GRAPH_ARTIFACT)
        if isinstance(resolution, EntityResolutionResult):
            resolution = self.intelligence.restore(resolution)
        else:
            resolution = None
        if not isinstance(graph, StoryKnowledgeGraph):
            graph = None

        assets = self._assets_by_id()
        rows = self._entity_rows(resolution, assets)
        active_rows = tuple(
            row for row in rows if row.review_status != CandidateReviewStatus.REJECTED.value
        )
        matched = sum(1 for row in active_rows if row.canonical_asset_id)
        coverage = round((matched / len(active_rows)) * 100) if active_rows else 100
        approved = sum(
            1 for row in rows if row.review_status == CandidateReviewStatus.APPROVED.value
        )
        proposed = sum(
            1 for row in rows if row.review_status == CandidateReviewStatus.PROPOSED.value
        )
        rejected = sum(
            1 for row in rows if row.review_status == CandidateReviewStatus.REJECTED.value
        )
        unresolved = sum(
            1
            for row in active_rows
            if row.review_status == CandidateReviewStatus.PROPOSED.value
            or row.resolution
            in {
                ResolutionMatchKind.POSSIBLE_DUPLICATE.value,
                ResolutionMatchKind.UNCERTAIN.value,
            }
        )
        approved_rows = tuple(
            row for row in rows if row.review_status == CandidateReviewStatus.APPROVED.value
        )
        cap_ready = sum(1 for row in approved_rows if row.cap_ready)
        cap_required = sum(
            1 for row in approved_rows if row.canonical_asset_id and not row.cap_ready
        )
        reasons = self._readiness_reasons(report, rows, resolution)
        planning_ready = not reasons
        generation_ready = planning_ready and cap_required == 0
        readiness = self._readiness(planning_ready, generation_ready)
        narrative = resolution.metadata if resolution is not None else None
        completeness_percent, missing_metadata = self._story_completeness(report.story_id)
        diagnostics = tuple(
            dict.fromkeys(
                (
                    *report.diagnostics,
                    *(resolution.diagnostics if resolution is not None else ()),
                )
            )
        )
        return StoryIntelligenceDashboardSnapshot(
            story_id=report.story_id,
            analysis_status=report.status,
            stage_count=len(report.stage_results),
            story_completeness_percent=completeness_percent,
            missing_story_metadata=missing_metadata,
            ai_confidence=narrative.confidence if narrative is not None else 0.0,
            entity_total=len(rows),
            approved_entities=approved,
            proposed_entities=proposed,
            rejected_entities=rejected,
            matched_entities=matched,
            unresolved_entities=unresolved,
            xpd_coverage_percent=coverage,
            cap_ready_assets=cap_ready,
            cap_required_assets=cap_required,
            graph_nodes=len(graph.nodes) if graph is not None else 0,
            graph_edges=len(graph.edges) if graph is not None else 0,
            readiness=readiness,
            ready_for_shot_planning=planning_ready,
            ready_for_generation=generation_ready,
            readiness_reasons=reasons,
            entity_rows=rows,
            summary=narrative.summary if narrative is not None else "",
            themes=narrative.themes if narrative is not None else (),
            tone=narrative.tone if narrative is not None else (),
            setting=narrative.setting if narrative is not None else (),
            production_notes=narrative.production_notes if narrative is not None else (),
            diagnostics=diagnostics,
        )

    def _assets_by_id(self) -> dict[str, object]:
        try:
            return {asset.asset_id: asset for asset in self.assets.list()}
        except Exception:
            return {}

    def _story_completeness(self, story_id: str) -> tuple[int | None, tuple[str, ...]]:
        if self.metadata is None:
            return None, ()
        try:
            completeness = self.metadata.completeness(story_id)
        except Exception:
            return None, ()
        return completeness.percentage, completeness.missing_fields

    def _entity_rows(self, resolution, assets) -> tuple[StoryIntelligenceEntityRow, ...]:
        if resolution is None:
            return ()
        rows: list[StoryIntelligenceEntityRow] = []
        for candidate in resolution.candidates:
            asset = assets.get(candidate.matched_asset_id) if candidate.matched_asset_id else None
            cap_status = self._cap_status(asset)
            cap_ready = cap_status.casefold() in self._CAP_READY_VALUES
            rows.append(
                StoryIntelligenceEntityRow(
                    candidate_id=candidate.candidate_id,
                    name=candidate.name,
                    category=candidate.category.value,
                    review_status=candidate.review_status.value,
                    confidence=candidate.confidence,
                    resolution=candidate.match_kind.value,
                    canonical_asset_id=candidate.matched_asset_id,
                    canonical_asset_name=candidate.matched_asset_name,
                    cap_status=cap_status,
                    cap_ready=cap_ready,
                    action=self._action(candidate, cap_ready),
                )
            )
        return tuple(rows)

    @staticmethod
    def _cap_status(asset) -> str:
        if asset is None:
            return "Not linked"
        for tag in asset.tags:
            prefix, separator, value = tag.partition("=")
            if separator and prefix.casefold() == "xpd:cap_status":
                return value or "Not defined"
        return "CAP required"

    @staticmethod
    def _action(candidate, cap_ready: bool) -> str:
        if candidate.review_status is CandidateReviewStatus.REJECTED:
            return "No action — rejected"
        if candidate.review_status is CandidateReviewStatus.PROPOSED:
            return "Review entity"
        if candidate.match_kind in {
            ResolutionMatchKind.POSSIBLE_DUPLICATE,
            ResolutionMatchKind.UNCERTAIN,
        }:
            return "Resolve XPD match"
        if candidate.matched_asset_id is None:
            return "Create/link canonical asset"
        if not cap_ready:
            return "Prepare/approve CAP"
        return "Ready"

    @staticmethod
    def _readiness_reasons(report, rows, resolution) -> tuple[str, ...]:
        reasons: list[str] = []
        if report.status is not AnalysisStatus.COMPLETED:
            reasons.append("Story Analysis has not completed successfully.")
        if resolution is None:
            reasons.append("AI Entity Resolution is unavailable.")
            return tuple(reasons)
        proposed = sum(
            1 for row in rows if row.review_status == CandidateReviewStatus.PROPOSED.value
        )
        if proposed:
            noun = "entity" if proposed == 1 else "entities"
            reasons.append(f"{proposed} AI {noun} await review.")
        ambiguous = sum(
            1
            for row in rows
            if row.review_status != CandidateReviewStatus.REJECTED.value
            and row.resolution
            in {
                ResolutionMatchKind.POSSIBLE_DUPLICATE.value,
                ResolutionMatchKind.UNCERTAIN.value,
            }
        )
        if ambiguous:
            noun = "entity has" if ambiguous == 1 else "entities have"
            reasons.append(f"{ambiguous} {noun} ambiguous XPD matching.")
        missing = sum(
            1
            for row in rows
            if row.review_status == CandidateReviewStatus.APPROVED.value
            and row.canonical_asset_id is None
        )
        if missing:
            noun = "entity lacks" if missing == 1 else "entities lack"
            reasons.append(f"{missing} approved {noun} a canonical asset.")
        return tuple(reasons)

    @staticmethod
    def _readiness(planning_ready: bool, generation_ready: bool) -> StoryProductionReadiness:
        if generation_ready:
            return StoryProductionReadiness.READY
        if planning_ready:
            return StoryProductionReadiness.ATTENTION
        return StoryProductionReadiness.BLOCKED
