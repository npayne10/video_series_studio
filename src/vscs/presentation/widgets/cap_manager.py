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
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import (
    CanonicalReferenceError,
    CanonicalReferenceService,
    CAPError,
    CAPGenerationError,
    CAPGeneratorService,
    CAPService,
)
from vscs.domain.caps import (
    CanonicalAssetProfile,
    CanonicalReference,
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceUpdate,
    CAPCreate,
    CAPStatus,
    CAPUpdate,
)
from vscs.infrastructure.ai.provider import GeneratedCAPDraft
from vscs.presentation.dialogs.cap_draft_review_dialog import CAPDraftReviewDialog


class CanonicalReferenceEditorDialog(QDialog):
    """Create or edit the metadata for one canonical reference."""

    def __init__(
        self,
        project_directory: Path,
        reference: CanonicalReference | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_directory = project_directory
        self.reference = reference
        self.setWindowTitle("Edit Canonical Reference" if reference else "Add Canonical Reference")
        self.setMinimumWidth(620)

        self.title = QLineEdit()
        self.file_path = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.file_path, 1)
        path_row.addWidget(browse)

        self.reference_type = QComboBox()
        for reference_type in CanonicalReferenceType:
            self.reference_type.addItem(
            reference_type.value.title(),
            reference_type,
            )

        self.role = QComboBox()
        for role in CanonicalReferenceRole:
            self.role.addItem(role.value.title(), role)

        self.status = QComboBox()
        for status in CanonicalReferenceStatus:
            self.status.addItem(status.value.title(), status)
        self.description = QTextEdit()
        self.description.setMaximumHeight(100)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(100)

        form = QFormLayout()
        form.addRow("Title", self.title)
        form.addRow("File", path_row)
        form.addRow("Type", self.reference_type)
        form.addRow("Role", self.role)
        form.addRow("Version", self.version)
        form.addRow("Approval status", self.status)
        form.addRow("Description", self.description)
        form.addRow("Notes", self.notes)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if reference is not None:
            self._load(reference)

    def create_value(self, cap_id: int) -> CanonicalReferenceCreate:
        return CanonicalReferenceCreate(
            cap_id=cap_id,
            reference_type=self.reference_type.currentData(),
            role=self.role.currentData(),
            title=self.title.text(),
            file_path=Path(self.file_path.text()),
            description=self.description.toPlainText(),
            notes=self.notes.toPlainText(),
            version=self.version.text(),
            status=self.status.currentData(),
        )

    def update_value(self) -> CanonicalReferenceUpdate:
        return CanonicalReferenceUpdate(
            reference_type=self.reference_type.currentData(),
            role=self.role.currentData(),
            title=self.title.text(),
            file_path=Path(self.file_path.text()),
            description=self.description.toPlainText(),
            notes=self.notes.toPlainText(),
            version=self.version.text(),
            status=self.status.currentData(),
        )

    def _load(self, reference: CanonicalReference) -> None:
        self.title.setText(reference.title)
        self.file_path.setText(str(reference.file_path))
        self.reference_type.setCurrentIndex(
            self.reference_type.findData(reference.reference_type)
        )
        self.role.setCurrentIndex(self.role.findData(reference.role))
        self.version.setText(reference.version)
        self.status.setCurrentIndex(self.status.findData(reference.status))
        self.description.setPlainText(reference.description)
        self.notes.setPlainText(reference.notes)

    def _browse(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select Canonical Reference",
            str(self.project_directory),
            "All Files (*)",
        )
        if not filename:
            return
        selected = Path(filename).resolve(strict=False)
        root = self.project_directory.resolve(strict=False)
        try:
            relative = selected.relative_to(root)
        except ValueError:
            QMessageBox.warning(
                self,
                "File Outside Project",
                "Canonical references must be inside the active project directory.",
            )
            return
        self.file_path.setText(str(relative))
        if not self.title.text().strip():
            self.title.setText(selected.stem.replace("_", " ").replace("-", " ").title())

    def _validate_and_accept(self) -> None:
        try:
            if self.reference is None:
                self.create_value(1)
            else:
                self.update_value()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Canonical Reference", str(exc))
            return
        self.accept()


class CAPEditorDialog(QDialog):
    """Create or edit a Canonical Asset Profile."""

    def __init__(
        self,
        caps: CAPService,
        references: CanonicalReferenceService | None = None,
        profile: CanonicalAssetProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.caps = caps
        self.reference_service = references
        self.profile = profile
        self.project_directory = caps.assets.projects.project_directory
        self.setWindowTitle("Edit CAP" if profile else "New CAP")
        self.setMinimumSize(900, 720)

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

        self.references = QTableWidget(0, 6)
        self.references.setHorizontalHeaderLabels(
            ("Title", "Type", "Role", "Version", "Status", "File")
        )
        self.references.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.references.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.references.setAlternatingRowColors(True)
        self.references.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.references.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.references.doubleClicked.connect(self._edit_reference)

        self.add_reference_button = QPushButton("Add Reference…")
        self.edit_reference_button = QPushButton("Edit Selected")
        self.remove_reference_button = QPushButton("Remove Selected")
        self.add_reference_button.clicked.connect(self._add_reference)
        self.edit_reference_button.clicked.connect(self._edit_reference)
        self.remove_reference_button.clicked.connect(self._remove_reference)

        reference_buttons = QHBoxLayout()
        reference_buttons.addWidget(self.add_reference_button)
        reference_buttons.addWidget(self.edit_reference_button)
        reference_buttons.addWidget(self.remove_reference_button)
        reference_buttons.addStretch(1)
        reference_box = QVBoxLayout()
        reference_box.addWidget(self.references)
        reference_box.addLayout(reference_buttons)

        if profile is None or references is None:
            self.add_reference_button.setEnabled(False)
            self.edit_reference_button.setEnabled(False)
            self.remove_reference_button.setEnabled(False)
            note = QLabel(
                "Save the CAP first, then reopen it to add structured canonical references."
                if profile is None
                else "Canonical reference services are not available."
            )
            note.setWordWrap(True)
            reference_box.insertWidget(0, note)

        form = QFormLayout()
        form.addRow("Registered asset", self.asset)
        form.addRow("CAP title", self.title)
        form.addRow("Version", self.version)
        form.addRow("Status", self.status)
        form.addRow("Canonical description", self.description)
        form.addRow("Visual identity", self.visual_identity)
        form.addRow("Production notes", self.production_notes)
        form.addRow("Canonical References", reference_box)

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
            self._refresh_references()

    def create_value(self) -> CAPCreate:
        return CAPCreate(
            asset_id=str(self.asset.currentData()),
            title=self.title.text(),
            version=self.version.text(),
            status=self.status.currentData(),
            canonical_description=self.description.toPlainText(),
            visual_identity=self.visual_identity.toPlainText(),
            production_notes=self.production_notes.toPlainText(),
        )

    def update_value(self) -> CAPUpdate:
        return CAPUpdate(
            title=self.title.text(),
            version=self.version.text(),
            status=self.status.currentData(),
            canonical_description=self.description.toPlainText(),
            visual_identity=self.visual_identity.toPlainText(),
            production_notes=self.production_notes.toPlainText(),
        )

    def _load(self, profile: CanonicalAssetProfile) -> None:
        self.title.setText(profile.title)
        self.version.setText(profile.version)
        self.status.setCurrentIndex(self.status.findData(profile.status))
        self.description.setPlainText(profile.canonical_description)
        self.visual_identity.setPlainText(profile.visual_identity)
        self.production_notes.setPlainText(profile.production_notes)

    def _refresh_references(self) -> None:
        if self.profile is None or self.reference_service is None:
            self.references.setRowCount(0)
            return
        try:
            values = self.reference_service.list_for_cap(self.profile.asset_id)
        except CanonicalReferenceError as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        self.references.setRowCount(len(values))
        for row, reference in enumerate(values):
            columns = (
                reference.title,
                reference.reference_type.value.title(),
                reference.role.value.title(),
                reference.version,
                reference.status.value.title(),
                str(reference.file_path),
            )
            for column, value in enumerate(columns):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, reference.id)
                self.references.setItem(row, column, item)

    def _selected_reference_id(self) -> int | None:
        row = self.references.currentRow()
        if row < 0:
            return None
        item = self.references.item(row, 0)
        return None if item is None else int(item.data(Qt.ItemDataRole.UserRole))

    def _add_reference(self) -> None:
        if (
            self.profile is None
            or self.reference_service is None
            or self.project_directory is None
        ):
            return
        dialog = CanonicalReferenceEditorDialog(self.project_directory, parent=self)
        if not dialog.exec():
            return
        try:
            self.reference_service.create(
                self.profile.asset_id,
                dialog.create_value(self.profile.id),
            )
        except (CanonicalReferenceError, ValueError) as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        self._refresh_references()

    def _edit_reference(self) -> None:
        if self.reference_service is None or self.project_directory is None:
            return
        reference_id = self._selected_reference_id()
        if reference_id is None:
            return
        try:
            reference = self.reference_service.get(reference_id)
        except CanonicalReferenceError as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        dialog = CanonicalReferenceEditorDialog(
            self.project_directory,
            reference,
            self,
        )
        if not dialog.exec():
            return
        try:
            self.reference_service.update(reference_id, dialog.update_value())
        except (CanonicalReferenceError, ValueError) as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        self._refresh_references()

    def _remove_reference(self) -> None:
        if self.reference_service is None:
            return
        reference_id = self._selected_reference_id()
        if reference_id is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove Canonical Reference",
                "Remove the selected canonical reference?\n\nThe source file will not be deleted.",
            )
            is not QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.reference_service.delete(reference_id)
        except CanonicalReferenceError as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        self._refresh_references()


class CAPManagerWidget(QWidget):
    """Browse, generate, create, edit, and remove Canonical Asset Profiles."""

    def __init__(
        self,
        caps: CAPService,
        generator: CAPGeneratorService | None = None,
        references: CanonicalReferenceService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.caps = caps
        self.generator = generator
        self.references = references
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search CAP asset ID, title, description, or identity")
        self.status_filter = QComboBox()
        self.status_filter.addItem("All statuses", None)
        for status in CAPStatus:
            self.status_filter.addItem(status.value.title(), status)
        self.generate_button = QPushButton("Generate CAP")
        self.generate_button.setToolTip("Generate and review a CAP Draft Package")
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
            ("Asset ID", "CAP Title", "Version", "Status", "Canonical References")
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
            reference_count = len(profile.reference_paths)
            if self.references is not None:
                try:
                    reference_count = len(self.references.list_for_cap(profile.asset_id))
                except CanonicalReferenceError:
                    reference_count = 0
            values = (
                profile.asset_id,
                profile.title,
                profile.version,
                profile.status.value,
                str(reference_count),
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

        def regenerate() -> GeneratedCAPDraft:
            if self.generator is None:
                raise CAPGenerationError("No CAP generator is configured")
            return self.generator.generate_draft(asset_id, story_context)

        try:
            draft = regenerate()
            dialog = CAPDraftReviewDialog(draft, regenerate, self)
        except (CAPError, CAPGenerationError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Generation Error", str(exc))
            return
        if not dialog.exec():
            return
        try:
            self.generator.create_from_draft(asset_id, dialog.reviewed_draft())
        except (CAPError, CAPGenerationError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Generation Error", str(exc))
            return
        self.refresh()
        QMessageBox.information(
            self,
            "CAP Draft Created",
            (
                f"The moderated CAP for {asset_id} was saved in Draft status. "
                "It remains non-canonical until approved through the normal CAP review process."
            ),
        )

    def _add(self) -> None:
        try:
            if not self.caps.available_assets():
                QMessageBox.information(
                    self, "CAP Manager", "Register an asset without a CAP before creating one."
                )
                return
            dialog = CAPEditorDialog(self.caps, self.references, parent=self)
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
            dialog = CAPEditorDialog(self.caps, self.references, profile, self)
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
