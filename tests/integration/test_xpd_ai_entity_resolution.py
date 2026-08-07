"""Integration coverage for XPD import feeding AI entity resolution."""

from __future__ import annotations

from pathlib import Path

from vscs.application.assets import XPDWorkbookImportService
from vscs.application.story_analysis.ai_analysis import (
    AssetServiceStoryEntityCatalog,
    EntityResolutionService,
)
from vscs.domain.story_analysis import (
    AIEntityProposal,
    AIStoryAnalysisDraft,
    AnalysisResult,
    EntityResolutionCategory,
    ResolutionMatchKind,
)

from tests.unit.test_xpd_workbook_import import _Assets, _row, _write_xpd


class _Provider:
    def analyze_story(self, *, story_id: str, source_text: str, baseline: AnalysisResult):
        return AIStoryAnalysisDraft(
            story_id=story_id,
            entities=(
                AIEntityProposal(
                    name="Iron Horizon",
                    category=EntityResolutionCategory.SHIP,
                    description="Survey vessel",
                    evidence_text=("Iron Horizon",),
                    confidence=0.99,
                ),
            ),
        )


def test_imported_xpd_asset_is_used_by_ai_entity_resolution(tmp_path: Path) -> None:
    workbook = tmp_path / "XPD.xlsx"
    _write_xpd(workbook, (_row("CAP-SHP-001", "Iron Horizon", "Ship"),))
    assets = _Assets(tmp_path)
    importer = XPDWorkbookImportService(assets)
    importer.apply(importer.preview(workbook))

    resolver = EntityResolutionService(
        _Provider(),
        AssetServiceStoryEntityCatalog(assets),
    )
    result = resolver.analyze(
        story_id="trailer",
        source_text="The Iron Horizon entered orbit.",
        baseline=AnalysisResult(story_id="trailer"),
    )

    candidate = result.candidates[0]
    assert candidate.match_kind is ResolutionMatchKind.EXISTING
    assert candidate.matched_asset_id == "CAP-SHP-001"
