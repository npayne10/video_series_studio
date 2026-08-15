"""Story Workspace UI for Phase 19.5.12 canonical library reuse."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.assets import AssetService, XPDWorkbookError
from vscs.application.automation import CanonicalLibraryImportService, ShotAssetBindingService
from vscs.application.automation.xpd_binding import CanonicalMatchDiagnosticReport


def import_xpd_library(parent: QWidget | None, assets: AssetService) -> bool:
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


def show_match_diagnostics(parent: QWidget | None, report: CanonicalMatchDiagnosticReport) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Canonical XPD Match Diagnostics")
    dialog.resize(1300, 760)
    layout = QVBoxLayout(dialog)
    summary = QLabel(
        f"Entities: {report.entity_count}    Resolved: {report.resolved_count}    "
        f"Suggested: {report.suggested_count}    Ambiguous: {report.ambiguous_count}    "
        f"No match: {report.no_match_count}\n"
        "Suggestions are diagnostic only. No canonical identity is changed by this review."
    )
    layout.addWidget(summary)

    table = QTableWidget(len(report.diagnostics), 8, dialog)
    table.setHorizontalHeaderLabels(
        (
            "Story Entity",
            "Category",
            "Status",
            "Current XPD",
            "Suggested XPD",
            "Score",
            "Reason",
            "Alternatives",
        )
    )
    table.setSortingEnabled(False)
    for row, diagnostic in enumerate(report.diagnostics):
        best = diagnostic.suggestions[0] if diagnostic.suggestions else None
        alternatives = "; ".join(
            f"{item.asset_name} ({item.score:.2f})" for item in diagnostic.suggestions[1:]
        )
        values = (
            diagnostic.entity_name,
            diagnostic.entity_category,
            diagnostic.status,
            (
                f"{diagnostic.current_asset_id} — {diagnostic.current_asset_name}"
                if diagnostic.current_asset_id
                else ""
            ),
            f"{best.asset_id} — {best.asset_name}" if best is not None else "",
            f"{best.score:.2f}" if best is not None else "",
            best.reason if best is not None else "",
            alternatives,
        )
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))
    table.resizeColumnsToContents()
    table.setSortingEnabled(True)
    layout.addWidget(table, 1)
    close_button = QPushButton("Close", dialog)
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)
    dialog.exec()


def binding_summary(service: ShotAssetBindingService, *, story_id: str, revision: str) -> str:
    report = service.bind(story_id=story_id, source_revision=revision)
    return (
        f"Shots inspected: {report.shot_count}\n"
        f"Canonical Shot/Asset bindings found: {report.binding_count}\n"
        f"Unresolved Story entities remaining: {report.unresolved_entity_count}\n\n"
        "Bindings are deterministic proposal evidence only. No governed Asset Plan was marked Ready or approved."
    )
