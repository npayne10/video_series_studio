"""Resolution-aware project asset browser for production editors."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.asset_resolution import (
    AssetBrowserFilter,
    AssetBrowserItem,
    AssetBrowserService,
    AssetResolutionStatus,
)
from vscs.application.assets import AssetError, AssetProjectNotOpenError
from vscs.domain.assets import AssetCategory, AssetStatus


class ResolutionAssetPickerDialog(QDialog):
    """Browse assets with CAP and canonical-reference readiness information."""

    def __init__(
        self,
        browser: AssetBrowserService,
        parent: QWidget | None = None,
        *,
        expected_categories: frozenset[AssetCategory] = frozenset(),
    ) -> None:
        super().__init__(parent)
        self.browser = browser
        self.expected_categories = expected_categories
        self._items: dict[str, AssetBrowserItem] = {}
        self.setWindowTitle("Browse Production Assets")
        self.resize(1080, 600)
        self.setMinimumSize(760, 460)

        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("resolutionAssetPickerSearch")
        self.search_edit.setPlaceholderText("Search by name, ID, description or tag")

        self.category_combo = QComboBox(self)
        self.category_combo.setObjectName("resolutionAssetPickerCategory")
        self.category_combo.addItem("All categories", None)
        categories = expected_categories or frozenset(AssetCategory)
        for category in sorted(categories, key=lambda item: item.value):
            self.category_combo.addItem(
                category.value.replace("_", " ").title(),
                category.value,
            )

        self.approved_only = QCheckBox("Approved assets only", self)
        self.approved_only.setObjectName("resolutionAssetPickerApprovedOnly")
        self.ready_only = QCheckBox("Production-ready only", self)
        self.ready_only.setObjectName("resolutionAssetPickerReadyOnly")

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search", self))
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(QLabel("Category", self))
        filters.addWidget(self.category_combo)
        filters.addWidget(self.approved_only)
        filters.addWidget(self.ready_only)

        self.asset_tree = QTreeWidget(self)
        self.asset_tree.setObjectName("resolutionAssetPickerTree")
        self.asset_tree.setColumnCount(9)
        self.asset_tree.setHeaderLabels(
            (
                "Name",
                "Asset ID",
                "Category",
                "Asset Status",
                "Resolution",
                "CAP Version",
                "Approved References",
                "Canonical Status",
                "Primary Reference",
            )
        )
        self.asset_tree.setRootIsDecorated(False)
        self.asset_tree.setAlternatingRowColors(True)
        self.asset_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.asset_tree.setSortingEnabled(True)
        self.asset_tree.sortItems(0, Qt.SortOrder.AscendingOrder)

        self.result_label = QLabel(self)
        self.result_label.setObjectName("resolutionAssetPickerResultCount")
        self.detail_label = QLabel(self)
        self.detail_label.setObjectName("resolutionAssetPickerDetails")
        self.detail_label.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.select_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.select_button.setText("Select Asset")
        self.select_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.asset_tree, 1)
        layout.addWidget(self.result_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.buttons)

        self.search_edit.textChanged.connect(self.refresh)
        self.category_combo.currentIndexChanged.connect(self.refresh)
        self.approved_only.toggled.connect(self.refresh)
        self.ready_only.toggled.connect(self.refresh)
        self.asset_tree.currentItemChanged.connect(self._update_selection)
        self.asset_tree.itemDoubleClicked.connect(
            lambda _item, _column: self._accept_selected()
        )
        self.buttons.accepted.connect(self._accept_selected)
        self.buttons.rejected.connect(self.reject)
        self.refresh()

    @property
    def selected_asset_id(self) -> str | None:
        item = self.asset_tree.currentItem()
        if item is None:
            return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    @property
    def selected_item(self) -> AssetBrowserItem | None:
        asset_id = self.selected_asset_id
        return self._items.get(asset_id) if asset_id is not None else None

    def refresh(self, *_args: object) -> None:
        category_value = self.category_combo.currentData()
        categories = (
            frozenset({AssetCategory(str(category_value))})
            if category_value is not None
            else self.expected_categories
        )
        statuses = (
            frozenset({AssetStatus.APPROVED})
            if self.approved_only.isChecked()
            else frozenset()
        )
        resolution_statuses = (
            frozenset({AssetResolutionStatus.RESOLVED})
            if self.ready_only.isChecked()
            else frozenset()
        )
        try:
            result = self.browser.browse(
                AssetBrowserFilter(
                    query=self.search_edit.text(),
                    categories=categories,
                    statuses=statuses,
                    resolution_statuses=resolution_statuses,
                    require_cap=self.ready_only.isChecked(),
                    require_approved_references=self.ready_only.isChecked(),
                )
            )
        except (AssetProjectNotOpenError, AssetError) as exc:
            QMessageBox.warning(self, "Browse Assets", str(exc))
            self.asset_tree.clear()
            self._items = {}
            return

        selected_id = self.selected_asset_id
        self.asset_tree.clear()
        self._items = {item.asset_id: item for item in result.items}
        for browser_item in result.items:
            canonical_status = (
                browser_item.canonical.status.value.title()
                if browser_item.canonical is not None
                else "—"
            )
            item = QTreeWidgetItem(
                (
                    browser_item.name,
                    browser_item.asset_id,
                    browser_item.category.value.replace("_", " ").title(),
                    browser_item.asset_status.value.title(),
                    browser_item.resolution_status.value.title(),
                    browser_item.cap_version or "—",
                    str(browser_item.approved_reference_count),
                    canonical_status,
                    browser_item.primary_reference_id or "—",
                )
            )
            item.setData(0, Qt.ItemDataRole.UserRole, browser_item.asset_id)
            item.setToolTip(0, browser_item.description or browser_item.name)
            self.asset_tree.addTopLevelItem(item)
            if browser_item.asset_id == selected_id:
                self.asset_tree.setCurrentItem(item)
        self.result_label.setText(
            f"{len(result.items)} matching asset(s) from "
            f"{result.total_assets} project asset(s)"
        )
        self._update_selection()

    def _update_selection(self, *_args: object) -> None:
        selected = self.selected_item
        self.select_button.setEnabled(selected is not None and selected.selectable)
        if selected is None:
            self.detail_label.clear()
            return
        messages = [
            diagnostic.message for diagnostic in selected.resolution.diagnostics
        ]
        if selected.canonical is not None:
            messages.extend(
                diagnostic.message for diagnostic in selected.canonical.diagnostics
            )
        self.detail_label.setText(
            " ".join(dict.fromkeys(messages))
            if messages
            else "Ready for selection."
        )

    def _accept_selected(self) -> None:
        selected = self.selected_item
        if selected is not None and selected.selectable:
            self.accept()
