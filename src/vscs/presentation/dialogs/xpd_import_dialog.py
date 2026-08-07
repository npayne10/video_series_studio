"""Preview and confirm one-way XPD workbook import into the VSCS Asset database."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.assets import (
    AssetError,
    XPDWorkbookError,
    XPDWorkbookImportService,
)
from vscs.domain.assets import XPDImportDisposition, XPDImportPreview


class XPDImportDialog(QDialog):
    """Select, validate, preview, and import an approved XPD workbook."""

    def __init__(
        self,
        service: XPDWorkbookImportService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.preview_result: XPDImportPreview | None = None
        self.setObjectName("xpdImportDialog")
        self.setWindowTitle("XPD Workbook Import / Synchronisation")
        self.resize(1280, 760)

        self.source_label = QLabel("No workbook selected", self)
        self.summary_label = QLabel("Select the approved XPD workbook to begin.", self)
        self.select_button = QPushButton("Select Workbook", self)
        self.validate_button = QPushButton("Validate / Preview", self)
        self.import_button = QPushButton("Import", self)
        self.close_button = QPushButton("Close", self)
        self.validate_button.setEnabled(False)
        self.import_button.setEnabled(False)

        actions = QHBoxLayout()
        actions.addWidget(self.select_button)
        actions.addWidget(self.validate_button)
        actions.addWidget(self.import_button)
        actions.addStretch(1)
        actions.addWidget(self.close_button)

        self.table = QTableWidget(0, 6, self)
        self.table.setObjectName("xpdImportPreviewTable")
        self.table.setHorizontalHeaderLabels(
            ("Result", "Asset ID", "Asset Name", "Category", "Matched Asset", "Reason")
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        root = QVBoxLayout(self)
        root.addLayout(actions)
        root.addWidget(self.source_label)
        root.addWidget(self.summary_label)
        root.addWidget(self.table, 1)

        self.select_button.clicked.connect(self._select_workbook)
        self.validate_button.clicked.connect(self._preview)
        self.import_button.clicked.connect(self._import)
        self.close_button.clicked.connect(self.accept)
        self._workbook_path: Path | None = None

    def _select_workbook(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "Select XPD Workbook",
            "",
            "Excel workbooks (*.xlsx)",
        )
        if not selected:
            return
        self._workbook_path = Path(selected)
        self.source_label.setText(str(self._workbook_path))
        self.validate_button.setEnabled(True)
        self.import_button.setEnabled(False)
        self.preview_result = None
        self.table.setRowCount(0)
        self.summary_label.setText("Workbook selected. Validate and preview before importing.")

    def _preview(self) -> None:
        if self._workbook_path is None:
            return
        try:
            preview = self.service.preview(self._workbook_path)
        except (AssetError, XPDWorkbookError, ValueError) as exc:
            QMessageBox.critical(self, "XPD Import", str(exc))
            return
        self.preview_result = preview
        self._populate(preview)
        self.import_button.setEnabled(
            preview.count(XPDImportDisposition.NEW) > 0
            or preview.count(XPDImportDisposition.UPDATE) > 0
        )

    def _populate(self, preview: XPDImportPreview) -> None:
        self.table.setRowCount(len(preview.items))
        for row_index, item in enumerate(preview.items):
            values = (
                item.disposition.value,
                item.row.asset_id,
                item.row.asset_name,
                item.row.category_text,
                item.matched_asset_id or "",
                item.reason,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.disposition.value)
                self.table.setItem(row_index, column, cell)
        self.summary_label.setText(
            f"{len(preview.items)} rows — "
            f"New {preview.count(XPDImportDisposition.NEW)}, "
            f"Update {preview.count(XPDImportDisposition.UPDATE)}, "
            f"Unchanged {preview.count(XPDImportDisposition.UNCHANGED)}, "
            f"Conflict {preview.count(XPDImportDisposition.CONFLICT)}, "
            f"Invalid {preview.count(XPDImportDisposition.INVALID)}"
        )

    def _import(self) -> None:
        if self.preview_result is None:
            return
        conflicts = self.preview_result.count(XPDImportDisposition.CONFLICT)
        message = (
            "Import all New and Update rows into the active VSCS Asset database?\n\n"
            "Unchanged rows will be retained, and Conflict/Invalid rows will be skipped."
        )
        if conflicts:
            message += (
                f"\n\n{conflicts} conflict(s) require manual review and will not be imported."
            )
        if (
            QMessageBox.question(self, "Confirm XPD Import", message)
            is not QMessageBox.StandardButton.Yes
        ):
            return
        try:
            report = self.service.apply(self.preview_result)
        except (AssetError, XPDWorkbookError, ValueError) as exc:
            QMessageBox.critical(self, "XPD Import", str(exc))
            return
        QMessageBox.information(
            self,
            "XPD Import Complete",
            f"Created: {report.created}\n"
            f"Updated: {report.updated}\n"
            f"Unchanged: {report.unchanged}\n"
            f"Conflicts skipped: {report.conflicts}\n"
            f"Invalid skipped: {report.invalid}",
        )
        self.import_button.setEnabled(False)
