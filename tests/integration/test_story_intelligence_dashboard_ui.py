"""Qt integration coverage for Phase 18.2.8 Story Intelligence dashboard."""

from __future__ import annotations

from pathlib import Path

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import (
    AI_ENTITY_RESOLUTION_ARTIFACT,
    KNOWLEDGE_GRAPH_ARTIFACT,
    AnalysisStatus,
    ApprovedStoryIntelligenceService,
    StoryAnalysisReport,
    StoryIntelligenceDashboardService,
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
from vscs.presentation.widgets.story_intelligence_dashboard import (
    StoryIntelligenceDashboardDialog,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Assets:
    def __init__(self, root: Path) -> None:
        self.projects = _Projects(root)
        self._asset = Asset(
            id=1,
            asset_id="CAP-CHR-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            description="",
            status=AssetStatus.APPROVED,
            file_path=None,
            tags=("xpd:cap_status=Locked",),
        )

    def list(self, **_kwargs) -> tuple[Asset, ...]:
        return (self._asset,)


class _Engine:
    def __init__(self, report: StoryAnalysisReport) -> None:
        self.report = report

    def analyze(self, _request) -> StoryAnalysisReport:
        return self.report


def _report() -> StoryAnalysisReport:
    candidate = EntityCandidate(
        candidate_id="candidate:character:james-spence",
        name="James Spence",
        category=EntityResolutionCategory.CHARACTER,
        confidence=0.98,
        review_status=CandidateReviewStatus.APPROVED,
        match_kind=ResolutionMatchKind.EXISTING,
        matched_asset_id="CAP-CHR-001",
        matched_asset_name="Commander James Spence",
    )
    resolution = EntityResolutionResult(
        story_id="STORY-001",
        candidates=(candidate,),
        metadata=AINarrativeMetadata(
            summary="The Iron Horizon approaches Xorix.",
            themes=("discovery",),
            confidence=0.95,
        ),
    )
    return StoryAnalysisReport(
        story_id="STORY-001",
        status=AnalysisStatus.COMPLETED,
        stage_results=(),
        artifacts={
            AI_ENTITY_RESOLUTION_ARTIFACT: resolution,
            KNOWLEDGE_GRAPH_ARTIFACT: StoryKnowledgeGraph(story_id="STORY-001"),
        },
    )


def test_story_intelligence_dashboard_renders_operational_metrics(tmp_path: Path, qtbot) -> None:
    source = tmp_path / "xorix.txt"
    source.write_text("James Spence watched Xorix fill the viewport.", encoding="utf-8")
    story = StoryRecord(
        story_id="STORY-001",
        title="Xorix Trailer",
        source_type=StorySourceType.PLAIN_TEXT,
        source_path=str(source),
    )
    assets = _Assets(tmp_path)
    intelligence = ApprovedStoryIntelligenceService(assets)
    dashboard = StoryIntelligenceDashboardService(assets, intelligence)
    dialog = StoryIntelligenceDashboardDialog(
        story,
        _Engine(_report()),
        dashboard,
    )
    qtbot.addWidget(dialog)

    assert dialog.entity_table.rowCount() == 1
    assert dialog.entity_table.item(0, 2).text() == "James Spence"
    assert dialog.entity_table.item(0, 5).text() == "CAP-CHR-001"
    assert dialog.xpd_progress.value() == 100
    assert dialog.cap_progress.value() == 100
    assert "READY" in dialog.readiness_label.text()
    assert "The Iron Horizon approaches Xorix." in dialog.narrative_view.toPlainText()

    dialog.filter_combo.setCurrentText("CAP Required")
    assert dialog.entity_table.rowCount() == 0
