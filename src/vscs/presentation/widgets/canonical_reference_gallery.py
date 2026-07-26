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

from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)


class CanonicalReferenceGallery(QWidget):
    """Browse canonical references as thumbnails with workflow controls."""

    reference_activated = Signal(int)
    primary_requested = Signal(int)
    candidate_requested = Signal(int)
    approve_requested = Signal(int)
    reject_requested = Signal(int)
    archive_requested = Signal(int)
    unlock_requested = Signal(int)

    REFERENCE_ID_ROLE = Qt.ItemDataRole.UserRole

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
        self.gallery.setGridSize(QSize(210, 185))
        self.gallery.setSpacing(8)
        self.gallery.setWordWrap(True)
        self.gallery.currentItemChanged.connect(self._selection_changed)
        self.gallery.itemDoubleClicked.connect(self._activate_item)

        self.preview = QLabel("No reference selected")
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
        self.approval_label = QLabel("Approval: —")
        self.approval_label.setWordWrap(True)
        self.path_label = QLabel("File: —")
        self.path_label.setWordWrap(True)
        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)

        self.primary_button = QPushButton("Set as Primary")
        self.candidate_button = QPushButton("Mark Candidate")
        self.approve_button = QPushButton("Approve")
        self.reject_button = QPushButton("Reject")
        self.archive_button = QPushButton("Archive")
        self.unlock_button = QPushButton("Unlock")
        for button in (
            self.primary_button,
            self.candidate_button,
            self.approve_button,
            self.reject_button,
            self.archive_button,
            self.unlock_button,
        ):
            button.setEnabled(False)
        self.primary_button.clicked.connect(lambda: self._emit(self.primary_requested))
        self.candidate_button.clicked.connect(lambda: self._emit(self.candidate_requested))
        self.approve_button.clicked.connect(lambda: self._emit(self.approve_requested))
        self.reject_button.clicked.connect(lambda: self._emit(self.reject_requested))
        self.archive_button.clicked.connect(lambda: self._emit(self.archive_requested))
        self.unlock_button.clicked.connect(lambda: self._emit(self.unlock_requested))

        workflow = QHBoxLayout()
        for button in (
            self.candidate_button,
            self.approve_button,
            self.reject_button,
            self.archive_button,
            self.unlock_button,
        ):
            workflow.addWidget(button)

        details = QVBoxLayout()
        details.addWidget(self.preview, 1)
        details.addWidget(self.title_label)
        details.addWidget(self.type_label)
        details.addWidget(self.role_label)
        details.addWidget(self.status_label)
        details.addWidget(self.version_label)
        details.addWidget(self.approval_label)
        details.addWidget(self.path_label)
        details.addWidget(self.description_label)
        details.addWidget(self.primary_button)
        details.addLayout(workflow)

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
        hint = QLabel("Double-click unlocked references to edit them. Approved references are production-locked.")
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.addWidget(heading)
        layout.addWidget(hint)
        layout.addWidget(splitter, 1)

    def set_references(self, references: Iterable[CanonicalReference], project_directory: Path | None) -> None:
        selected_id = self.selected_reference_id()
        self._project_directory = project_directory
        values = tuple(references)
        self._references = {reference.id: reference for reference in values}
        self.gallery.clear()
        ordered = sorted(values, key=lambda r: (0 if r.role is CanonicalReferenceRole.PRIMARY else 1, r.title.casefold(), r.id))
        selected_item: QListWidgetItem | None = None
        for reference in ordered:
            item = QListWidgetItem(self._icon_for(reference), self._display_title(reference))
            item.setData(self.REFERENCE_ID_ROLE, reference.id)
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
        item = self.gallery.currentItem()
        if item is None:
            return None
        value = item.data(self.REFERENCE_ID_ROLE)
        return None if value is None else int(value)

    def selected_reference(self) -> CanonicalReference | None:
        reference_id = self.selected_reference_id()
        return None if reference_id is None else self._references.get(reference_id)

    @staticmethod
    def _status_marker(status: CanonicalReferenceStatus) -> str:
        return {
            CanonicalReferenceStatus.IMPORTED: "●",
            CanonicalReferenceStatus.CANDIDATE: "◆",
            CanonicalReferenceStatus.APPROVED: "✓",
            CanonicalReferenceStatus.ARCHIVED: "■",
        }[status]

    def _display_title(self, reference: CanonicalReference) -> str:
        primary = "★ " if reference.role is CanonicalReferenceRole.PRIMARY else ""
        lock = " 🔒" if reference.locked else ""
        return f"{primary}{reference.title}\n{self._status_marker(reference.status)} {reference.status.value.title()}{lock}"

    def _tooltip(self, reference: CanonicalReference) -> str:
        approval = reference.approved_by or "—"
        return (
            f"{reference.title}\nType: {reference.reference_type.value.title()}\n"
            f"Role: {reference.role.value.title()}\nStatus: {reference.status.value.title()}\n"
            f"Version: {reference.version}\nApproved by: {approval}\nFile: {reference.file_path}"
        )

    def _absolute_path(self, reference: CanonicalReference) -> Path:
        if reference.file_path.is_absolute() or self._project_directory is None:
            return reference.file_path
        return self._project_directory / reference.file_path

    def _icon_for(self, reference: CanonicalReference) -> QIcon:
        path = self._absolute_path(reference)
        if reference.reference_type is CanonicalReferenceType.IMAGE and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return QIcon(pixmap.scaled(self.gallery.iconSize(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_map = {
            CanonicalReferenceType.DOCUMENT: QStyle.StandardPixmap.SP_FileIcon,
            CanonicalReferenceType.AUDIO: QStyle.StandardPixmap.SP_MediaVolume,
            CanonicalReferenceType.VIDEO: QStyle.StandardPixmap.SP_MediaPlay,
            CanonicalReferenceType.MATERIAL: QStyle.StandardPixmap.SP_DirIcon,
        }
        return self.style().standardIcon(icon_map.get(reference.reference_type, QStyle.StandardPixmap.SP_FileIcon))

    def _selection_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        reference = None if current is None else self._references.get(int(current.data(self.REFERENCE_ID_ROLE)))
        self._show_reference(reference)

    def _show_reference(self, reference: CanonicalReference | None) -> None:
        if reference is None:
            self.preview.setPixmap(QPixmap())
            self.preview.setText("No reference selected")
            for label, text in (
                (self.title_label, "—"), (self.type_label, "Type: —"), (self.role_label, "Role: —"),
                (self.status_label, "Status: —"), (self.version_label, "Version: —"),
                (self.approval_label, "Approval: —"), (self.path_label, "File: —"),
            ):
                label.setText(text)
            self.description_label.clear()
            for button in (self.primary_button, self.candidate_button, self.approve_button, self.reject_button, self.archive_button, self.unlock_button):
                button.setEnabled(False)
            return

        path = self._absolute_path(reference)
        if reference.reference_type is CanonicalReferenceType.IMAGE and path.is_file():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.preview.setText("")
                self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.preview.setPixmap(QPixmap())
                self.preview.setText("Preview unavailable")
        else:
            self.preview.setPixmap(self._icon_for(reference).pixmap(QSize(96, 96)))
            self.preview.setText("")

        self.title_label.setText(reference.title)
        self.type_label.setText(f"Type: {reference.reference_type.value.title()}")
        self.role_label.setText(f"Role: {reference.role.value.title()}")
        self.status_label.setText(f"Status: {reference.status.value.title()}{' — Locked' if reference.locked else ''}")
        self.version_label.setText(f"Version: {reference.version}")
        approved_at = reference.approved_at.astimezone().strftime("%Y-%m-%d %H:%M") if reference.approved_at else "—"
        self.approval_label.setText(f"Approved by: {reference.approved_by or '—'}\nApproved at: {approved_at}")
        self.path_label.setText(f"File: {reference.file_path}")
        self.description_label.setText(reference.description or reference.notes or "No description")

        self.primary_button.setEnabled(not reference.locked and reference.role is not CanonicalReferenceRole.PRIMARY)
        self.candidate_button.setEnabled(not reference.locked and reference.status is CanonicalReferenceStatus.IMPORTED)
        self.approve_button.setEnabled(reference.status is CanonicalReferenceStatus.CANDIDATE and not reference.locked)
        self.reject_button.setEnabled(reference.status is CanonicalReferenceStatus.APPROVED)
        self.archive_button.setEnabled(reference.status is not CanonicalReferenceStatus.ARCHIVED)
        self.unlock_button.setEnabled(reference.locked)

    def _activate_item(self, item: QListWidgetItem) -> None:
        reference_id = int(item.data(self.REFERENCE_ID_ROLE))
        reference = self._references.get(reference_id)
        if reference is not None and not reference.locked:
            self.reference_activated.emit(reference_id)

    def _emit(self, signal: Signal) -> None:
        reference_id = self.selected_reference_id()
        if reference_id is not None:
            signal.emit(reference_id)
