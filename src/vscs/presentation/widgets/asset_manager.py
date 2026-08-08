"""Asset Manager workspace for project production assets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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

from vscs.application.assets import (
    AssetError,
    AssetService,
    CanonicalAssetCreationError,
    CanonicalAssetCreationService,
    XPDWorkbookImportService,
)
from vscs.application.caps import CAPService, CanonicalReferenceService, ReferenceLibraryService
from vscs.domain.assets import Asset, AssetCategory, AssetCreate, AssetStatus
from vscs.presentation.dialogs.xpd_import_dialog import XPDImportDialog


class AssetEditorDialog(QDialog):
    """Collect metadata and the approved ChatGPT MASTER for a new canonical asset."""

    def __init__(self, project_directory: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.project_directory = project_directory.resolve(strict=False)
        self.setWindowTitle("New Asset")
        self.setMinimumWidth(620)

        self.asset_id = QLineEdit()
        self.name = QLineEdit()
        self.category = QComboBox()
        for category in AssetCategory:
            self.category.addItem(category.value.replace("_", " ").title(), category)
        self.status = QComboBox()
        for status in AssetStatus:
            self.status.addItem(status.value.title(), status)
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Select the approved ChatGPT master image")
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self._browse_for_file)
        self.master_confirmation = QCheckBox(
            "I confirm this is the approved ChatGPT Master Canonical Reference"
        )
        self.tags = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(110)

        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(self.browse_button)

        form = QFormLayout()
        form.addRow("Asset ID", self.asset_id)
        form.addRow("Name", self.name)
        form.addRow("Category", self.category)
        form.addRow("Status", self.status)
        form.addRow("Master Canonical Reference", file_row)
        form.addRow("", self.master_confirmation)
        form.addRow("Tags (comma-separated)", self.tags)
        form.addRow("Description", self.description)

        note = QLabel(
            "Saving creates the Asset, a Draft Canonical Profile, and one locked MASTER "
            "reference. Additional production views are managed from the CAP workflow."
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addWidget(buttons)

    def value(self) -> AssetCreate:
        """Return validated asset input from the current fields."""
        return AssetCreate(
            asset_id=self.asset_id.text(),
            name=self.name.text(),
            category=self.category.currentData(),
            status=self.status.currentData(),
            file_path=self.master_reference_path(),
            tags=tuple(tag.strip() for tag in self.tags.text().split(",")),
            description=self.description.toPlainText(),
        )

    def master_reference_path(self) -> Path:
        """Return the selected MASTER as a project-relative path."""
        file_text = self.file_path.text().strip()
        if not file_text:
            raise ValueError("Master Canonical Reference is required")
        return Path(file_text)

    def confirmed_chatgpt_master(self) -> bool:
        return self.master_confirmation.isChecked()

    def _validate_and_accept(self) -> None:
        try:
            self.value()
            self.master_reference_path()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Asset", str(exc))
            return
        if not self.confirmed_chatgpt_master():
            QMessageBox.warning(
                self,
                "Master Confirmation Required",
                "Confirm that the selected image is the approved ChatGPT Master Canonical Reference.",
            )
            return
        self.accept()

    def _browse_for_file(self) -> None:
        """Select the approved master image and store its project-relative path."""
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Master Canonical Reference",
            str(self.project_directory),
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not selected_file:
            return

        selected_path = Path(selected_file).resolve(strict=False)
        try:
            relative_path = selected_path.relative_to(self.project_directory)
        except ValueError:
            QMessageBox.warning(
                self,
                "File Outside Project",
                "Select a master reference located inside the active VSCS project directory.",
            )
            return

        self.file_path.setText(str(relative_path))


class AssetManagerWidget(QWidget):
    """Browse, search, create, remove, and synchronize project assets."""

    def __init__(
        self,
        assets: AssetService,
        caps: CAPService | None = None,
        references: CanonicalReferenceService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.assets = assets
        self.xpd_import = XPDWorkbookImportService(assets)
        self.canonical_creation: CanonicalAssetCreationService | None = None
        if caps is not None and references is not None:
            self.canonical_creation = CanonicalAssetCreationService(
                assets,
                caps,
                references,
                ReferenceLibraryService(references),
            )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search asset ID, name, description, or tags")
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories", None)
        for category in AssetCategory:
            self.category_filter.addItem(category.value.replace("_", " ").title(), category)

        self.add_button = QPushButton("Add Asset")
        self.xpd_import_button = QPushButton("Import / Synchronise XPD")
        self.xpd_import_button.setObjectName("importSynchroniseXPD")
        self.delete_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh")
        self.summary_label = QLabel("No project open")

        controls = QHBoxLayout()
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.category_filter)
        controls.addWidget(self.add_button)
        controls.addWidget(self.xpd_import_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.refresh_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Asset ID", "Name", "Category", "Status", "MASTER"))
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
        self.xpd_import_button.clicked.connect(self._import_xpd)
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
        self.xpd_import_button.setEnabled(enabled)
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
        project_directory = self.assets.projects.project_directory
        if project_directory is None:
            QMessageBox.warning(self, "Asset Error", "Open a project before adding an asset.")
            return
        if self.canonical_creation is None:
            QMessageBox.critical(
                self,
                "Asset Error",
                "Canonical Asset Creation services are not available.",
            )
            return

        dialog = AssetEditorDialog(project_directory, self)
        if not dialog.exec():
            return
        try:
            result = self.canonical_creation.create(
                dialog.value(),
                dialog.master_reference_path(),
                confirmed_chatgpt_master=dialog.confirmed_chatgpt_master(),
            )
        except (CanonicalAssetCreationError, ValueError) as exc:
            QMessageBox.critical(self, "Asset Error", str(exc))
            return
        self.refresh()
        QMessageBox.information(
            self,
            "Canonical Asset Created",
            (
                f"{result.asset.asset_id} was created with a Draft CAP and locked MASTER "
                f"reference {result.production_reference_id}."
            ),
        )

    def _import_xpd(self) -> None:
        if self.assets.projects.project_directory is None:
            QMessageBox.warning(self, "XPD Import", "Open a project before importing XPD.")
            return
        self._xpd_import_dialog = XPDImportDialog(self.xpd_import, self)
        self._xpd_import_dialog.exec()
        self.refresh()

    def _delete_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
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
