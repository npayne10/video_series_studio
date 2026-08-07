"""Small UI affordance checks for Phase 18.2.5."""

from vscs.presentation.widgets.story_analysis_workspace import StoryAnalysisWorkspaceDialog


def test_story_analysis_workspace_exposes_expected_controls() -> None:
    assert hasattr(StoryAnalysisWorkspaceDialog, "rebuild_analysis")
    assert hasattr(StoryAnalysisWorkspaceDialog, "graph_view_zoom_in")
    assert hasattr(StoryAnalysisWorkspaceDialog, "graph_view_zoom_out")
    assert hasattr(StoryAnalysisWorkspaceDialog, "graph_view_fit")
