"""Phase 20.18.2.3.7.3 Shot-set UI preview and approval barrier tests."""

from PySide6.QtWidgets import QPushButton

from vscs.presentation.widgets.episode_shots_complete_dialog import (
    EpisodeShotsCompleteDialog,
)


def test_dialog_opens_fail_closed_without_assembly_revision(qtbot, tmp_path):
    dialog = EpisodeShotsCompleteDialog(tmp_path)
    qtbot.addWidget(dialog)
    assert dialog.objectName() == "episode_shots_complete_dialog"
    button = dialog.findChild(QPushButton, "shot_set_declare_complete")
    assert button is not None
    assert not button.isEnabled()

    dialog.assembly_id.setText("ASM-MISSING")
    dialog.revision_id.setText("REV-MISSING")
    dialog.expected_shots.setText("SHT-001")
    dialog.operator_id.setText("operator")
    dialog.refresh_readiness()

    assert "BLOCKED" in dialog.status.text()
    assert not button.isEnabled()


def test_manual_operator_input_does_not_enable_completion(qtbot, tmp_path):
    dialog = EpisodeShotsCompleteDialog(tmp_path)
    qtbot.addWidget(dialog)
    button = dialog.findChild(QPushButton, "shot_set_declare_complete")
    assert button is not None

    dialog.expected_shots.setText("SHT-001,SHT-002,SHT-003")
    dialog.operator_id.setText("operator")
    assert not button.isEnabled()
    assert "authoritative" in button.toolTip()
