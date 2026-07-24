"""Asset Manager workspace for project production assets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.assets import AssetError, AssetService
from vscs.domain.assets import Asset, AssetCategory, AssetCreate, AssetStatus


class AssetEditorDialog(QDialog):
    """Collect the core metadata required to register an asset."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Asset")
        self.setMinimumWidth(520)

        self.asset_id = QLineEdit()
        self.name = QLineEdit()
        self.category = QComboBox()
        for category in AssetCategory:
            self.category.addItem(category.value.replace("_", " ").title(), category)
        self.status = QComboBox()
        for status in AssetStatus:
            self.status.addItem(status.value.title(), status)
        self.file_path = QLineEdit()
        self.tags = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(110)

        form = QFormLayout()
        form.addRow("Asset ID", self.asset_id)
        form.addRow("Name", self.name)
        form.addRow("Category", self.category)
        form.addRow("Status", self.status)
        form.addRow("Project-relative file", self.file_path)
        form.addRow("Tags (comma-separated)", self.tags)
        form.addRow("Description", self.description)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def value(self) -> AssetCreate:
        """Return validated asset input from the current fields."""
        file_text = self.file_path.text().strip()
        return AssetCreate(
            asset_id=self.asset_id.text(),
            name=self.name.text(),
            category=self.category.currentData(),
            status=self.status.currentData(),
            file_path=Path(file_text) if file_text else None,
            tags=tuple(tag.strip() for tag in self.tags.text().split(",")),
            description=self.description.toPlainText(),
        )


class AssetManagerWidget(QWidget):
    """Browse, search, create, and remove project assets."""

    def __init__(self, assets: AssetService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.assets = assets

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search asset ID, name, description, or tags")
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories", None)
        for category in AssetCategory:
            self.category_filter.addItem(category.value.replace("_", " ").title(), category)

        self.add_button = QPushButton("Add Asset")
        self.delete_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh")
        self.summary_label = QLabel("No project open")

        controls = QHBoxLayout()
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.category_filter)
        controls.addWidget(self.add_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.refresh_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Asset ID", "Name", "Category", "Status", "File"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)

        self.search_input.textChanged.connect(self.refresh)
        self.category_filter.currentIndexChanged.connect(self.refresh)
        self.add_button.clicked.connect(self._add_asset)
        self.delete_button.clicked.connect(self._delete_selected)
        self.refresh_button.clicked.connect(self.refresh)

    def refresh(self) -> None:
        """Reload the table from the active project database."""
        category = self.category_filter.currentData()
        try:
            assets = self.assets.list(query=self.search_input.text(), category=category)
        except AssetError:
            self.table.setRowCount(0)
            self.summary_label.setText("Open a project to manage assets")
            self.set_enabled(False)
            return

        self.set_enabled(True)
        self.table.setRowCount(len(assets))
        for row, asset in enumerate(assets):
            self._populate_row(row, asset)
        self.summary_label.setText(f"{len(assets)} asset(s)")

    def set_enabled(self, enabled: bool) -> None:
        """Enable project-dependent actions while keeping filters usable."""
        self.add_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def _populate_row(self, row: int, asset: Asset) -> None:
        values = (
            asset.asset_id,
            asset.name,
            asset.category.value,
            asset.status.value,
            str(asset.file_path or ""),
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 0:
                item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
            self.table.setItem(row, column, item)

    def _add_asset(self) -> None:
        dialog = AssetEditorDialog(self)
        if not dialog.exec():
            return
        try:
            self.assets.create(dialog.value())
        except (AssetError, ValueError) as exc:
            QMessageBox.critical(self, "Asset Error", str(exc))
            return
        self.refresh()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        asset_id = str(item.data(Qt.ItemDataRole.UserRole))
        answer = QMessageBox.question(
            self,
            "Delete Asset",
            f"Remove {asset_id} from the project registry?\n\nThe source file will not be deleted.",
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.assets.delete(asset_id)
        except AssetError as exc:
            QMessageBox.critical(self, "Asset Error", str(exc))
            return
        self.refresh()
