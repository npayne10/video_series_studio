"""The operator spatial report must be readable and strictly read-only."""

from PySide6.QtWidgets import QDialogButtonBox, QTableWidget

from vscs.application.caps.spatial_graph import SpatialGraphFinding, SpatialGraphReport
from vscs.application.caps.spatial_report import build_spatial_review_report
from vscs.presentation.dialogs.spatial_continuity_report_dialog import (
    SpatialContinuityReportDialog,
)


def test_spatial_report_dialog_displays_finding_without_save_action(qtbot):
    graph = SpatialGraphReport(
        "CAP-LOC-001",
        (),
        (
            SpatialGraphFinding(
                "missing_parent_geometry", "Parent needs typed geometry", ("CAP-LOC-001",)
            ),
        ),
        False,
    )
    dialog = SpatialContinuityReportDialog(build_spatial_review_report(graph))
    qtbot.addWidget(dialog)
    dialog.resize(540, 360)
    dialog.show()
    table = dialog.findChild(QTableWidget)
    buttons = dialog.findChild(QDialogButtonBox)
    assert table is not None
    assert table.rowCount() == 1
    assert table.item(0, 2).text() == "missing_parent_geometry"
    assert buttons is not None
    assert buttons.button(QDialogButtonBox.StandardButton.Save) is None
    assert buttons.isVisible()
