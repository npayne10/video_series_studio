"""Qt coverage for the Phase 18.2.5 Story Analysis UI."""

from __future__ import annotations

from vscs.application.story import StoryRecord, StorySourceType
from vscs.application.story_analysis import StoryAnalysisStageRegistry
from vscs.application.story_analysis.bootstrap import register_story_analysis
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.widgets.story_analysis_workspace import StoryAnalysisWorkspaceDialog


TRAILER = """# Arrival

Commander James Spence stood beside the viewport on the Iron Horizon.
Captain Cheryl Draker watched Xorix below.
\"Confirmed visual,\" Cheryl Draker said.
James frowned as the ship entered the atmosphere.

# Discovery

Commander James Spence stared at the circular doorway.
"""


def _dialog(tmp_path, qtbot) -> StoryAnalysisWorkspaceDialog:
    source = tmp_path / "xorix-trailer.txt"
    source.write_text(TRAILER, encoding="utf-8")
    story = StoryRecord(
        story_id="STORY-001",
        title="Xorix Trailer Test Story",
        source_type=StorySourceType.PLAIN_TEXT,
        source_path=str(source),
        updated_at="test-revision",
    )
    services = ApplicationServices()
    engine = register_story_analysis(services, StoryAnalysisStageRegistry())
    dialog = StoryAnalysisWorkspaceDialog(story, engine)
    qtbot.addWidget(dialog)
    return dialog


def test_analysis_workspace_displays_source_inspector_graph_and_diagnostics(
    tmp_path,
    qtbot,
) -> None:
    dialog = _dialog(tmp_path, qtbot)

    assert dialog.analysis is not None
    assert dialog.graph is not None
    assert "Commander James Spence" in dialog.source_view.toPlainText()
    assert dialog.inspector.topLevelItemCount() > 0
    assert dialog.graph_view.scene() is not None
    assert dialog.graph_view.scene().items()
    assert dialog.diagnostics.count() > 0
    assert "Analysis complete" in dialog.status_label.text()


def test_analysis_workspace_search_and_filter_narrow_inspector(tmp_path, qtbot) -> None:
    dialog = _dialog(tmp_path, qtbot)

    dialog.filter_combo.setCurrentText("Characters")
    dialog.search_edit.setText("James")

    assert dialog.inspector.topLevelItemCount() == 1
    group = dialog.inspector.topLevelItem(0)
    assert group.text(0) == "Characters"
    assert group.childCount() >= 1
    assert any("James" in group.child(index).text(0) for index in range(group.childCount()))


def test_analysis_source_view_is_read_only(tmp_path, qtbot) -> None:
    dialog = _dialog(tmp_path, qtbot)

    assert dialog.source_view.isReadOnly()
