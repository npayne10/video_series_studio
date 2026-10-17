"""Checkpoint 4B: governed Episode UI coverage matrix remains fail closed."""

from types import SimpleNamespace
from unittest.mock import Mock

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_unregistered_authority_blocks_coverage(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.resolve_coverage()
    assert "services unavailable" in workspace.coverage_status.text()
    assert not workspace.complete_button.isEnabled()


def test_governed_episode_selection_lists_registered_plans(qtbot, tmp_path):
    episodes = Mock()
    episodes.list_plans.return_value = (
        SimpleNamespace(episode_id="EP-001", title="First Episode"),
    )
    workspace = EpisodeAssemblyWorkspace(
        lambda: tmp_path,
        authority_services=lambda: (episodes, Mock(), Mock(), Mock()),
    )
    qtbot.addWidget(workspace)
    workspace.discover_episodes()
    assert workspace.episode_selector.count() == 2
    assert workspace.episode_selector.itemData(1) == "EP-001"
    assert not workspace.complete_button.isEnabled()


def test_missing_shots_display_in_coverage_matrix(qtbot, tmp_path):
    episodes, scenes, shots, reviews = Mock(), Mock(), Mock(), Mock()
    episodes.list_plans.return_value = (
        SimpleNamespace(episode_id="EP-001", title="First Episode"),
    )
    episodes.plan.return_value = SimpleNamespace(production_ready=True)
    scenes.list_plans.return_value = (SimpleNamespace(scene_id="SCN-001"),)
    scenes.is_production_ready.return_value = True
    shots.list_plans.return_value = (SimpleNamespace(shot_id="SHT-001"),)
    shots.is_production_ready.return_value = True
    reviews.review.return_value = SimpleNamespace(status="approved")
    reviews.is_production_ready.return_value = True
    workspace = EpisodeAssemblyWorkspace(
        lambda: tmp_path,
        authority_services=lambda: (episodes, scenes, shots, reviews),
    )
    qtbot.addWidget(workspace)
    workspace.discover_episodes()
    workspace.episode_selector.setCurrentIndex(1)
    workspace.resolve_coverage()
    assert workspace.coverage_table.rowCount() == 1
    assert workspace.coverage_table.item(0, 0).text() == "SHT-001"
    assert workspace.coverage_table.item(0, 2).text() == "No media record"
    assert workspace.coverage_table.item(0, 3).text() == "Not in timeline"
    assert "BLOCKED" in workspace.coverage_status.text()
    assert not workspace.complete_button.isEnabled()
