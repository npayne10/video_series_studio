"""Qt coverage for the Phase 18.2.6 AI entity review surface."""

from pathlib import Path

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import (
    EntityResolutionService,
    StoryAnalysisStageRegistry,
    register_story_analysis,
)
from vscs.infrastructure.ai import TemplateStoryAIAnalysisProvider
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.widgets.story_ai_entity_review import AIEntityReviewDialog


def test_ai_entity_review_lists_and_approves_candidate(tmp_path: Path, qtbot) -> None:
    source = tmp_path / "xorix.txt"
    source.write_text("Commander James Spence stood on the bridge.", encoding="utf-8")
    story = StoryRecord(
        story_id="STORY-001",
        title="Xorix",
        source_type=StorySourceType.PLAIN_TEXT,
        source_path=str(source),
    )
    services = ApplicationServices()
    resolution = EntityResolutionService(TemplateStoryAIAnalysisProvider())
    pipeline = register_story_analysis(
        services,
        StoryAnalysisStageRegistry(),
        entity_resolution=resolution,
    )
    dialog = AIEntityReviewDialog(story, pipeline)
    qtbot.addWidget(dialog)

    assert dialog.table.rowCount() >= 1
    dialog.table.selectRow(0)
    dialog._approve()

    assert dialog.table.item(0, 0).text() == "approved"
    assert "awaiting review" in dialog.summary.text()
