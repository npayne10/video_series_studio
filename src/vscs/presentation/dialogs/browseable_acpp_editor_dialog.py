"""ACPP Editor extension with project-aware canonical asset browsing."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.application.acpp import ACPPEditorService, AssetBindingRole
from vscs.application.assets import AssetService
from vscs.application.shots import ProductionShot

from .acpp_editor_dialog import ACPPEditorDialog
from .asset_picker_dialog import AssetPickerDialog


class BrowseableACPPEditorDialog(ACPPEditorDialog):
    """Add canonical project asset browsing to the ACPP Assets tab."""

    def __init__(
        self,
        shot: ProductionShot,
        service: ACPPEditorService,
        assets: AssetService,
        parent: QWidget | None = None,
    ) -> None:
        self.assets = assets
        super().__init__(shot, service, parent)

    def _build_assets_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.asset_list = QListWidget()
        self.asset_list.setObjectName("acppAssetBindingList")

        self.asset_id_edit = QLineEdit()
        self.asset_id_edit.setObjectName("acppAssetId")
        self.asset_id_edit.setPlaceholderText(
            "Enter an Asset ID or browse the project catalog"
        )

        self.browse_asset_button = QPushButton("Browse Assets…")
        self.browse_asset_button.setObjectName("browseACPPAssets")
        self.browse_asset_button.setToolTip(
            "Browse canonical assets registered in the active VSCS project."
        )

        self.asset_role_combo = QComboBox()
        self.asset_role_combo.setObjectName("acppAssetRole")
        for role in AssetBindingRole:
            self.asset_role_combo.addItem(role.value.title(), role.value)

        self.add_asset_button = QPushButton("Add Asset")
        self.remove_asset_button = QPushButton("Remove Selected")

        row = QHBoxLayout()
        row.addWidget(QLabel("Asset"))
        row.addWidget(self.asset_id_edit, 1)
        row.addWidget(self.browse_asset_button)
        row.addWidget(self.asset_role_combo)
        row.addWidget(self.add_asset_button)
        row.addWidget(self.remove_asset_button)

        layout.addWidget(self.asset_list, 1)
        layout.addLayout(row)

        self.browse_asset_button.clicked.connect(self._browse_asset)
        self.add_asset_button.clicked.connect(self._add_asset)
        self.remove_asset_button.clicked.connect(self._remove_asset)
        self.tabs.addTab(page, "Assets")

    def _browse_asset(self) -> None:
        picker = AssetPickerDialog(self.assets, self)
        if picker.exec() != AssetPickerDialog.DialogCode.Accepted:
            return
        asset_id = picker.selected_asset_id
        if asset_id is None:
            return
        self.asset_id_edit.setText(asset_id)
        self._add_asset()
