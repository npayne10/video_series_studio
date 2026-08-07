"""Unit coverage for Phase 18.2.6a XPD workbook import foundation."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from vscs.application.assets import XPDWorkbookImportService, XPDWorkbookReader
from vscs.domain.assets import (
    Asset,
    AssetCategory,
    AssetStatus,
    XPDImportDisposition,
)

_HEADERS = (
    "Asset ID",
    "Asset Name",
    "Category",
    "Subcategory",
    "Asset Owner",
    "Parent Asset",
    "Production Priority",
    "First Season",
    "First Episode",
    "First Clip",
    "CAP Status",
    "CAP Version",
    "SVB Status",
    "ARC Status",
    "MSR Status",
    "PRL",
    "Variant Count",
    "Dependencies",
    "Image Filename",
    "Prompt Filename",
    "Last Modified",
    "Notes",
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Assets:
    def __init__(self, root: Path, initial: tuple[Asset, ...] = ()) -> None:
        self.projects = _Projects(root)
        self._items = {asset.asset_id: asset for asset in initial}
        self._next_id = len(self._items) + 1

    def list(self, **_kwargs) -> tuple[Asset, ...]:
        return tuple(self._items.values())

    def create(self, value):
        asset = Asset(
            id=self._next_id,
            asset_id=value.asset_id,
            name=value.name,
            category=value.category,
            description=value.description,
            status=value.status,
            file_path=value.file_path,
            tags=value.tags,
        )
        self._next_id += 1
        self._items[asset.asset_id] = asset
        return asset

    def update(self, asset_id, changes):
        current = self._items[asset_id]
        values = changes.model_dump(exclude_unset=True)
        updated = current.model_copy(update=values)
        self._items[asset_id] = updated
        return updated


def _column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _write_xpd(path: Path, data_rows: tuple[tuple[str, ...], ...]) -> None:
    rows = (_HEADERS, *data_rows)
    xml_rows: list[str] = []
    for row_number, values in enumerate(rows, start=1):
        cells = []
        for column, value in enumerate(values):
            ref = f"{_column_name(column)}{row_number}"
            escaped = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="XAR_Master" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", relationships)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


def _row(asset_id: str, name: str, category: str, notes: str = "") -> tuple[str, ...]:
    values = [""] * 22
    values[0] = asset_id
    values[1] = name
    values[2] = category
    values[3] = "Human" if category == "Character" else ""
    values[6] = "A"
    values[10] = "Locked"
    values[11] = "1.0"
    values[18] = f"{asset_id}.png"
    values[19] = f"{asset_id}.md"
    values[21] = notes
    return tuple(values)


def test_reader_parses_approved_xar_master_schema(tmp_path: Path) -> None:
    workbook = tmp_path / "XPD.xlsx"
    _write_xpd(workbook, (_row("CAP-CHR-001", "Commander James Spence", "Character"),))

    workbook_hash, rows = XPDWorkbookReader().read(workbook)

    assert len(workbook_hash) == 64
    assert len(rows) == 1
    assert rows[0].asset_id == "CAP-CHR-001"
    assert rows[0].asset_name == "Commander James Spence"
    assert rows[0].category is AssetCategory.CHARACTER
    assert rows[0].raw_fields["CAP Status"] == "Locked"


def test_preview_classifies_new_update_unchanged_conflict_and_invalid(tmp_path: Path) -> None:
    workbook = tmp_path / "XPD.xlsx"
    _write_xpd(
        workbook,
        (
            _row("CAP-SHP-001", "Iron Horizon", "Ship", "Survey vessel"),
            _row("CAP-CHR-001", "Commander James Spence", "Character", "Changed note"),
            _row("CAP-PLN-001", "Xorix", "Planet"),
            _row("CAP-OLD-999", "Iron Horizon", "Ship"),
            _row("CAP-BAD-001", "Bad", "UnknownCategory"),
        ),
    )
    existing = (
        Asset(
            id=1,
            asset_id="CAP-CHR-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            description="Old note",
            status=AssetStatus.APPROVED,
            file_path=None,
            tags=(),
        ),
        Asset(
            id=2,
            asset_id="CAP-PLN-001",
            name="Xorix",
            category=AssetCategory.PLANET,
            description="",
            status=AssetStatus.APPROVED,
            file_path=None,
            tags=(
                "xpd:priority=A",
                "xpd:cap_status=Locked",
                "xpd:cap_version=1.0",
                "xpd:image=CAP-PLN-001.png",
                "xpd:prompt=CAP-PLN-001.md",
            ),
        ),
    )
    service = XPDWorkbookImportService(_Assets(tmp_path, existing))

    preview = service.preview(workbook)
    dispositions = {item.row.asset_id: item.disposition for item in preview.items}

    assert dispositions["CAP-SHP-001"] is XPDImportDisposition.NEW
    assert dispositions["CAP-CHR-001"] is XPDImportDisposition.UPDATE
    assert dispositions["CAP-PLN-001"] is XPDImportDisposition.UNCHANGED
    assert dispositions["CAP-OLD-999"] is XPDImportDisposition.CONFLICT
    assert dispositions["CAP-BAD-001"] is XPDImportDisposition.INVALID


def test_apply_imports_assets_and_retains_complete_provenance(tmp_path: Path) -> None:
    workbook = tmp_path / "XPD.xlsx"
    _write_xpd(workbook, (_row("CAP-SHP-001", "Iron Horizon", "Ship", "Survey vessel"),))
    assets = _Assets(tmp_path)
    service = XPDWorkbookImportService(assets)

    preview = service.preview(workbook)
    report = service.apply(preview)

    assert report.created == 1
    imported = assets.list()[0]
    assert imported.asset_id == "CAP-SHP-001"
    assert imported.category is AssetCategory.SHIP
    assert imported.status is AssetStatus.APPROVED
    provenance = service.provenance.load()["CAP-SHP-001"]
    assert provenance.raw_fields["Asset Name"] == "Iron Horizon"
    assert provenance.raw_fields["Notes"] == "Survey vessel"
    assert len(provenance.workbook_hash) == 64
