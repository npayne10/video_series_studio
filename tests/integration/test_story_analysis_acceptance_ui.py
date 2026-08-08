"""Qt integration coverage for Phase 18.2.10 Story Analysis acceptance reporting."""

from __future__ import annotations

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import (
    AcceptanceLevel,
    StoryAnalysisAcceptanceCheck,
    StoryAnalysisAcceptanceReport,
    StoryAnalysisCacheState,
)
from vscs.presentation.widgets.story_analysis_acceptance import StoryAnalysisAcceptanceDialog


class _Acceptance:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, story):
        self.calls += 1
        return StoryAnalysisAcceptanceReport(
            story_id=story.story_id,
            checks=(
                StoryAnalysisAcceptanceCheck(
                    check_id="cache",
                    title="Analysis revision",
                    level=AcceptanceLevel.PASS,
                    detail="Cached analysis matches the current Story revision.",
                ),
                StoryAnalysisAcceptanceCheck(
                    check_id="entity-review",
                    title="Human entity review",
                    level=AcceptanceLevel.WARNING,
                    detail="2 AI entity proposal(s) still await review.",
                ),
            ),
            cache_state=StoryAnalysisCacheState.CURRENT,
            analysis_version=3,
            provider="OpenAI",
            ready_for_shot_planning=False,
            ready_for_generation=False,
        )


def test_acceptance_dialog_renders_health_separately_from_readiness(qtbot) -> None:
    story = StoryRecord(
        story_id="STORY-001",
        title="Xorix Acceptance",
        source_type=StorySourceType.PLAIN_TEXT,
        source_path="story.txt",
    )
    service = _Acceptance()
    dialog = StoryAnalysisAcceptanceDialog(story, service)
    qtbot.addWidget(dialog)

    assert "PASSED WITH WARNINGS" in dialog.summary.text()
    assert "Provider: OpenAI" in dialog.metadata.text()
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 0).text() == "PASS"
    assert dialog.table.item(1, 0).text() == "WARNING"

    dialog.refresh_report()
    assert service.calls == 2
