"""Public presentation exports for Story Analysis widgets."""

from vscs.presentation.widgets import StoryAnalysisWorkspaceDialog, StoryGraphView


def test_story_analysis_widgets_are_publicly_importable() -> None:
    assert StoryAnalysisWorkspaceDialog.__name__ == "StoryAnalysisWorkspaceDialog"
    assert StoryGraphView.__name__ == "StoryGraphView"
