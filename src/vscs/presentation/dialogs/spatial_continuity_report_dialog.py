"""Read-only operator workspace for Draft spatial graph findings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.spatial_report import SpatialReviewReport


class SpatialContinuityReportDialog(QDialog):
    """Present report evidence without changing any project records."""

    def __init__(self, report: SpatialReviewReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Spatial Continuity Review — {report.parent_asset_id}")
        self.resize(860, 560)
        self.setMinimumSize(510, 340)
        layout = QVBoxLayout(self)
        header = QLabel(
            f"Parent: {report.parent_asset_id}  |  Status: {report.status.value.upper()}\n"
            f"Resolved siblings: {len(report.placed_asset_ids)}  |  "
            f"Findings: {len(report.rows)}"
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        self.table = QTableWidget(len(report.rows), 4)
        self.table.setHorizontalHeaderLabels(("Status", "Assets", "Finding", "Explanation"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        for row, item in enumerate(report.rows):
            for column, value in enumerate(
                (item.status.value, ", ".join(item.asset_ids), item.code, item.detail)
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))
        layout.addWidget(self.table, 1)
        if not report.rows:
            placed = ", ".join(report.placed_asset_ids) or "none"
            layout.addWidget(QLabel(f"Resolved asset IDs: {placed}"))
        note = QLabel(report.scope_note)
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
