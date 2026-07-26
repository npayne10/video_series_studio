"""Thumbnail gallery for Canonical Asset Profile reference files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from vscs.domain.caps import CanonicalReference, CanonicalReferenceRole, CanonicalReferenceType


class CanonicalReferenceGallery(QWidget):
    """Browse canonical references as thumbnails with a metadata inspector."""

    reference_activated = Signal(int)
    primary_requested = Signal(int)

    REFERENCE_ID_ROLE = Qt.ItemDataRole.UserRole
    REFERENCE_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._references: dict[int, CanonicalReference] = {}
        self._project_directory: Path | None = None

        self.gallery = QListWidget()
        self.gallery.setObjectName("canonicalReferenceGallery")
        self.gallery.setViewMode(QListWidget.ViewMode.IconMode)
        self.gallery.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.gallery.setMovement(QListWidget.Movement.Static)
        self.gallery.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.gallery.setIconSize(QSize(180, 120))
        self.gallery.setGridSize(QSize(210, 175))
        self.gallery.setSpacing(8)
        self.gallery.setWordWrap(True)
        self.gallery.currentItemChanged.connect(self._selection_changed)
        self.gallery.itemDoubleClicked.connect(self._activate_item)

        self.preview = QLabel("No reference selected")
        self.preview.setObjectName("canonicalReferencePreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(280, 180)
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.title_label = QLabel("—")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight: 600;")
        self.type_label = QLabel("Type: —")
        self.role_label = QLabel("Role: —")
        self.status_label = QLabel("Status: —")
        self.version_label = QLabel("Version: —")
        self.path_label = QLabel("File: —")
        self.path_label.setWordWrap(True)
        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)

        self.primary_button = QPushButton("Set as Primary")
        self.primary_button.setObjectName("setPrimaryReferenceButton")
        self.primary_button.setEnabled(False)
        self.primary_button.clicked.connect(self._request_primary)

        details = QVBoxLayout()
        details.addWidget(self.preview, 1)
        details.addWidget(self.title_label)
        details.addWidget(self.type_label)
        details.addWidget(self.role_label)
        details.addWidget(self.status_label)
        details.addWidget(self.version_label)
        details.addWidget(self.path_label)
        details.addWidget(self.description_label)
        details.addWidget(self.primary_button)

        detail_widget = QWidget()
        detail_widget.setLayout(details)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.gallery)
        splitter.addWidget(detail_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([620, 360])

        heading = QLabel("Canonical Reference Gallery")
        heading.setStyleSheet("font-weight: 600; font-size: 14px;")
        hint = QLabel("Double-click a reference to edit its metadata. Select an item to inspect it.")
        hint.setWordWrap(True)

        header = QHBoxLayout()
        header.addWidget(heading)
        header.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.addLayout(header)
        layout.addWidget(hint)
        layout.addWidget(splitter, 1)

    def set_references(
        self,
        references: Iterable[CanonicalReference],
        project_directory: Path | None,
    ) -> None:
        """Replace the gallery contents while preserving the selected reference."""
        selected_id = self.selected_reference_id()
        self._project_directory = project_directory
        values = tuple(references)
        self._references = {reference.id: reference for reference in values}
        self.gallery.clear()

        ordered = sorted(
            values,
            key=lambda reference: (
                0 if reference.role is CanonicalReferenceRole.PRIMARY else 1,
                reference.title.casefold(),
                reference.id,
            ),
        )
        selected_item: QListWidgetItem | None = None
        for reference in ordered:
            item = QListWidgetItem(self._icon_for(reference), self._display_title(reference))
            item.setData(self.REFERENCE_ID_ROLE, reference.id)
            item.setData(self.REFERENCE_ROLE, reference.role.value)
            item.setToolTip(self._tooltip(reference))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            self.gallery.addItem(item)
            if reference.id == selected_id:
                selected_item = item

        if selected_item is not None:
            self.gallery.setCurrentItem(selected_item)
        elif self.gallery.count():
            self.gallery.setCurrentRow(0)
        else:
            self._show_reference(None)

    def selected_reference_id(self) -> int | None:
        """Return the database ID of the selected gallery item."""
        item = self.gallery.currentItem()
        if item is None:
            return None
        value = item.data(self.REFERENCE_ID_ROLE)
        return None if value is None else int(value)

    def _display_title(self, reference: CanonicalReference) -> str:
        marker = "★ " if reference.role is CanonicalReferenceRole.PRIMARY else ""
        return f"{marker}{reference.title}\n{reference.status.value.title()}"

    def _tooltip(self, reference: CanonicalReference) -> str:
        return (
            f"{reference.title}\n"
            f"Type: {reference.reference_type.value.title()}\n"
            f"Role: {reference.role.value.title()}\n"
            f"Status: {reference.status.value.title()}\n"
            f"Version: {reference.version}\n"
            f"File: {reference.file_path}"
        )

    def _absolute_path(self, reference: CanonicalReference) -> Path:
        path = reference.file_path
        if path.is_absolute() or self._project_directory is None:
            return path
        return self._project_directory / path

    def _icon_for(self, reference: CanonicalReference) -> QIcon:
        path = self._absolute_path(reference)
        if reference.reference_type is CanonicalReferenceType.IMAGE and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                thumbnail = pixmap.scaled(
                    self.gallery.iconSize(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                return QIcon(thumbnail)

        icon_map = {
            CanonicalReferenceType.DOCUMENT: QStyle.StandardPixmap.SP_FileIcon,
            CanonicalReferenceType.AUDIO: QStyle.StandardPixmap.SP_MediaVolume,
            CanonicalReferenceType.VIDEO: QStyle.StandardPixmap.SP_MediaPlay,
            CanonicalReferenceType.MATERIAL: QStyle.StandardPixmap.SP_DirIcon,
        }
        standard = icon_map.get(reference.reference_type, QStyle.StandardPixmap.SP_FileIcon)
        return self.style().standardIcon(standard)

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._show_reference(None)
            return
        reference_id = int(current.data(self.REFERENCE_ID_ROLE))
        self._show_reference(self._references.get(reference_id))

    def _show_reference(self, reference: CanonicalReference | None) -> None:
        if reference is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("No reference selected")
            self.title_label.setText("—")
            self.type_label.setText("Type: —")
            self.role_label.setText("Role: —")
            self.status_label.setText("Status: —")
            self.version_label.setText("Version: —")
            self.path_label.setText("File: —")
            self.description_label.clear()
            self.primary_button.setEnabled(False)
            return

        path = self._absolute_path(reference)
        if reference.reference_type is CanonicalReferenceType.IMAGE and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.preview.setText("")
                self.preview.setPixmap(
                    pixmap.scaled(
                        self.preview.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self.preview.setPixmap(QPixmap())
                self.preview.setText("Preview unavailable")
        else:
            self.preview.setPixmap(self._icon_for(reference).pixmap(QSize(96, 96)))
            self.preview.setText("")

        self.title_label.setText(reference.title)
        self.type_label.setText(f"Type: {reference.reference_type.value.title()}")
        self.role_label.setText(f"Role: {reference.role.value.title()}")
        self.status_label.setText(f"Status: {reference.status.value.title()}")
        self.version_label.setText(f"Version: {reference.version}")
        self.path_label.setText(f"File: {reference.file_path}")
        self.description_label.setText(reference.description or reference.notes or "No description")
        self.primary_button.setEnabled(reference.role is not CanonicalReferenceRole.PRIMARY)

    def _activate_item(self, item: QListWidgetItem) -> None:
        reference_id = item.data(self.REFERENCE_ID_ROLE)
        if reference_id is not None:
            self.reference_activated.emit(int(reference_id))

    def _request_primary(self) -> None:
        reference_id = self.selected_reference_id()
        if reference_id is not None:
            self.primary_requested.emit(reference_id)
