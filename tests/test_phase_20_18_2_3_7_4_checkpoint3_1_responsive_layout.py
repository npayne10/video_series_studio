"""Checkpoint 3.1: responsive, independently scrollable Episode Assembly."""

from unittest.mock import Mock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSplitter

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_episode_assembly_uses_two_independently_scrollable_panels(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    splitter = workspace.findChild(QSplitter, "episodeAssemblyResponsiveSplitter")
    assert splitter is not None
    assert splitter.orientation() == Qt.Orientation.Horizontal
    assert splitter.count() == 2
    coverage = workspace.findChild(QScrollArea, "episodeAssemblyCoverageScroll")
    timeline = workspace.findChild(QScrollArea, "episodeAssemblyTimelineScroll")
    assert coverage is not None and timeline is not None
    assert coverage.widgetResizable() and timeline.widgetResizable()
    assert coverage.widget() is workspace.coverage_panel
    assert timeline.widget() is workspace.timeline_panel
    assert workspace.coverage_panel.isAncestorOf(workspace.coverage_table)
    assert workspace.timeline_panel.isAncestorOf(workspace.successor_comparison)
    assert workspace.timeline_panel.isAncestorOf(workspace.persisted_revisions)
    assert not workspace.complete_button.isEnabled()
    assert not workspace.successor_publish_button.isEnabled()


def test_responsive_splitter_has_saved_layout_callback(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._layout_settings = Mock()
    workspace._save_splitter_layout()
    workspace._layout_settings.setValue.assert_called_once()
