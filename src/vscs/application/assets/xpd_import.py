"""Phase 18.2.6a XPD workbook reader, dry-run classifier and import service."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from vscs.application.assets.service import AssetService
from vscs.domain.assets import (
    AssetCategory,
    AssetCreate,
    AssetStatus,
    AssetUpdate,
    XPDImportDisposition,
    XPDImportItem,
    XPDImportPreview,
    XPDImportReport,
    XPDProvenanceRecord,
    XPDWorkbookRow,
)

XPD_SHEET_NAME = "XAR_Master"
XPD_HEADERS = (
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

_CATEGORY_MAP = {
    "character": AssetCategory.CHARACTER,
    "uniform": AssetCategory.UNIFORM,
    "ship": AssetCategory.SHIP,
    "location": AssetCategory.LOCATION,
    "prop": AssetCategory.PROP,
    "planet": AssetCategory.PLANET,
    "environment": AssetCategory.ENVIRONMENT,
    "lighting": AssetCategory.LIGHTING,
    "technology": AssetCategory.TECHNOLOGY,
    "vehicle": AssetCategory.VEHICLE,
    "effect": AssetCategory.EFFECT,
    "audio": AssetCategory.AUDIO,
    "camera": AssetCategory.CAMERA,
    "reference": AssetCategory.REFERENCE,
    "other": AssetCategory.OTHER,
}


class XPDWorkbookError(RuntimeError):
    """Raised when an XPD workbook cannot be validated or read."""


class XPDWorkbookReader:
    """Read the canonical XAR_Master sheet using Python's OOXML primitives."""

    def read(self, path: Path) -> tuple[str, tuple[XPDWorkbookRow, ...]]:
        workbook_path = path.expanduser().resolve(strict=False)
        if not workbook_path.is_file():
            raise XPDWorkbookError(f"XPD workbook does not exist: {workbook_path}")
        if workbook_path.suffix.casefold() != ".xlsx":
            raise XPDWorkbookError("XPD import requires an .xlsx workbook")
        workbook_hash = hashlib.sha256(workbook_path.read_bytes()).hexdigest()
        try:
            with ZipFile(workbook_path) as archive:
                shared_strings = self._shared_strings(archive)
                sheet_path = self._sheet_path(archive, XPD_SHEET_NAME)
                rows = self._sheet_rows(archive, sheet_path, shared_strings)
        except (BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
            raise XPDWorkbookError(f"Unable to read XPD workbook: {exc}") from exc
        if not rows:
            raise XPDWorkbookError(f"{XPD_SHEET_NAME} contains no rows")
        headers = tuple(rows[0].get(index, "").strip() for index in range(len(XPD_HEADERS)))
        if headers != XPD_HEADERS:
            raise XPDWorkbookError(
                "XAR_Master schema mismatch. Expected the approved 22-column XPD v1.1 header."
            )
        normalized: list[XPDWorkbookRow] = []
        for row_number, values in enumerate(rows[1:], start=2):
            fields = {
                header: values.get(index, "").strip() for index, header in enumerate(XPD_HEADERS)
            }
            if not any(fields.values()):
                continue
            normalized.append(self._row(row_number, fields))
        return workbook_hash, tuple(normalized)

    @staticmethod
    def _shared_strings(archive: ZipFile) -> tuple[str, ...]:
        try:
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
        except KeyError:
            return ()
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        values: list[str] = []
        for item in root.findall(f"{namespace}si"):
            values.append("".join(node.text or "" for node in item.iter(f"{namespace}t")))
        return tuple(values)

    @staticmethod
    def _sheet_path(archive: ZipFile, sheet_name: str) -> str:
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        rel_namespace = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationship_id = ""
        for sheet in workbook.findall(f".//{namespace}sheet"):
            if sheet.attrib.get("name") == sheet_name:
                relationship_id = sheet.attrib.get(f"{rel_namespace}id", "")
                break
        if not relationship_id:
            raise XPDWorkbookError(f"Required worksheet not found: {sheet_name}")
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        for relationship in relationships:
            if relationship.attrib.get("Id") == relationship_id:
                target = relationship.attrib.get("Target", "")
                if target.startswith("/"):
                    return target.lstrip("/")
                return f"xl/{target.lstrip('/')}"
        raise XPDWorkbookError(f"Worksheet relationship is missing: {sheet_name}")

    @classmethod
    def _sheet_rows(
        cls,
        archive: ZipFile,
        sheet_path: str,
        shared_strings: tuple[str, ...],
    ) -> tuple[dict[int, str], ...]:
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        root = ElementTree.fromstring(archive.read(sheet_path))
        rows: list[dict[int, str]] = []
        for row in root.findall(f".//{namespace}row"):
            values: dict[int, str] = {}
            for cell in row.findall(f"{namespace}c"):
                reference = cell.attrib.get("r", "A1")
                column = cls._column_index(reference)
                cell_type = cell.attrib.get("t", "")
                value = cell.find(f"{namespace}v")
                inline = cell.find(f"{namespace}is")
                if cell_type == "inlineStr" and inline is not None:
                    text = "".join(node.text or "" for node in inline.iter(f"{namespace}t"))
                elif value is None:
                    text = ""
                elif cell_type == "s":
                    index = int(value.text or "0")
                    text = shared_strings[index] if index < len(shared_strings) else ""
                else:
                    text = value.text or ""
                values[column] = text
            rows.append(values)
        return tuple(rows)

    @staticmethod
    def _column_index(reference: str) -> int:
        letters = re.match(r"[A-Z]+", reference.upper())
        if letters is None:
            return 0
        result = 0
        for character in letters.group(0):
            result = result * 26 + ord(character) - ord("A") + 1
        return result - 1

    @staticmethod
    def _row(row_number: int, fields: dict[str, str]) -> XPDWorkbookRow:
        category_text = fields["Category"]
        category = _CATEGORY_MAP.get(category_text.casefold())
        serialized = json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return XPDWorkbookRow(
            row_number=row_number,
            asset_id=fields["Asset ID"],
            asset_name=fields["Asset Name"],
            category_text=category_text,
            category=category,
            subcategory=fields["Subcategory"],
            asset_owner=fields["Asset Owner"],
            parent_asset=fields["Parent Asset"],
            production_priority=fields["Production Priority"],
            first_season=fields["First Season"],
            first_episode=fields["First Episode"],
            first_clip=fields["First Clip"],
            cap_status=fields["CAP Status"],
            cap_version=fields["CAP Version"],
            svb_status=fields["SVB Status"],
            arc_status=fields["ARC Status"],
            msr_status=fields["MSR Status"],
            prl=fields["PRL"],
            variant_count=fields["Variant Count"],
            dependencies=fields["Dependencies"],
            image_filename=fields["Image Filename"],
            prompt_filename=fields["Prompt Filename"],
            last_modified=fields["Last Modified"],
            notes=fields["Notes"],
            raw_fields=fields,
            row_hash=hashlib.sha256(serialized).hexdigest(),
        )


class XPDProvenanceStore:
    """Persist complete workbook provenance alongside the active project."""

    FILE_NAME = "xpd_import_provenance.json"

    def __init__(self, assets: AssetService) -> None:
        self.assets = assets

    def load(self) -> dict[str, XPDProvenanceRecord]:
        path = self._path()
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return {
                asset_id: XPDProvenanceRecord.model_validate(record)
                for asset_id, record in payload.items()
            }
        except (OSError, ValueError, TypeError) as exc:
            raise XPDWorkbookError(f"Unable to read XPD provenance ledger: {exc}") from exc

    def save(self, records: dict[str, XPDProvenanceRecord]) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            asset_id: record.model_dump(mode="json") for asset_id, record in sorted(records.items())
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise XPDWorkbookError(f"Unable to write XPD provenance ledger: {exc}") from exc

    def _path(self) -> Path:
        project = self.assets.projects.project_directory
        if project is None:
            raise XPDWorkbookError("Open a VSCS project before importing XPD")
        return project / ".vscs" / self.FILE_NAME


class XPDWorkbookImportService:
    """Preview and apply one-way XPD workbook synchronization into AssetService."""

    def __init__(
        self,
        assets: AssetService,
        reader: XPDWorkbookReader | None = None,
        provenance: XPDProvenanceStore | None = None,
    ) -> None:
        self.assets = assets
        self.reader = reader or XPDWorkbookReader()
        self.provenance = provenance or XPDProvenanceStore(assets)

    def preview(self, workbook_path: Path) -> XPDImportPreview:
        workbook_hash, rows = self.reader.read(workbook_path)
        existing = self.assets.list()
        by_id = {asset.asset_id.casefold(): asset for asset in existing}
        by_name: dict[str, list[object]] = {}
        for asset in existing:
            by_name.setdefault(asset.name.casefold(), []).append(asset)
        provenance = self.provenance.load()
        items = tuple(self._classify(row, by_id, by_name, provenance) for row in rows)
        return XPDImportPreview(
            workbook_path=str(workbook_path.expanduser().resolve(strict=False)),
            workbook_hash=workbook_hash,
            sheet_name=XPD_SHEET_NAME,
            items=items,
        )

    def apply(self, preview: XPDImportPreview) -> XPDImportReport:
        provenance = self.provenance.load()
        created = updated = unchanged = conflicts = invalid = 0
        imported_ids: list[str] = []
        for item in preview.items:
            row = item.row
            if item.disposition is XPDImportDisposition.NEW:
                self.assets.create(self._asset_create(row))
                created += 1
            elif item.disposition is XPDImportDisposition.UPDATE:
                self.assets.update(row.asset_id, self._asset_update(row))
                updated += 1
            elif item.disposition is XPDImportDisposition.UNCHANGED:
                unchanged += 1
            elif item.disposition is XPDImportDisposition.CONFLICT:
                conflicts += 1
                continue
            else:
                invalid += 1
                continue
            imported_ids.append(row.asset_id)
            provenance[row.asset_id] = XPDProvenanceRecord(
                asset_id=row.asset_id,
                workbook_path=preview.workbook_path,
                workbook_hash=preview.workbook_hash,
                sheet_name=preview.sheet_name,
                row_number=row.row_number,
                row_hash=row.row_hash,
                raw_fields=row.raw_fields,
            )
        self.provenance.save(provenance)
        return XPDImportReport(
            workbook_path=preview.workbook_path,
            workbook_hash=preview.workbook_hash,
            created=created,
            updated=updated,
            unchanged=unchanged,
            conflicts=conflicts,
            invalid=invalid,
            imported_asset_ids=tuple(imported_ids),
        )

    def _classify(self, row, by_id, by_name, provenance) -> XPDImportItem:
        if not row.asset_id or not row.asset_name:
            return XPDImportItem(
                row=row,
                disposition=XPDImportDisposition.INVALID,
                reason="Asset ID and Asset Name are required",
            )
        if row.category is None:
            return XPDImportItem(
                row=row,
                disposition=XPDImportDisposition.INVALID,
                reason=f"Unsupported XPD category: {row.category_text or '(blank)'}",
            )
        current = by_id.get(row.asset_id.casefold())
        if current is not None:
            if (
                current.name.casefold() != row.asset_name.casefold()
                or current.category is not row.category
            ):
                return XPDImportItem(
                    row=row,
                    disposition=XPDImportDisposition.CONFLICT,
                    reason="Asset ID exists with a different canonical name or category",
                    matched_asset_id=current.asset_id,
                )
            previous = provenance.get(row.asset_id)
            if previous is not None and previous.row_hash == row.row_hash:
                return XPDImportItem(
                    row=row,
                    disposition=XPDImportDisposition.UNCHANGED,
                    reason="Workbook row is unchanged since the last XPD import",
                    matched_asset_id=current.asset_id,
                )
            desired = self._asset_update(row)
            if (
                current.description == desired.description
                and current.status is desired.status
                and current.tags == desired.tags
            ):
                return XPDImportItem(
                    row=row,
                    disposition=XPDImportDisposition.UNCHANGED,
                    reason="Canonical asset already matches the workbook row",
                    matched_asset_id=current.asset_id,
                )
            return XPDImportItem(
                row=row,
                disposition=XPDImportDisposition.UPDATE,
                reason="Existing asset differs from XPD workbook metadata",
                matched_asset_id=current.asset_id,
            )
        same_name = by_name.get(row.asset_name.casefold(), [])
        if same_name:
            matched = same_name[0]
            return XPDImportItem(
                row=row,
                disposition=XPDImportDisposition.CONFLICT,
                reason="Canonical name already exists under a different Asset ID",
                matched_asset_id=matched.asset_id,
            )
        return XPDImportItem(
            row=row,
            disposition=XPDImportDisposition.NEW,
            reason="New canonical XPD asset",
        )

    @staticmethod
    def _asset_status(row: XPDWorkbookRow) -> AssetStatus:
        normalized = row.cap_status.casefold()
        if normalized in {"locked", "approved"}:
            return AssetStatus.APPROVED
        if normalized in {"review", "pending review"}:
            return AssetStatus.REVIEW
        return AssetStatus.DRAFT

    @classmethod
    def _tags(cls, row: XPDWorkbookRow) -> tuple[str, ...]:
        values = (
            f"xpd:subcategory={row.subcategory}" if row.subcategory else "",
            f"xpd:owner={row.asset_owner}" if row.asset_owner else "",
            f"xpd:parent={row.parent_asset}" if row.parent_asset else "",
            f"xpd:priority={row.production_priority}" if row.production_priority else "",
            f"xpd:cap_status={row.cap_status}" if row.cap_status else "",
            f"xpd:cap_version={row.cap_version}" if row.cap_version else "",
            f"xpd:image={row.image_filename}" if row.image_filename else "",
            f"xpd:prompt={row.prompt_filename}" if row.prompt_filename else "",
        )
        return tuple(value for value in values if value)

    @classmethod
    def _asset_create(cls, row: XPDWorkbookRow) -> AssetCreate:
        if row.category is None:
            raise XPDWorkbookError("Cannot import a row with no mapped category")
        return AssetCreate(
            asset_id=row.asset_id,
            name=row.asset_name,
            category=row.category,
            description=row.notes,
            status=cls._asset_status(row),
            tags=cls._tags(row),
        )

    @classmethod
    def _asset_update(cls, row: XPDWorkbookRow) -> AssetUpdate:
        if row.category is None:
            raise XPDWorkbookError("Cannot update a row with no mapped category")
        return AssetUpdate(
            name=row.asset_name,
            category=row.category,
            description=row.notes,
            status=cls._asset_status(row),
            tags=cls._tags(row),
        )
