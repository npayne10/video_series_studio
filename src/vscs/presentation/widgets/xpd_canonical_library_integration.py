"""Story Workspace UI for Phase 19.5.12 canonical library reuse."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from vscs.application.automation import CanonicalLibraryImportService, ShotAssetBindingService
from vscs.application.assets import AssetService, XPDWorkbookError


def import_xpd_library(parent: object, assets: AssetService) -> bool:
    path, _filter = QFileDialog.getOpenFileName(
        parent,
        "Import Canonical XPD Library",
        "",
        "XPD Workbooks (*.xlsx)",
    )
    if not path:
        return False
    service = CanonicalLibraryImportService(assets)
    try:
        preview = service.preview_counts(Path(path))
    except XPDWorkbookError as exc:
        QMessageBox.critical(parent, "XPD Import Error", str(exc))
        return False
    answer = QMessageBox.question(
        parent,
        "Import Canonical XPD Library",
        f"XPD rows: {preview.total_rows}\nNew: {preview.created}\nUpdates: {preview.updated}\nUnchanged: {preview.unchanged}\nConflicts: {preview.conflicts}\nInvalid: {preview.invalid}\n\nImport non-conflicting canonical assets into the current VSCS project?",
    )
    if answer != QMessageBox.StandardButton.Yes:
        return False
    report = service.import_xpd(Path(path))
    QMessageBox.information(
        parent,
        "Canonical XPD Library Imported",
        f"Created: {report.created}\nUpdated: {report.updated}\nUnchanged: {report.unchanged}\nConflicts left for human review: {report.conflicts}\nInvalid: {report.invalid}\n\nNo CAP, Master Reference or production approval was fabricated.",
    )
    return True


def binding_summary(service: ShotAssetBindingService, *, story_id: str, revision: str) -> str:
    report = service.bind(story_id=story_id, source_revision=revision)
    return (
        f"Shots inspected: {report.shot_count}\n"
        f"Canonical Shot/Asset bindings found: {report.binding_count}\n"
        f"Unresolved Story entities remaining: {report.unresolved_entity_count}\n\n"
        "Bindings are deterministic proposal evidence only. No governed Asset Plan was marked Ready or approved."
    )
