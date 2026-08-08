"""Asset Manager readiness-column integration."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHeaderView, QTableWidgetItem, QWidget

from vscs.application.caps import (
    CanonicalReferenceService,
    CAPReadinessService,
    CAPService,
    ReferenceLibraryService,
)

_STATE_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class _ReadinessItem(QTableWidgetItem):
    """Sort readiness percentages numerically rather than as display text."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        left = self.data(Qt.ItemDataRole.UserRole)
        right = other.data(Qt.ItemDataRole.UserRole)
        if isinstance(left, int) and isinstance(right, int):
            return left < right
        return super().__lt__(other)


def install_asset_readiness_column(
    asset_manager: QWidget,
    caps: CAPService,
    references: CanonicalReferenceService | None,
) -> CAPReadinessService | None:
    """Add deterministic readiness sorting/filtering without coupling it to AssetService."""
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

    readiness_filter = QComboBox()
    readiness_filter.setObjectName("assetReadinessFilter")
    readiness_filter.addItem("Readiness: All", "all")
    readiness_filter.addItem("Readiness: Ready", "ready")
    readiness_filter.addItem("Readiness: Partial", "partial")
    readiness_filter.addItem("Readiness: Blocked", "blocked")
    controls = asset_manager.layout().itemAt(0).layout()
    if controls is not None:
        controls.insertWidget(2, readiness_filter)

    original: Callable[[int, object], None] = asset_manager._populate_row

    def populate_with_readiness(row: int, asset: object) -> None:
        original(row, asset)
        asset_id = str(getattr(asset, "asset_id"))
        try:
            report = service.evaluate(asset_id)
            item = _ReadinessItem(f"{report.overall_score}%")
            item.setData(Qt.ItemDataRole.UserRole, report.overall_score)
            state = "ready" if report.production_ready else (
                "blocked" if report.blocking_gaps else "partial"
            )
            item.setData(_STATE_ROLE, state)
            item.setToolTip(
                f"Identity {report.identity.score}% | References {report.references.score}% | "
                f"Generation {report.generation.state.value} | "
                f"Production {report.production.state.value}"
            )
        except RuntimeError:
            item = _ReadinessItem("—")
            item.setData(Qt.ItemDataRole.UserRole, -1)
            item.setData(_STATE_ROLE, "partial")
            item.setToolTip("No Canonical Profile readiness report is available")
        table.setItem(row, 5, item)

    def apply_filter() -> None:
        selected = str(readiness_filter.currentData() or "all")
        for row in range(table.rowCount()):
            item = table.item(row, 5)
            state = str(item.data(_STATE_ROLE) if item is not None else "partial")
            table.setRowHidden(row, selected != "all" and state != selected)

    asset_manager._populate_row = populate_with_readiness
    readiness_filter.currentIndexChanged.connect(apply_filter)
    asset_manager.search_input.textChanged.connect(apply_filter)
    asset_manager.category_filter.currentIndexChanged.connect(apply_filter)
    asset_manager.refresh_button.clicked.connect(apply_filter)
    asset_manager.readiness_service = service
    asset_manager.readiness_filter = readiness_filter
    return service
