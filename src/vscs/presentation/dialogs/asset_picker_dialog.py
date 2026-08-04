"""Project-aware canonical asset picker for production editors."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from vscs.application.assets import (
    AssetError,
    AssetProjectNotOpenError,
    AssetService,
)
from vscs.domain.assets import Asset, AssetCategory


class AssetPickerDialog(QDialog):
    """Browse and select one canonical asset from the active project."""

    def __init__(
        self,
        assets: AssetService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.assets = assets
        self._all_assets: tuple[Asset, ...] = ()
        self.setWindowTitle("Browse Project Assets")
        self.resize(820, 560)
        self.setMinimumSize(640, 420)

        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("assetPickerSearch")
        self.search_edit.setPlaceholderText("Search by asset name, ID, description or tag")

        self.category_combo = QComboBox(self)
        self.category_combo.setObjectName("assetPickerCategory")
        self.category_combo.addItem("All categories", None)
        for category in AssetCategory:
            self.category_combo.addItem(
                category.value.replace("_", " ").title(),
                category.value,
            )

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Search", self))
        filters.addWidget(self.search_edit, 1)
        filters.addWidget(QLabel("Category", self))
        filters.addWidget(self.category_combo)

        self.asset_tree = QTreeWidget(self)
        self.asset_tree.setObjectName("assetPickerTree")
        self.asset_tree.setColumnCount(4)
        self.asset_tree.setHeaderLabels(("Name", "Asset ID", "Category", "Status"))
        self.asset_tree.setRootIsDecorated(False)
        self.asset_tree.setAlternatingRowColors(True)
        self.asset_tree.setSelectionMode(
            QTreeWidget.SelectionMode.SingleSelection
        )
        self.asset_tree.setSortingEnabled(True)
        self.asset_tree.sortItems(0, Qt.SortOrder.AscendingOrder)

        self.result_label = QLabel(self)
        self.result_label.setObjectName("assetPickerResultCount")

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.select_button = self.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.select_button.setText("Select Asset")
        self.select_button.setEnabled(False)

        layout = QVBoxLayout(self)
        layout.addLayout(filters)
        layout.addWidget(self.asset_tree, 1)
        layout.addWidget(self.result_label)
        layout.addWidget(self.buttons)

        self.search_edit.textChanged.connect(self._apply_filters)
        self.category_combo.currentIndexChanged.connect(self._apply_filters)
        self.asset_tree.currentItemChanged.connect(self._update_selection)
        self.asset_tree.itemDoubleClicked.connect(
            lambda _item, _column: self._accept_selected()
        )
        self.buttons.accepted.connect(self._accept_selected)
        self.buttons.rejected.connect(self.reject)

        self._load_assets()

    @property
    def selected_asset_id(self) -> str | None:
        """Return the selected canonical asset identifier."""
        item = self.asset_tree.currentItem()
        if item is None:
            return None
        value = item.data(0, Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _load_assets(self) -> None:
        try:
            self._all_assets = self.assets.list()
        except (AssetProjectNotOpenError, AssetError) as exc:
            QMessageBox.warning(self, "Browse Assets", str(exc))
            self._all_assets = ()
        self._apply_filters()

    def _apply_filters(self, *_args: object) -> None:
        query = self.search_edit.text().strip().casefold()
        category_value = self.category_combo.currentData()
        selected_id = self.selected_asset_id
        self.asset_tree.clear()
        matches = tuple(
            asset
            for asset in self._all_assets
            if self._matches(asset, query, category_value)
        )
        for asset in matches:
            item = QTreeWidgetItem(
                (
                    asset.name,
                    asset.asset_id,
                    asset.category.value.replace("_", " ").title(),
                    asset.status.value.title(),
                )
            )
            item.setData(0, Qt.ItemDataRole.UserRole, asset.asset_id)
            item.setToolTip(0, asset.description or asset.name)
            self.asset_tree.addTopLevelItem(item)
            if asset.asset_id == selected_id:
                self.asset_tree.setCurrentItem(item)
        self.result_label.setText(f"{len(matches)} project asset(s)")
        self.asset_tree.resizeColumnToContents(0)
        self.asset_tree.resizeColumnToContents(1)
        self._update_selection()

    @staticmethod
    def _matches(
        asset: Asset,
        query: str,
        category_value: object,
    ) -> bool:
        if category_value is not None and asset.category.value != str(category_value):
            return False
        if not query:
            return True
        searchable = " ".join(
            (
                asset.asset_id,
                asset.name,
                asset.description,
                asset.category.value,
                *asset.tags,
            )
        ).casefold()
        return query in searchable

    def _update_selection(self, *_args: object) -> None:
        self.select_button.setEnabled(self.selected_asset_id is not None)

    def _accept_selected(self) -> None:
        if self.selected_asset_id is not None:
            self.accept()
