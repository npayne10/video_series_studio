"""Qt coverage for the Phase 18.2.6a XPD import review surface."""

from __future__ import annotations

from pathlib import Path

from vscs.application.assets import XPDWorkbookImportService
from vscs.domain.assets import XPDImportDisposition
from vscs.presentation.dialogs.xpd_import_dialog import XPDImportDialog
from vscs.presentation.widgets.asset_manager import AssetManagerWidget

from tests.unit.test_xpd_workbook_import import _Assets, _row, _write_xpd


def test_asset_manager_exposes_xpd_import_action(tmp_path: Path, qtbot) -> None:
    widget = AssetManagerWidget(_Assets(tmp_path))
    qtbot.addWidget(widget)

    assert widget.xpd_import_button.text() == "Import / Synchronise XPD"
    assert widget.xpd_import_button.objectName() == "importSynchroniseXPD"


def test_xpd_dialog_preview_shows_dry_run_summary(tmp_path: Path, qtbot) -> None:
    workbook = tmp_path / "XPD.xlsx"
    _write_xpd(
        workbook,
        (
            _row("CAP-SHP-001", "Iron Horizon", "Ship"),
            _row("CAP-PLN-001", "Xorix", "Planet"),
        ),
    )
    service = XPDWorkbookImportService(_Assets(tmp_path))
    preview = service.preview(workbook)
    dialog = XPDImportDialog(service)
    qtbot.addWidget(dialog)

    dialog.preview_result = preview
    dialog._populate(preview)

    assert dialog.table.rowCount() == 2
    assert preview.count(XPDImportDisposition.NEW) == 2
    assert "New 2" in dialog.summary_label.text()
