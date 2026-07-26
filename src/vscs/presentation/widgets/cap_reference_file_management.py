"""UI integration for managed canonical reference imports and the reference gallery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox

from vscs.application.caps.file_manager import (
    CanonicalReferenceFileError,
    CanonicalReferenceFileManager,
    DuplicateFileResolution,
)
from vscs.application.caps.reference_service import CanonicalReferenceError
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceUpdate,
)
from vscs.presentation.widgets import cap_manager
from vscs.presentation.widgets.canonical_reference_gallery import CanonicalReferenceGallery


class CanonicalReferenceDropFilter(QObject):
    """Accept local files dropped onto the Canonical References gallery."""

    def __init__(self, dialog: Any) -> None:
        super().__init__(dialog)
        self.dialog = dialog

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.DragEnter:
            mime = event.mimeData()  # type: ignore[attr-defined]
            if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
                event.acceptProposedAction()  # type: ignore[attr-defined]
                return True
        if event.type() == QEvent.Type.Drop:
            mime = event.mimeData()  # type: ignore[attr-defined]
            files = [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]
            if files:
                _import_sources(self.dialog, files)
                event.acceptProposedAction()  # type: ignore[attr-defined]
                return True
        return super().eventFilter(watched, event)


def _duplicate_resolution(parent: Any, destination: Path) -> DuplicateFileResolution:
    box = QMessageBox(parent)
    box.setWindowTitle("Canonical Reference Already Exists")
    box.setText(f"A managed reference named {destination.name} already exists.")
    box.setInformativeText("Choose whether to replace it, keep both files, or cancel the import.")
    replace = box.addButton("Replace", QMessageBox.ButtonRole.DestructiveRole)
    keep_both = box.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(keep_both)
    box.exec()
    clicked = box.clickedButton()
    if clicked is replace:
        return DuplicateFileResolution.REPLACE
    if clicked is keep_both:
        return DuplicateFileResolution.KEEP_BOTH
    if clicked is cancel:
        return DuplicateFileResolution.CANCEL
    return DuplicateFileResolution.CANCEL


def _import_sources(dialog: Any, sources: list[Path]) -> None:
    if dialog.profile is None or dialog.reference_service is None or dialog.project_directory is None:
        return
    manager = CanonicalReferenceFileManager(dialog.project_directory)
    for source in sources:
        if not source.is_file():
            continue
        reference_type = manager.detect_type(source)
        destination = manager.destination_for(dialog.profile.asset_id, source, reference_type)
        resolution = DuplicateFileResolution.KEEP_BOTH
        if destination.exists() and source.resolve(strict=False) != destination.resolve(strict=False):
            resolution = _duplicate_resolution(dialog, destination)
            if resolution is DuplicateFileResolution.CANCEL:
                continue
        try:
            managed = manager.import_file(
                dialog.profile.asset_id,
                source,
                reference_type=reference_type,
                duplicate_resolution=resolution,
            )
            editor = cap_manager.CanonicalReferenceEditorDialog(
                dialog.project_directory,
                parent=dialog,
            )
            editor.title.setText(source.stem.replace("_", " ").replace("-", " ").title())
            editor.file_path.setText(str(managed.relative_path))
            editor.reference_type.setCurrentIndex(
                editor.reference_type.findData(managed.reference_type)
            )
            editor.role.setCurrentIndex(editor.role.findData(CanonicalReferenceRole.SUPPLEMENTARY))
            editor.status.setCurrentIndex(
                editor.status.findData(CanonicalReferenceStatus.IMPORTED)
            )
            editor.notes.setPlainText(
                "Managed by VSCS\n"
                f"SHA256: {managed.sha256}\n"
                f"Size: {managed.size_bytes} bytes\n"
                f"Modified: {managed.modified_at}"
            )
            if not editor.exec():
                continue
            dialog.reference_service.create(
                dialog.profile.asset_id,
                editor.create_value(dialog.profile.id),
            )
        except (CanonicalReferenceFileError, ValueError, Exception) as exc:
            QMessageBox.critical(dialog, "Canonical Reference Import Error", str(exc))
    dialog._refresh_references()


def _managed_add_reference(dialog: Any) -> None:
    if dialog.profile is None or dialog.reference_service is None or dialog.project_directory is None:
        return
    files, _ = QFileDialog.getOpenFileNames(
        dialog,
        "Import Canonical References",
        str(Path.home()),
        "All Files (*)",
    )
    if files:
        _import_sources(dialog, [Path(filename) for filename in files])


def _set_primary_reference(dialog: Any, reference_id: int) -> None:
    """Make one reference primary and demote any existing primary reference."""
    if dialog.profile is None or dialog.reference_service is None:
        return
    try:
        references = dialog.reference_service.list_for_cap(dialog.profile.asset_id)
        target = next((reference for reference in references if reference.id == reference_id), None)
        if target is None:
            return
        for reference in references:
            if (
                reference.id != reference_id
                and reference.role is CanonicalReferenceRole.PRIMARY
            ):
                dialog.reference_service.update(
                    reference.id,
                    CanonicalReferenceUpdate(role=CanonicalReferenceRole.SECONDARY),
                )
        if target.role is not CanonicalReferenceRole.PRIMARY:
            dialog.reference_service.update(
                reference_id,
                CanonicalReferenceUpdate(role=CanonicalReferenceRole.PRIMARY),
            )
    except CanonicalReferenceError as exc:
        QMessageBox.critical(dialog, "Canonical Reference Error", str(exc))
        return
    dialog._refresh_references()


def install_canonical_reference_file_management() -> None:
    """Extend the CAP editor with managed imports and a thumbnail gallery."""
    if getattr(cap_manager.CAPEditorDialog, "_managed_reference_files_installed", False):
        return

    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references
    original_selected_reference_id = cap_manager.CAPEditorDialog._selected_reference_id

    def managed_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)

        self.reference_gallery = CanonicalReferenceGallery(self)
        self.reference_gallery.reference_activated.connect(
            lambda _reference_id: self._edit_reference()
        )
        self.reference_gallery.primary_requested.connect(
            lambda reference_id: _set_primary_reference(self, reference_id)
        )

        # Retain the original table as the compatibility data model while the
        # gallery becomes the visible reference browser.
        self.references.hide()
        self.layout().insertWidget(1, self.reference_gallery, 1)

        self.reference_gallery.setAcceptDrops(True)
        self._canonical_reference_drop_filter = CanonicalReferenceDropFilter(self)
        self.reference_gallery.installEventFilter(self._canonical_reference_drop_filter)
        self.reference_gallery.gallery.installEventFilter(self._canonical_reference_drop_filter)
        self.reference_gallery.setToolTip(
            "Drop files here to copy them into managed Canonical Assets storage."
        )
        if self.profile is not None and self.project_directory is not None:
            CanonicalReferenceFileManager(self.project_directory).ensure_asset_structure(
                self.profile.asset_id
            )
        self._refresh_references()

    def managed_refresh(self: Any) -> None:
        original_refresh(self)
        gallery = getattr(self, "reference_gallery", None)
        if gallery is None:
            return
        if self.profile is None or self.reference_service is None:
            gallery.set_references((), self.project_directory)
            return
        try:
            references = self.reference_service.list_for_cap(self.profile.asset_id)
        except CanonicalReferenceError as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        gallery.set_references(references, self.project_directory)

    def managed_selected_reference_id(self: Any) -> int | None:
        gallery = getattr(self, "reference_gallery", None)
        if gallery is not None:
            reference_id = gallery.selected_reference_id()
            if reference_id is not None:
                return reference_id
        return original_selected_reference_id(self)

    cap_manager.CAPEditorDialog.__init__ = managed_init
    cap_manager.CAPEditorDialog._refresh_references = managed_refresh
    cap_manager.CAPEditorDialog._selected_reference_id = managed_selected_reference_id
    cap_manager.CAPEditorDialog._add_reference = _managed_add_reference
    cap_manager.CAPEditorDialog._managed_reference_files_installed = True
