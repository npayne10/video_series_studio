"""UI contract coverage for editing registered assets."""

from pathlib import Path

from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.widgets.asset_manager import AssetEditDialog, AssetManagerWidget


def _asset(file_path: Path | None = Path("references/Guild_Tug_MASTER.png")) -> Asset:
    return Asset(
        id=1,
        asset_id="CAP-SHP-004",
        name="Guild Tug Ship",
        category=AssetCategory.SHIP,
        status=AssetStatus.APPROVED,
        file_path=file_path,
        tags=("guild", "ship"),
        description="Canonical tug ship.",
    )


def test_asset_edit_dialog_protects_identity_and_governs_master(qtbot, tmp_path: Path) -> None:
    dialog = AssetEditDialog(_asset(), tmp_path)
    qtbot.addWidget(dialog)

    assert dialog.asset_id.isReadOnly()
    assert dialog.master_reference.isReadOnly()
    assert dialog.master_browse_button.text() == "Browse…"
    assert dialog.master_browse_button.isEnabled()
    assert dialog.master_status.isReadOnly()
    assert (
        dialog.master_reference.text() == "references\\Guild_Tug_MASTER.png"
        or dialog.master_reference.text() == "references/Guild_Tug_MASTER.png"
    )
    assert dialog.master_status.text() == "Locked canonical authority"
    assert not dialog.master_confirmation.isEnabled()
    assert dialog.open_cap_button.text() == "Open Canonical Profile"


def test_asset_edit_dialog_preserves_category_and_status_through_qt(qtbot, tmp_path: Path) -> None:
    dialog = AssetEditDialog(_asset(None), tmp_path)
    qtbot.addWidget(dialog)

    assert dialog.category.currentData() == AssetCategory.SHIP.value
    assert dialog.status.currentData() == AssetStatus.APPROVED.value

    value = dialog.value()
    assert value.category is AssetCategory.SHIP
    assert value.status is AssetStatus.APPROVED


def test_asset_edit_dialog_marks_missing_master(qtbot, tmp_path: Path) -> None:
    dialog = AssetEditDialog(_asset(None), tmp_path)
    qtbot.addWidget(dialog)

    assert dialog.master_reference.text() == ""
    assert dialog.master_status.text() == "Missing — select a MASTER"
    assert dialog.master_browse_button.isEnabled()


def test_asset_manager_exposes_edit_selected_button(qtbot) -> None:
    class _Projects:
        project_directory = None

    class _Assets:
        projects = _Projects()

    widget = AssetManagerWidget(_Assets())  # type: ignore[arg-type]
    qtbot.addWidget(widget)

    assert widget.edit_button.text() == "Edit Selected"
