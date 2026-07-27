"""UI integration for managed canonical references, approvals, and generation."""

from __future__ import annotations

import getpass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from vscs.application.caps.asset_generator import (
    CanonicalAssetGenerationError,
    CanonicalAssetGeneratorService,
)
from vscs.application.caps.file_manager import (
    CanonicalReferenceFileError,
    CanonicalReferenceFileManager,
    DuplicateFileResolution,
)
from vscs.application.caps.reference_service import CanonicalReferenceError
from vscs.domain.caps import CanonicalReferenceRole, CanonicalReferenceStatus
from vscs.infrastructure.xcic import XCICImageProvider
from vscs.presentation.dialogs.canonical_asset_generation_dialog import (
    CanonicalAssetGenerationDialog,
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
    if box.clickedButton() is replace:
        return DuplicateFileResolution.REPLACE
    if box.clickedButton() is keep_both:
        return DuplicateFileResolution.KEEP_BOTH
    if box.clickedButton() is cancel:
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
            editor = cap_manager.CanonicalReferenceEditorDialog(dialog.project_directory, parent=dialog)
            editor.title.setText(source.stem.replace("_", " ").replace("-", " ").title())
            editor.file_path.setText(str(managed.relative_path))
            editor.reference_type.setCurrentIndex(editor.reference_type.findData(managed.reference_type))
            editor.role.setCurrentIndex(editor.role.findData(CanonicalReferenceRole.SUPPLEMENTARY))
            editor.status.setCurrentIndex(editor.status.findData(CanonicalReferenceStatus.IMPORTED))
            editor.status.setEnabled(False)
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
        except (CanonicalReferenceFileError, CanonicalReferenceError, ValueError, OSError) as exc:
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


def _generate_references(dialog: Any) -> None:
    if (
        dialog.profile is None
        or dialog.reference_service is None
        or dialog.project_directory is None
    ):
        return
    default_prompt = "\n\n".join(
        value for value in (
            dialog.description.toPlainText().strip(),
            dialog.visual_identity.toPlainText().strip(),
        ) if value
    )
    editor = CanonicalAssetGenerationDialog(default_prompt, dialog)
    if not editor.exec():
        return
    try:
        generator = CanonicalAssetGeneratorService(
            dialog.reference_service,
            XCICImageProvider(dialog.project_directory),
        )
        created = generator.generate(dialog.profile.asset_id, editor.request_value())
    except (CanonicalAssetGenerationError, CanonicalReferenceError, ValueError, OSError) as exc:
        QMessageBox.critical(dialog, "Canonical Asset Generation", str(exc))
        return
    dialog._refresh_references()
    QMessageBox.information(
        dialog,
        "Canonical Asset Generation",
        f"Generated {len(created)} versioned Candidate reference(s) using the "
        "XCIC Rendering Engine and ComfyUI.\n\n"
        "The generated PNG files were imported into the Canonical Reference Gallery. "
        "Prompt, model, seed, dimensions, provider, and generation time were stored in "
        "provenance manifests.",
    )


def _run_workflow(dialog: Any, action: Callable[[], object], success: str | None = None) -> None:
    try:
        action()
    except (CanonicalReferenceError, ValueError) as exc:
        QMessageBox.critical(dialog, "Canonical Reference Workflow", str(exc))
        return
    if success:
        dialog.statusTip = success
    dialog._refresh_references()


def _set_primary_reference(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None:
        _run_workflow(dialog, lambda: dialog.reference_service.set_primary(reference_id))


def _mark_candidate(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None:
        _run_workflow(dialog, lambda: dialog.reference_service.mark_candidate(reference_id))


def _approve(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is None:
        return
    reference = dialog.reference_service.get(reference_id)
    if QMessageBox.question(
        dialog,
        "Approve Canonical Reference",
        f"Approve '{reference.title}' for production?\n\nThe reference will become locked.",
    ) is not QMessageBox.StandardButton.Yes:
        return
    _run_workflow(dialog, lambda: dialog.reference_service.approve(reference_id, getpass.getuser()))


def _reject(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None and QMessageBox.question(
        dialog,
        "Return to Candidate",
        "Remove production approval and return this reference to Candidate status?",
    ) is QMessageBox.StandardButton.Yes:
        _run_workflow(dialog, lambda: dialog.reference_service.reject(reference_id))


def _archive(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None and QMessageBox.question(
        dialog,
        "Archive Canonical Reference",
        "Archive this reference? Archived references remain in the project but cannot be edited or used for production.",
    ) is QMessageBox.StandardButton.Yes:
        _run_workflow(dialog, lambda: dialog.reference_service.archive(reference_id))


def _unlock(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None and QMessageBox.question(
        dialog,
        "Unlock Canonical Reference",
        "Unlocking removes production approval and returns the reference to Candidate status. Continue?",
    ) is QMessageBox.StandardButton.Yes:
        _run_workflow(dialog, lambda: dialog.reference_service.unlock(reference_id))


def _update_edit_controls(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    enabled = reference is not None and not reference.locked
    dialog.edit_reference_button.setEnabled(enabled)
    dialog.remove_reference_button.setEnabled(enabled)


def install_canonical_reference_file_management() -> None:
    """Extend the CAP editor with managed imports, generation, gallery, and approvals."""
    if getattr(cap_manager.CAPEditorDialog, "_managed_reference_files_installed", False):
        return

    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references
    original_selected_reference_id = cap_manager.CAPEditorDialog._selected_reference_id

    def managed_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.reference_gallery = CanonicalReferenceGallery(self)
        self.reference_gallery.reference_activated.connect(lambda _id: self._edit_reference())
        self.reference_gallery.primary_requested.connect(lambda rid: _set_primary_reference(self, rid))
        self.reference_gallery.candidate_requested.connect(lambda rid: _mark_candidate(self, rid))
        self.reference_gallery.approve_requested.connect(lambda rid: _approve(self, rid))
        self.reference_gallery.reject_requested.connect(lambda rid: _reject(self, rid))
        self.reference_gallery.archive_requested.connect(lambda rid: _archive(self, rid))
        self.reference_gallery.unlock_requested.connect(lambda rid: _unlock(self, rid))
        self.reference_gallery.gallery.currentItemChanged.connect(lambda *_: _update_edit_controls(self))

        self.generate_reference_button = QPushButton("Generate Canonical Images…")
        self.generate_reference_button.setObjectName("generateCanonicalImagesButton")
        self.generate_reference_button.setEnabled(self.profile is not None and self.reference_service is not None)
        self.generate_reference_button.clicked.connect(lambda: _generate_references(self))

        self.references.hide()
        self.layout().insertWidget(1, self.reference_gallery, 1)
        self.layout().insertWidget(2, self.generate_reference_button)
        self.reference_gallery.setAcceptDrops(True)
        self._canonical_reference_drop_filter = CanonicalReferenceDropFilter(self)
        self.reference_gallery.installEventFilter(self._canonical_reference_drop_filter)
        self.reference_gallery.gallery.installEventFilter(self._canonical_reference_drop_filter)
        self.reference_gallery.setToolTip("Drop files here to copy them into managed Canonical Assets storage.")
        if self.profile is not None and self.project_directory is not None:
            CanonicalReferenceFileManager(self.project_directory).ensure_asset_structure(self.profile.asset_id)
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
        _update_edit_controls(self)

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
