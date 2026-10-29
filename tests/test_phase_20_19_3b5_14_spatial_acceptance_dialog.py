"""B.5.14 offline operator entry has no generation dependency."""

from unittest.mock import Mock

from vscs.application.caps.spatial_acceptance import AcceptanceScenario
from vscs.presentation.dialogs.story_cap_batch_dialog import StoryCAPBatchDialog


def test_offline_acceptance_controls_have_three_local_scenarios(qtbot, monkeypatch):
    generator = Mock()
    generator.caps.assets.projects.project_directory = None
    monkeypatch.setattr(
        "vscs.presentation.dialogs.story_cap_batch_dialog.StoryLifecycleService",
        lambda _projects: Mock(list_stories=lambda: ()),
    )
    monkeypatch.setattr(
        "vscs.presentation.dialogs.story_cap_batch_dialog.StoryCAPSpecificationService",
        lambda *_args: Mock(),
    )
    dialog = StoryCAPBatchDialog(generator)
    qtbot.addWidget(dialog)
    assert dialog.acceptance_scenario.count() == 3
    assert dialog.acceptance_scenario.itemData(0) == AcceptanceScenario.VALID.value
    assert dialog.spatial_acceptance.isEnabled()
    assert not dialog.preview.isEnabled()
