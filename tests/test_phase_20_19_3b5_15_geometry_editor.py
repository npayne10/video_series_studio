"""B.5.15 structured geometry editing is local and non-authoritative."""

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.geometry_contract import CAPGeometry
from vscs.presentation.dialogs.cap_geometry_editor_dialog import CAPGeometryEditorDialog


def test_structured_geometry_editor_preserves_bounds_and_anchors(qtbot):
    original = CAPGeometry.model_validate(
        {
            "frame_id": "room",
            "origin_mm": {"x": 10, "y": 20, "z": 30},
            "size_mm": {"x": 8000, "y": 5000, "z": 2600},
            "anchors": [{"name": "mount", "position_mm": {"x": 100, "y": 200, "z": 300}}],
        }
    )
    dialog = CAPGeometryEditorDialog(original)
    qtbot.addWidget(dialog)
    assert dialog.frame.text() == "room"
    assert dialog.dimensions["x"].value() == 8000
    assert dialog.origin["z"].value() == 30
    dialog.dimensions["x"].setValue(9000)
    dialog._apply()
    assert dialog.result_geometry is not None
    assert dialog.result_geometry.size_mm.x == 9000
    assert dialog.result_geometry.anchors[0].name == "mount"


def test_invalid_duplicate_anchor_names_cannot_be_accepted(qtbot):
    dialog = CAPGeometryEditorDialog(None)
    qtbot.addWidget(dialog)
    dialog.frame.setText("test-frame")
    dialog.anchors.setPlainText("Mount|0|0|0\nmount|1|1|1")
    with patch.object(QMessageBox, "warning") as warning:
        dialog._apply()
    warning.assert_called_once()
    assert dialog.result_geometry is None


def test_missing_frame_cannot_be_accepted(qtbot):
    dialog = CAPGeometryEditorDialog(None)
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "warning") as warning:
        dialog._apply()
    warning.assert_called_once()
    assert dialog.result_geometry is None
