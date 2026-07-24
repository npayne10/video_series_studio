"""Canonical Asset Profile Manager workspace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import (
    CAPError,
    CAPGenerationError,
    CAPGeneratorService,
    CAPService,
)
from vscs.domain.caps import CanonicalAssetProfile, CAPCreate, CAPStatus, CAPUpdate


class CAPEditorDialog(QDialog):
    """Create or edit a Canonical Asset Profile."""

    def __init__(
        self,
        caps: CAPService,
        profile: CanonicalAssetProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.caps = caps
        self.profile = profile
        self.project_directory = caps.assets.projects.project_directory
        self.setWindowTitle("Edit CAP" if profile else "New CAP")
        self.setMinimumSize(760, 680)

        self.asset = QComboBox()
        if profile is None:
            for asset_id, name in caps.available_assets():
                self.asset.addItem(f"{asset_id} — {name}", asset_id)
        else:
            self.asset.addItem(profile.asset_id, profile.asset_id)
            self.asset.setEnabled(False)

        self.title = QLineEdit()
        self.version = QLineEdit("1.0")
        self.status = QComboBox()
        for status in CAPStatus:
            self.status.addItem(status.value.title(), status)
        self.description = QTextEdit()
        self.visual_identity = QTextEdit()
        self.production_notes = QTextEdit()
        self.references = QListWidget()
        add_reference = QPushButton("Add Reference…")
        remove_reference = QPushButton("Remove Selected")
        add_reference.clicked.connect(self._add_reference)
        remove_reference.clicked.connect(self._remove_reference)

        reference_buttons = QHBoxLayout()
        reference_buttons.addWidget(add_reference)
        reference_buttons.addWidget(remove_reference)
        reference_buttons.addStretch(1)
        reference_box = QVBoxLayout()
        reference_box.addWidget(self.references)
        reference_box.addLayout(reference_buttons)

        form = QFormLayout()
        form.addRow("Registered asset", self.asset)
        form.addRow("CAP title", self.title)
        form.addRow("Version", self.version)
        form.addRow("Status", self.status)
        form.addRow("Canonical description", self.description)
        form.addRow("Visual identity", self.visual_identity)
        form.addRow("Production notes", self.production_notes)
        form.addRow("Reference files", reference_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if profile is not None:
            self._load(profile)

    def create_value(self) -> CAPCreate:
        return CAPCreate(
            asset_id=str(self.asset.currentData()),
            title=self.title.text(),
            version=self.version.text(),
            status=self.status.currentData(),
            canonical_description=self.description.toPlainText(),
            visual_identity=self.visual_identity.toPlainText(),
            production_notes=self.production_notes.toPlainText(),
            reference_paths=self._reference_paths(),
        )

    def update_value(self) -> CAPUpdate:
        return CAPUpdate(
            title=self.title.text(),
            version=self.version.text(),
            status=self.status.currentData(),
            canonical_description=self.description.toPlainText(),
            visual_identity=self.visual_identity.toPlainText(),
            production_notes=self.production_notes.toPlainText(),
            reference_paths=self._reference_paths(),
        )

    def _load(self, profile: CanonicalAssetProfile) -> None:
        self.title.setText(profile.title)
        self.version.setText(profile.version)
        self.status.setCurrentIndex(self.status.findData(profile.status))
        self.description.setPlainText(profile.canonical_description)
        self.visual_identity.setPlainText(profile.visual_identity)
        self.production_notes.setPlainText(profile.production_notes)
        for path in profile.reference_paths:
            self.references.addItem(str(path))

    def _reference_paths(self) -> tuple[Path, ...]:
        return tuple(
            Path(self.references.item(index).text()) for index in range(self.references.count())
        )

    def _add_reference(self) -> None:
        if self.project_directory is None:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select CAP Reference Files",
            str(self.project_directory),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;All Files (*)",
        )
        root = self.project_directory.resolve(strict=False)
        for filename in files:
            selected = Path(filename).resolve(strict=False)
            try:
                relative = selected.relative_to(root)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "File Outside Project",
                    "CAP references must be inside the active project directory.",
                )
                continue
            existing = {self.references.item(i).text() for i in range(self.references.count())}
            if str(relative) not in existing:
                self.references.addItem(str(relative))

    def _remove_reference(self) -> None:
        for item in self.references.selectedItems():
            self.references.takeItem(self.references.row(item))


class CAPManagerWidget(QWidget):
    """Browse, generate, create, edit, and remove Canonical Asset Profiles."""

    def __init__(
        self,
        caps: CAPService,
        generator: CAPGeneratorService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.caps = caps
        self.generator = generator
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search CAP asset ID, title, description, or identity")
        self.status_filter = QComboBox()
        self.status_filter.addItem("All statuses", None)
        for status in CAPStatus:
            self.status_filter.addItem(status.value.title(), status)
        self.generate_button = QPushButton("Generate CAP")
        self.generate_button.setToolTip("Generate a moderated CAP draft from story context")
        self.add_button = QPushButton("New CAP")
        self.edit_button = QPushButton("Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        self.refresh_button = QPushButton("Refresh")
        self.summary_label = QLabel("No project open")

        controls = QHBoxLayout()
        controls.addWidget(self.search_input, 1)
        controls.addWidget(self.status_filter)
        controls.addWidget(self.generate_button)
        controls.addWidget(self.add_button)
        controls.addWidget(self.edit_button)
        controls.addWidget(self.delete_button)
        controls.addWidget(self.refresh_button)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ("Asset ID", "CAP Title", "Version", "Status", "References")
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)

        self.search_input.textChanged.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.generate_button.clicked.connect(self._generate)
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.refresh_button.clicked.connect(self.refresh)
        self.table.doubleClicked.connect(self._edit)

    def refresh(self) -> None:
        try:
            profiles = self.caps.list(
                query=self.search_input.text(), status=self.status_filter.currentData()
            )
        except CAPError as exc:
            self.table.setRowCount(0)
            self.summary_label.setText(str(exc))
            self._set_enabled(False)
            return
        self._set_enabled(True)
        self.table.setRowCount(len(profiles))
        for row, profile in enumerate(profiles):
            values = (
                profile.asset_id,
                profile.title,
                profile.version,
                profile.status.value,
                str(len(profile.reference_paths)),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, profile.asset_id)
                self.table.setItem(row, column, item)
        self.summary_label.setText(f"{len(profiles)} CAP(s)")

    def _set_enabled(self, enabled: bool) -> None:
        self.generate_button.setEnabled(enabled and self.generator is not None)
        self.add_button.setEnabled(enabled)
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def _selected_asset_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return None if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    def _generate(self) -> None:
        if self.generator is None:
            QMessageBox.information(self, "CAP Generator", "No CAP generator is configured.")
            return
        try:
            assets = self.caps.available_assets()
        except CAPError as exc:
            QMessageBox.critical(self, "CAP Generation Error", str(exc))
            return
        if not assets:
            QMessageBox.information(
                self,
                "CAP Generator",
                "Register an asset without a CAP before generating one.",
            )
            return
        labels = [f"{asset_id} — {name}" for asset_id, name in assets]
        selected, accepted = QInputDialog.getItem(
            self,
            "Generate CAP",
            "Asset:",
            labels,
            editable=False,
        )
        if not accepted:
            return
        selected_index = labels.index(selected)
        asset_id = assets[selected_index][0]
        story_context, accepted = QInputDialog.getMultiLineText(
            self,
            "Generate CAP",
            "Paste the relevant story passage or approved story context:",
        )
        if not accepted:
            return
        try:
            self.generator.generate_and_create(asset_id, story_context)
        except (CAPError, CAPGenerationError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Generation Error", str(exc))
            return
        self.refresh()
        QMessageBox.information(
            self,
            "CAP Generated",
            f"A Draft CAP was generated for {asset_id}. Review and approve it before production use.",
        )

    def _add(self) -> None:
        try:
            if not self.caps.available_assets():
                QMessageBox.information(
                    self, "CAP Manager", "Register an asset without a CAP before creating one."
                )
                return
            dialog = CAPEditorDialog(self.caps, parent=self)
        except CAPError as exc:
            QMessageBox.critical(self, "CAP Error", str(exc))
            return
        if not dialog.exec():
            return
        try:
            self.caps.create(dialog.create_value())
        except (CAPError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Error", str(exc))
            return
        self.refresh()

    def _edit(self) -> None:
        asset_id = self._selected_asset_id()
        if asset_id is None:
            return
        try:
            profile = self.caps.get(asset_id)
            dialog = CAPEditorDialog(self.caps, profile, self)
            if not dialog.exec():
                return
            self.caps.update(asset_id, dialog.update_value())
        except (CAPError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Error", str(exc))
            return
        self.refresh()

    def _delete(self) -> None:
        asset_id = self._selected_asset_id()
        if asset_id is None:
            return
        if (
            QMessageBox.question(
                self,
                "Delete CAP",
                f"Delete the CAP for {asset_id}?\n\nThe linked asset and files remain unchanged.",
            )
            is not QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.caps.delete(asset_id)
        except CAPError as exc:
            QMessageBox.critical(self, "CAP Error", str(exc))
            return
        self.refresh()
