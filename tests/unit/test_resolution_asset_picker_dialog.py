"""UI coverage for canonical readiness in the production asset picker."""

from PySide6.QtWidgets import QApplication

from vscs.application.asset_resolution import (
    AssetBrowserFilter,
    AssetBrowserItem,
    AssetBrowserResult,
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionStatus,
    CanonicalReferenceBinding,
    CanonicalResolutionRequest,
    CanonicalResolutionResult,
    CanonicalResolutionStatus,
    ResolvedAssetBinding,
    ResolvedCAPBinding,
)
from vscs.domain.assets import AssetCategory, AssetStatus
from vscs.domain.caps import (
    CAPStatus,
    CanonicalReferenceRole,
    CanonicalReferenceType,
)
from vscs.presentation.dialogs.resolution_asset_picker_dialog import (
    ResolutionAssetPickerDialog,
)


class _Browser:
    def browse(self, filter_: AssetBrowserFilter) -> AssetBrowserResult:
        asset = ResolvedAssetBinding(
            "CAP-SHP-IRON-HORIZON",
            "Iron Horizon",
            AssetCategory.SHIP,
            "Guild survey spacecraft.",
            AssetStatus.APPROVED,
            ("guild", "ship"),
            "asset-checksum",
        )
        cap = ResolvedCAPBinding(
            asset.asset_id,
            "Iron Horizon",
            "2.0",
            CAPStatus.APPROVED,
            "A 145 metre Guild survey spacecraft.",
            "Four rear fusion engines.",
            "Controlled blue-white engine trails.",
            "cap-checksum",
        )
        reference = CanonicalReferenceBinding(
            "7",
            "Iron Horizon primary",
            "references/iron_horizon.png",
            CanonicalReferenceType.IMAGE,
            CanonicalReferenceRole.PRIMARY,
            "1.0",
            "Approved production view.",
            "Stable reference.",
            "reference-checksum",
        )
        resolution = AssetResolutionResult(
            AssetResolutionRequest(asset.asset_id),
            AssetResolutionStatus.RESOLVED,
            asset,
            cap,
        )
        canonical = CanonicalResolutionResult(
            CanonicalResolutionRequest(asset.asset_id),
            CanonicalResolutionStatus.READY,
            cap,
            (reference,),
            reference,
        )
        item = AssetBrowserItem(
            asset.asset_id,
            asset.name,
            asset.category,
            asset.status,
            asset.description,
            asset.tags,
            resolution,
            canonical,
        )
        return AssetBrowserResult(filter_, (item,), 1)


def test_picker_displays_canonical_status_and_primary_reference(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ResolutionAssetPickerDialog(_Browser())  # type: ignore[arg-type]
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    assert dialog.asset_tree.columnCount() == 9
    row = dialog.asset_tree.topLevelItem(0)
    assert row.text(7) == "Ready"
    assert row.text(8) == "7"
    dialog.asset_tree.setCurrentItem(row)
    assert dialog.selected_asset_id == "CAP-SHP-IRON-HORIZON"
    assert dialog.select_button.isEnabled()
