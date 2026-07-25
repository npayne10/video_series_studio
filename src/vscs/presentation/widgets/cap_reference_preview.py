"""Thumbnail and preview support for CAP canonical references."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import CAPError, CanonicalReferenceError
from vscs.domain.caps import CanonicalReference, CanonicalReferenceType
from vscs.presentation.widgets.cap_manager import CAPEditorDialog, CAPManagerWidget


IMAGE_SUFFIXES = frozenset({".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"})


def is_previewable_image(reference: CanonicalReference) -> bool:
    """Return whether a canonical reference can be rendered as an image."""
    return (
        reference.reference_type is CanonicalReferenceType.IMAGE
        or reference.file_path.suffix.lower() in IMAGE_SUFFIXES
    )


class CanonicalReferencePreviewDialog(QDialog):
    """Display a canonical reference image and its approved metadata."""

    def __init__(
        self,
        project_directory: Path,
        reference: CanonicalReference,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_directory = project_directory
        self.reference = reference
        self.absolute_path = (project_directory / reference.file_path).resolve(strict=False)
        self._source_pixmap = QPixmap(str(self.absolute_path))
        self._fit_to_window = True

        self.setWindowTitle(f"Canonical Reference Preview — {reference.title}")
        self.setMinimumSize(900, 650)
        self.resize(1100, 780)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.image_label.setMinimumSize(320, 240)

        self.scroll_area = QScrollArea()
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.image_label)

        self.message = QLabel()
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.hide()

        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(10, 400)
        self.zoom.setValue(100)
        self.zoom.setTickInterval(25)
        self.zoom.valueChanged.connect(self._apply_zoom)

        fit_button = QPushButton("Fit to Window")
        actual_button = QPushButton("100%")
        open_button = QPushButton("Open Externally")
        fit_button.clicked.connect(self._fit_image)
        actual_button.clicked.connect(self._actual_size)
        open_button.clicked.connect(self._open_externally)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Zoom"))
        controls.addWidget(self.zoom, 1)
        controls.addWidget(actual_button)
        controls.addWidget(fit_button)
        controls.addWidget(open_button)

        metadata = QFormLayout()
        metadata.addRow("Title", QLabel(reference.title))
        metadata.addRow("Type", QLabel(reference.reference_type.value.title()))
        metadata.addRow("Role", QLabel(reference.role.value.title()))
        metadata.addRow("Version", QLabel(reference.version))
        metadata.addRow("Approval status", QLabel(reference.status.value.title()))
        metadata.addRow("File", QLabel(str(reference.file_path)))
        if reference.description:
            description = QLabel(reference.description)
            description.setWordWrap(True)
            metadata.addRow("Description", description)
        if reference.notes:
            notes = QLabel(reference.notes)
            notes.setWordWrap(True)
            metadata.addRow("Notes", notes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.message)
        layout.addLayout(controls)
        layout.addLayout(metadata)
        layout.addWidget(buttons)

        if not self.absolute_path.is_file():
            self._show_message(f"The reference file could not be found:\n{self.absolute_path}")
        elif self._source_pixmap.isNull():
            self._show_message(
                "This file cannot be rendered as an image preview. "
                "Use Open Externally to view it in its associated application."
            )
        else:
            self._fit_image()

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)  # type: ignore[arg-type]
        if self._fit_to_window and not self._source_pixmap.isNull():
            self._render_fit()

    def _show_message(self, text: str) -> None:
        self.scroll_area.hide()
        self.zoom.setEnabled(False)
        self.message.setText(text)
        self.message.show()

    def _fit_image(self) -> None:
        if self._source_pixmap.isNull():
            return
        self._fit_to_window = True
        self.zoom.blockSignals(True)
        self.zoom.setValue(100)
        self.zoom.blockSignals(False)
        self._render_fit()

    def _render_fit(self) -> None:
        viewport = self.scroll_area.viewport().size()
        target = QSize(max(1, viewport.width() - 12), max(1, viewport.height() - 12))
        scaled = self._source_pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def _actual_size(self) -> None:
        if self._source_pixmap.isNull():
            return
        self._fit_to_window = False
        self.zoom.setValue(100)
        self._render_scale(1.0)

    def _apply_zoom(self, value: int) -> None:
        if self._source_pixmap.isNull():
            return
        self._fit_to_window = False
        self._render_scale(value / 100.0)

    def _render_scale(self, scale: float) -> None:
        size = self._source_pixmap.size() * scale
        scaled = self._source_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def _open_externally(self) -> None:
        if not self.absolute_path.is_file():
            QMessageBox.warning(self, "Reference Missing", str(self.absolute_path))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.absolute_path))):
            QMessageBox.warning(
                self,
                "Unable to Open Reference",
                "No associated application could open this reference file.",
            )


class PreviewCAPEditorDialog(CAPEditorDialog):
    """CAP editor enhanced with reference thumbnails and a full preview action."""

    THUMBNAIL_SIZE = QSize(72, 54)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.references.setIconSize(self.THUMBNAIL_SIZE)
        self.references.setColumnWidth(0, 230)

        self.preview_reference_button = QPushButton("Preview Selected")
        self.preview_reference_button.clicked.connect(self._preview_reference)
        self._insert_preview_button()

        self.references.itemSelectionChanged.connect(self._update_preview_enabled)
        self.references.doubleClicked.disconnect(self._edit_reference)
        self.references.doubleClicked.connect(self._preview_reference)
        self._update_preview_enabled()
        if self.profile is not None:
            self._refresh_reference_previews()

    def _insert_preview_button(self) -> None:
        form = self.layout().itemAt(0).layout()
        if not isinstance(form, QFormLayout):
            return
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            label = None if label_item is None else label_item.widget()
            if isinstance(label, QLabel) and label.text() == "Canonical References":
                field_layout = None if field_item is None else field_item.layout()
                if field_layout is not None and field_layout.count() >= 2:
                    button_layout = field_layout.itemAt(field_layout.count() - 1).layout()
                    if button_layout is not None:
                        button_layout.insertWidget(2, self.preview_reference_button)
                return

    def _refresh_reference_previews(self) -> None:
        CAPEditorDialog._refresh_references(self)
        if self.profile is None or self.reference_service is None:
            self._update_preview_enabled()
            return
        try:
            values = self.reference_service.list_for_cap(self.profile.asset_id)
        except CanonicalReferenceError:
            self._update_preview_enabled()
            return
        value_by_id = {reference.id: reference for reference in values}
        for row in range(self.references.rowCount()):
            item = self.references.item(row, 0)
            if item is None:
                continue
            reference_id = int(item.data(Qt.ItemDataRole.UserRole))
            reference = value_by_id.get(reference_id)
            if reference is None:
                continue
            item.setData(Qt.ItemDataRole.UserRole + 1, reference)
            if is_previewable_image(reference) and self.project_directory is not None:
                pixmap = QPixmap(str(self.project_directory / reference.file_path))
                if not pixmap.isNull():
                    thumbnail = pixmap.scaled(
                        self.THUMBNAIL_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    item.setIcon(QIcon(thumbnail))
                    self.references.setRowHeight(row, self.THUMBNAIL_SIZE.height() + 10)
        self._update_preview_enabled()

    def _add_reference(self) -> None:
        super()._add_reference()
        self._refresh_reference_previews()

    def _edit_reference(self) -> None:
        super()._edit_reference()
        self._refresh_reference_previews()

    def _remove_reference(self) -> None:
        super()._remove_reference()
        self._refresh_reference_previews()

    def _selected_reference(self) -> CanonicalReference | None:
        row = self.references.currentRow()
        if row < 0:
            return None
        item = self.references.item(row, 0)
        if item is None:
            return None
        stored = item.data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(stored, CanonicalReference):
            return stored
        if self.reference_service is None:
            return None
        try:
            return self.reference_service.get(int(item.data(Qt.ItemDataRole.UserRole)))
        except CanonicalReferenceError:
            return None

    def _update_preview_enabled(self) -> None:
        self.preview_reference_button.setEnabled(
            self.project_directory is not None and self._selected_reference() is not None
        )

    def _preview_reference(self) -> None:
        reference = self._selected_reference()
        if reference is None or self.project_directory is None:
            return
        CanonicalReferencePreviewDialog(self.project_directory, reference, self).exec()


class PreviewCAPManagerWidget(CAPManagerWidget):
    """CAP manager that opens the thumbnail-enabled CAP editor."""

    def _add(self) -> None:
        try:
            if not self.caps.available_assets():
                QMessageBox.information(
                    self, "CAP Manager", "Register an asset without a CAP before creating one."
                )
                return
            dialog = PreviewCAPEditorDialog(self.caps, self.references, parent=self)
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
            dialog = PreviewCAPEditorDialog(self.caps, self.references, profile, self)
            if not dialog.exec():
                return
            self.caps.update(asset_id, dialog.update_value())
        except (CAPError, ValueError) as exc:
            QMessageBox.critical(self, "CAP Error", str(exc))
            return
        self.refresh()
