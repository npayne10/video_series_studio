"""Asset Manager workspace for project production assets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
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

from vscs.application.assets import AssetError, AssetService, XPDWorkbookImportService
from vscs.application.assets.canonical_creation import (
    CanonicalAssetCreationError,
    CanonicalAssetCreationService,
)
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.domain.assets import Asset, AssetCategory, AssetCreate, AssetStatus, AssetUpdate
from vscs.presentation.dialogs.xpd_import_dialog import XPDImportDialog


def _current_asset_category(combo: QComboBox) -> AssetCategory:
    """Return Qt combo data as a stable AssetCategory value."""
    value = combo.currentData()
    if isinstance(value, AssetCategory):
        return value
    return AssetCategory(str(value))


def _current_asset_status(combo: QComboBox) -> AssetStatus:
    """Return Qt combo data as a stable AssetStatus value."""
    value = combo.currentData()
    if isinstance(value, AssetStatus):
        return value
    return AssetStatus(str(value))


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
            self.category.addItem(category.value.replace("_", " ").title(), category.value)
        self.status = QComboBox()
        for status in AssetStatus:
            self.status.addItem(status.value.title(), status.value)
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
            category=_current_asset_category(self.category),
            status=_current_asset_status(self.status),
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


class AssetEditDialog(QDialog):
    """Edit registry metadata and govern missing/revised MASTER selection."""

    open_canonical_profile_requested = Signal(str)

    def __init__(
        self,
        asset: Asset,
        project_directory: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.asset = asset
        self.project_directory = (
            project_directory.resolve(strict=False) if project_directory is not None else None
        )
        self.original_master = str(asset.file_path or "")
        self.setWindowTitle(f"Edit Asset — {asset.asset_id}")
        self.setMinimumWidth(680)

        self.asset_id = QLineEdit(asset.asset_id)
        self.asset_id.setReadOnly(True)
        self.name = QLineEdit(asset.name)
        self.category = QComboBox()
        for category in AssetCategory:
            self.category.addItem(category.value.replace("_", " ").title(), category.value)
        self.category.setCurrentIndex(max(0, self.category.findData(asset.category.value)))
        self.status = QComboBox()
        for status in AssetStatus:
            self.status.addItem(status.value.title(), status.value)
        self.status.setCurrentIndex(max(0, self.status.findData(asset.status.value)))

        self.master_reference = QLineEdit(self.original_master)
        self.master_reference.setReadOnly(True)
        self.master_browse_button = QPushButton("Browse…")
        self.master_browse_button.setEnabled(self.project_directory is not None)
        self.master_browse_button.clicked.connect(self._browse_master)
        master_row = QHBoxLayout()
        master_row.addWidget(self.master_reference, 1)
        master_row.addWidget(self.master_browse_button)

        initial_status = (
            "Locked canonical authority" if self.original_master else "Missing — select a MASTER"
        )
        self.master_status = QLineEdit(initial_status)
        self.master_status.setReadOnly(True)
        self.master_confirmation = QCheckBox(
            "I confirm the selected replacement is the approved ChatGPT Master Canonical Reference"
        )
        self.master_confirmation.setEnabled(False)

        self.tags = QLineEdit(", ".join(asset.tags))
        self.description = QTextEdit(asset.description)
        self.description.setMinimumHeight(110)
        self.open_cap_button = QPushButton("Open Canonical Profile")
        self.open_cap_button.clicked.connect(
            lambda: self.open_canonical_profile_requested.emit(asset.asset_id)
        )

        form = QFormLayout()
        form.addRow("Asset ID", self.asset_id)
        form.addRow("Name", self.name)
        form.addRow("Category", self.category)
        form.addRow("Status", self.status)
        form.addRow("Master Canonical Reference", master_row)
        form.addRow("MASTER Status", self.master_status)
        form.addRow("", self.master_confirmation)
        form.addRow("Tags (comma-separated)", self.tags)
        form.addRow("Description", self.description)

        note = QLabel(
            "Asset ID remains immutable. Use Browse to attach a missing MASTER or propose a "
            "new ChatGPT MASTER revision. Existing MASTER history is preserved; replacement is "
            "blocked when active derived references still depend on it."
        )
        note.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        actions = QHBoxLayout()
        actions.addWidget(self.open_cap_button)
        actions.addStretch(1)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addLayout(actions)
        layout.addWidget(buttons)

    def value(self) -> AssetUpdate:
        """Return editable registry fields; MASTER changes use the canonical service."""
        return AssetUpdate(
            name=self.name.text(),
            category=_current_asset_category(self.category),
            status=_current_asset_status(self.status),
            tags=tuple(tag.strip() for tag in self.tags.text().split(",")),
            description=self.description.toPlainText(),
        )

    def master_changed(self) -> bool:
        return self.master_reference.text().strip() != self.original_master

    def selected_master_path(self) -> Path | None:
        text = self.master_reference.text().strip()
        return Path(text) if text else None

    def confirmed_chatgpt_master(self) -> bool:
        return self.master_confirmation.isChecked()

    def _validate_and_accept(self) -> None:
        try:
            self.value()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Asset", str(exc))
            return
        if self.master_changed() and not self.confirmed_chatgpt_master():
            QMessageBox.warning(
                self,
                "Master Confirmation Required",
                "Confirm that the selected image is the approved ChatGPT Master Canonical Reference.",
            )
            return
        self.accept()

    def _browse_master(self) -> None:
        if self.project_directory is None:
            return
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
            relative = selected_path.relative_to(self.project_directory)
        except ValueError:
            QMessageBox.warning(
                self,
                "File Outside Project",
                "Select a master reference located inside the active VSCS project directory.",
            )
            return
        self.master_reference.setText(str(relative))
        self.master_confirmation.setChecked(False)
        self.master_confirmation.setEnabled(True)
        self.master_status.setText(
            "Pending MASTER revision" if self.original_master else "Pending MASTER attachment"
        )


class AssetManagerWidget(QWidget):
    """Browse, search, create, edit, remove, and synchronize project assets."""

    open_canonical_profile_requested = Signal(str)

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
            self.category_filter.addItem(category.value.replace("_", " ").title(), category.value)

        self.add_button = QPushButton("Add Asset")
        self.edit_button = QPushButton("Edit Selected")
        self.xpd_import_button = QPushButton("Import / Synchronise XPD")
        self.xpd_import_button.setObjectName("importSynchroniseXPD")
        self.delete_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh")
        self.summary_label = QLabel("No project open")

        controls = QHBoxLayout()
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.category_filter)
        controls.addWidget(self.add_button)
        controls.addWidget(self.edit_button)
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
        self.edit_button.clicked.connect(self._edit_selected)
        self.xpd_import_button.clicked.connect(self._import_xpd)
        self.delete_button.clicked.connect(self._delete_selected)
        self.refresh_button.clicked.connect(self.refresh)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit_selected())

    def refresh(self) -> None:
        """Reload the table from the active project database."""
        category_value = self.category_filter.currentData()
        category = AssetCategory(str(category_value)) if category_value is not None else None
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
        self.edit_button.setEnabled(enabled)
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

    def _selected_asset_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

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

    def _edit_selected(self) -> None:
        asset_id = self._selected_asset_id()
        if asset_id is None:
            QMessageBox.information(self, "Edit Asset", "Select an asset to edit.")
            return
        try:
            asset = self.assets.get(asset_id)
        except AssetError as exc:
            QMessageBox.critical(self, "Asset Error", str(exc))
            return
        dialog = AssetEditDialog(asset, self.assets.projects.project_directory, self)
        dialog.open_canonical_profile_requested.connect(self.open_canonical_profile_requested.emit)
        if not dialog.exec():
            return
        if _current_asset_category(dialog.category) != asset.category:
            answer = QMessageBox.warning(
                self,
                "Category Change",
                "Changing the Asset category may change canonical reference requirements and "
                "production readiness. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer is not QMessageBox.StandardButton.Yes:
                return
        if dialog.master_changed():
            if self.canonical_creation is None:
                QMessageBox.critical(
                    self,
                    "Asset Error",
                    "Canonical Asset Creation services are not available.",
                )
                return
            master_path = dialog.selected_master_path()
            if master_path is None:
                QMessageBox.critical(
                    self,
                    "Asset Error",
                    "Master Canonical Reference is required.",
                )
                return
            try:
                self.canonical_creation.set_or_revise_master(
                    asset.asset_id,
                    master_path,
                    confirmed_chatgpt_master=dialog.confirmed_chatgpt_master(),
                )
            except CanonicalAssetCreationError as exc:
                QMessageBox.critical(self, "MASTER Revision Error", str(exc))
                return
        try:
            self.assets.update(asset_id, dialog.value())
        except (AssetError, ValueError) as exc:
            QMessageBox.critical(self, "Asset Error", str(exc))
            return
        self.refresh()

    def _import_xpd(self) -> None:
        if self.assets.projects.project_directory is None:
            QMessageBox.warning(self, "XPD Import", "Open a project before importing XPD.")
            return
        self._xpd_import_dialog = XPDImportDialog(self.xpd_import, self)
        self._xpd_import_dialog.exec()
        self.refresh()

    def _delete_selected(self) -> None:
        asset_id = self._selected_asset_id()
        if asset_id is None:
            return
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
