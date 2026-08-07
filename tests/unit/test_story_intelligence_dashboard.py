"""Unit coverage for Phase 18.2.8 Story Intelligence production dashboard."""

from __future__ import annotations

from pathlib import Path

from vscs.application.story_analysis import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    AnalysisStatus,
    ApprovedStoryIntelligenceService,
    StoryAnalysisReport,
    StoryIntelligenceDashboardService,
    StoryProductionReadiness,
)
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.domain.story_analysis import (
    AINarrativeMetadata,
    CandidateReviewStatus,
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
    StoryKnowledgeGraph,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Assets:
    def __init__(self, root: Path, items: tuple[Asset, ...]) -> None:
        self.projects = _Projects(root)
        self._items = items

    def list(self, **_kwargs) -> tuple[Asset, ...]:
        return self._items


def _asset(
    asset_id: str,
    name: str,
    category: AssetCategory,
    cap_status: str,
) -> Asset:
    return Asset(
        id=1,
        asset_id=asset_id,
        name=name,
        category=category,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(f"xpd:cap_status={cap_status}",),
    )


def _candidate(
    name: str,
    category: EntityResolutionCategory,
    asset_id: str,
    status: CandidateReviewStatus,
) -> EntityCandidate:
    return EntityCandidate(
        candidate_id=f"candidate:{category.value}:{name.casefold().replace(' ', '-')}",
        name=name,
        category=category,
        confidence=0.9,
        review_status=status,
        match_kind=ResolutionMatchKind.EXISTING,
        matched_asset_id=asset_id,
        matched_asset_name=name,
    )


def _report(*candidates: EntityCandidate) -> StoryAnalysisReport:
    resolution = EntityResolutionResult(
        story_id="xorix-trailer",
        source_revision="rev-1",
        candidates=candidates,
        metadata=AINarrativeMetadata(
            summary="Arrival at Xorix",
            themes=("discovery",),
            tone=("awe",),
            setting=("Xorix orbit",),
            production_notes=("Maintain ship continuity",),
            confidence=0.92,
        ),
    )
    graph = StoryKnowledgeGraph(story_id="xorix-trailer")
    return StoryAnalysisReport(
        story_id="xorix-trailer",
        status=AnalysisStatus.COMPLETED,
        stage_results=(),
        artifacts={
            AI_ENTITY_RESOLUTION_ARTIFACT: resolution,
            KNOWLEDGE_GRAPH_ARTIFACT: graph,
        },
        diagnostics=("Dashboard fixture",),
    )


def test_dashboard_exposes_review_xpd_cap_and_readiness_metrics(tmp_path: Path) -> None:
    assets = _Assets(
        tmp_path,
        (
            _asset("CAP-CHR-001", "Commander James Spence", AssetCategory.CHARACTER, "Locked"),
            _asset("CAP-SHP-001", "Iron Horizon", AssetCategory.SHIP, "Review"),
            _asset("CAP-PLN-001", "Xorix", AssetCategory.PLANET, "Locked"),
        ),
    )
    intelligence = ApprovedStoryIntelligenceService(assets)
    dashboard = StoryIntelligenceDashboardService(assets, intelligence)

    snapshot = dashboard.build(
        _report(
            _candidate(
                "James Spence",
                EntityResolutionCategory.CHARACTER,
                "CAP-CHR-001",
                CandidateReviewStatus.APPROVED,
            ),
            _candidate(
                "Iron Horizon",
                EntityResolutionCategory.SHIP,
                "CAP-SHP-001",
                CandidateReviewStatus.APPROVED,
            ),
            _candidate(
                "Xorix",
                EntityResolutionCategory.PLANET,
                "CAP-PLN-001",
                CandidateReviewStatus.PROPOSED,
            ),
        )
    )

    assert snapshot.entity_total == 3
    assert snapshot.approved_entities == 2
    assert snapshot.proposed_entities == 1
    assert snapshot.matched_entities == 3
    assert snapshot.xpd_coverage_percent == 100
    assert snapshot.cap_ready_assets == 1
    assert snapshot.cap_required_assets == 1
    assert snapshot.ready_for_shot_planning is False
    assert snapshot.ready_for_generation is False
    assert snapshot.readiness is StoryProductionReadiness.BLOCKED
    assert "await review" in snapshot.readiness_reasons[0]
    assert snapshot.summary == "Arrival at Xorix"


def test_dashboard_marks_fully_reviewed_cap_ready_story_ready(tmp_path: Path) -> None:
    assets = _Assets(
        tmp_path,
        (
            _asset("CAP-CHR-001", "Commander James Spence", AssetCategory.CHARACTER, "Locked"),
        ),
    )
    intelligence = ApprovedStoryIntelligenceService(assets)
    dashboard = StoryIntelligenceDashboardService(assets, intelligence)

    snapshot = dashboard.build(
        _report(
            _candidate(
                "James Spence",
                EntityResolutionCategory.CHARACTER,
                "CAP-CHR-001",
                CandidateReviewStatus.APPROVED,
            )
        )
    )

    assert snapshot.ready_for_shot_planning is True
    assert snapshot.ready_for_generation is True
    assert snapshot.readiness is StoryProductionReadiness.READY
    assert snapshot.readiness_reasons == ()
    assert snapshot.entity_rows[0].action == "Ready"
