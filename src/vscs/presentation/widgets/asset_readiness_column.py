"""Asset Manager readiness-column integration."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidgetItem, QWidget

from vscs.application.caps import (
    CanonicalReferenceService,
    CAPReadinessService,
    CAPService,
    ReferenceLibraryService,
)


def install_asset_readiness_column(
    asset_manager: QWidget,
    caps: CAPService,
    references: CanonicalReferenceService | None,
) -> CAPReadinessService | None:
    """Add a deterministic readiness column without coupling AssetService to CAP logic."""
    if references is None:
        return None
    service = CAPReadinessService(caps, references, ReferenceLibraryService(references))
    table = asset_manager.table
    table.setColumnCount(6)
    table.setHorizontalHeaderLabels(
        ("Asset ID", "Name", "Category", "Status", "MASTER", "Readiness")
    )
    table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    table.setSortingEnabled(True)

    original: Callable[[int, object], None] = asset_manager._populate_row

    def populate_with_readiness(row: int, asset: object) -> None:
        original(row, asset)
        asset_id = str(getattr(asset, "asset_id"))
        try:
            report = service.evaluate(asset_id)
            text = f"{report.overall_score}%"
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, report.overall_score)
            item.setToolTip(
                f"Identity {report.identity.score}% | References {report.references.score}% | "
                f"Generation {report.generation.state.value} | "
                f"Production {report.production.state.value}"
            )
        except RuntimeError:
            item = QTableWidgetItem("—")
            item.setData(Qt.ItemDataRole.UserRole, -1)
            item.setToolTip("No Canonical Profile readiness report is available")
        table.setItem(row, 5, item)

    asset_manager._populate_row = populate_with_readiness
    asset_manager.readiness_service = service
    return service
