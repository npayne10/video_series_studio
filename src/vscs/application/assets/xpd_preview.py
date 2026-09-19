"""Hardened XPD preview classification with authoritative Asset-ID conflict detection."""

from __future__ import annotations

from pathlib import Path

from vscs.application.assets.xpd_import import XPD_SHEET_NAME
from vscs.application.assets.xpd_import import (
    XPDWorkbookImportService as _BaseXPDWorkbookImportService,
)
from vscs.domain.assets import XPDImportDisposition, XPDImportItem, XPDImportPreview


class XPDWorkbookImportService(_BaseXPDWorkbookImportService):
    """Preview XPD imports while rejecting duplicate IDs and allowing scoped name reuse."""

    def preview(self, workbook_path: Path) -> XPDImportPreview:
        workbook_hash, rows = self.reader.read(workbook_path)
        existing = self.assets.list()
        by_id = {asset.asset_id.casefold(): asset for asset in existing}
        provenance = self.provenance.load()

        seen_ids: dict[str, object] = {}
        items: list[XPDImportItem] = []
        for row in rows:
            asset_id_key = row.asset_id.casefold()

            previous_id = seen_ids.get(asset_id_key) if asset_id_key else None
            if previous_id is not None:
                items.append(
                    XPDImportItem(
                        row=row,
                        disposition=XPDImportDisposition.CONFLICT,
                        reason="Asset ID appears more than once in the XPD workbook",
                        matched_asset_id=previous_id.asset_id,
                    )
                )
                continue

            item = self._classify(row, by_id, provenance)
            items.append(item)
            if row.asset_id:
                seen_ids[asset_id_key] = row

        return XPDImportPreview(
            workbook_path=str(workbook_path.expanduser().resolve(strict=False)),
            workbook_hash=workbook_hash,
            sheet_name=XPD_SHEET_NAME,
            items=tuple(items),
        )
