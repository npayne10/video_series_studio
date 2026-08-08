"""UI contract coverage for editing registered assets."""

from pathlib import Path

from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.widgets.asset_manager import AssetEditDialog, AssetManagerWidget


def _asset() -> Asset:
    return Asset(
        id=1,
        asset_id="CAP-SHP-004",
        name="Guild Tug Ship",
        category=AssetCategory.SHIP,
        status=AssetStatus.APPROVED,
        file_path=Path("references/Guild_Tug_MASTER.png"),
        tags=("guild", "ship"),
        description="Canonical tug ship.",
    )


def test_asset_edit_dialog_protects_identity_and_master(qtbot) -> None:
    dialog = AssetEditDialog(_asset())
    qtbot.addWidget(dialog)

    assert dialog.asset_id.isReadOnly()
    assert dialog.master_reference.isReadOnly()
    assert dialog.master_status.isReadOnly()
    assert dialog.master_reference.text() == "references\\Guild_Tug_MASTER.png" or dialog.master_reference.text() == "references/Guild_Tug_MASTER.png"
    assert dialog.open_cap_button.text() == "Open Canonical Profile"


def test_asset_manager_exposes_edit_selected_button(qtbot) -> None:
    class _Projects:
        project_directory = None

    class _Assets:
        projects = _Projects()

    widget = AssetManagerWidget(_Assets())  # type: ignore[arg-type]
    qtbot.addWidget(widget)

    assert widget.edit_button.text() == "Edit Selected"
