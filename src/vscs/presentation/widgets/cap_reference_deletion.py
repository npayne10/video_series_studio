"""Managed deletion for canonical references and their physical files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.reference_service import CanonicalReferenceError
from vscs.presentation.widgets import cap_manager


def _generation_manifest(project_directory: Path, asset_id: str, image_path: Path) -> Path:
    return (
        project_directory
        / "Canonical Assets"
        / asset_id.upper()
        / ".metadata"
        / "generation"
        / f"{image_path.stem}.generation.json"
    )


def _remove_reference(dialog: Any) -> None:
    """Remove a database reference, optionally deleting its managed file and manifest."""
    if dialog.reference_service is None or dialog.project_directory is None:
        return
    reference_id = dialog._selected_reference_id()
    if reference_id is None:
        return

    try:
        reference = dialog.reference_service.get(reference_id)
    except CanonicalReferenceError as exc:
        QMessageBox.critical(dialog, "Canonical Reference Error", str(exc))
        return

    if reference.locked:
        QMessageBox.warning(
            dialog,
            "Canonical Reference Locked",
            "Approved or archived references are locked. Unlock the reference before deleting it.",
        )
        return

    box = QMessageBox(dialog)
    box.setWindowTitle("Delete Canonical Reference")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(f"Delete '{reference.title}'?")
    box.setInformativeText(
        "Choose whether to remove only the gallery/database reference, or permanently delete "
        "the managed file and its generation manifest as well."
    )
    delete_all = box.addButton("Delete File and Reference", QMessageBox.ButtonRole.DestructiveRole)
    reference_only = box.addButton("Remove Reference Only", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()

    selected = box.clickedButton()
    if selected is cancel or selected is None:
        return

    absolute_file = (dialog.project_directory / reference.file_path).resolve(strict=False)
    project_root = dialog.project_directory.resolve(strict=False)
    try:
        absolute_file.relative_to(project_root)
    except ValueError:
        QMessageBox.critical(
            dialog,
            "Canonical Reference Error",
            f"The reference file is outside the active project and cannot be deleted:\n{absolute_file}",
        )
        return

    try:
        dialog.reference_service.delete(reference_id)
    except CanonicalReferenceError as exc:
        QMessageBox.critical(dialog, "Canonical Reference Error", str(exc))
        return

    cleanup_errors: list[str] = []
    if selected is delete_all:
        candidates = [absolute_file]
        if dialog.profile is not None:
            candidates.append(
                _generation_manifest(dialog.project_directory, dialog.profile.asset_id, absolute_file)
            )
        for path in candidates:
            try:
                if path.is_file():
                    path.unlink()
            except OSError as exc:
                cleanup_errors.append(f"{path}: {exc}")

    dialog._refresh_references()
    if cleanup_errors:
        QMessageBox.warning(
            dialog,
            "Reference Removed; File Cleanup Incomplete",
            "The database reference was removed, but some files could not be deleted:\n\n"
            + "\n".join(cleanup_errors),
        )


def install_canonical_reference_deletion() -> None:
    """Install managed physical-file deletion into the CAP editor."""
    if getattr(cap_manager.CAPEditorDialog, "_managed_reference_deletion_installed", False):
        return
    cap_manager.CAPEditorDialog._remove_reference = _remove_reference
    cap_manager.CAPEditorDialog._managed_reference_deletion_installed = True
