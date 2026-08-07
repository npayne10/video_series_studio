"""Domain contracts for Phase 18.2.6a XPD workbook import and synchronisation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from vscs.domain.assets.models import AssetCategory


class XPDImportDisposition(StrEnum):
    """Dry-run classification for one XPD workbook row."""

    NEW = "new"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    INVALID = "invalid"


class XPDWorkbookRow(BaseModel):
    """Normalized representation of one XAR_Master source row."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    row_number: int = Field(ge=2)
    asset_id: str = ""
    asset_name: str = ""
    category_text: str = ""
    category: AssetCategory | None = None
    subcategory: str = ""
    asset_owner: str = ""
    parent_asset: str = ""
    production_priority: str = ""
    first_season: str = ""
    first_episode: str = ""
    first_clip: str = ""
    cap_status: str = ""
    cap_version: str = ""
    svb_status: str = ""
    arc_status: str = ""
    msr_status: str = ""
    prl: str = ""
    variant_count: str = ""
    dependencies: str = ""
    image_filename: str = ""
    prompt_filename: str = ""
    last_modified: str = ""
    notes: str = ""
    raw_fields: dict[str, str] = Field(default_factory=dict)
    row_hash: str = Field(min_length=64, max_length=64)


class XPDImportItem(BaseModel):
    """Preview decision for one source row."""

    model_config = ConfigDict(frozen=True)

    row: XPDWorkbookRow
    disposition: XPDImportDisposition
    reason: str = ""
    matched_asset_id: str | None = None


class XPDImportPreview(BaseModel):
    """Immutable workbook dry-run result."""

    model_config = ConfigDict(frozen=True)

    workbook_path: str
    workbook_hash: str = Field(min_length=64, max_length=64)
    sheet_name: str
    items: tuple[XPDImportItem, ...]

    def count(self, disposition: XPDImportDisposition) -> int:
        return sum(1 for item in self.items if item.disposition is disposition)


class XPDImportReport(BaseModel):
    """Result of applying an approved preview."""

    model_config = ConfigDict(frozen=True)

    workbook_path: str
    workbook_hash: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    conflicts: int = 0
    invalid: int = 0
    imported_asset_ids: tuple[str, ...] = ()


class XPDProvenanceRecord(BaseModel):
    """Project-local provenance retained for an imported canonical asset."""

    model_config = ConfigDict(frozen=True)

    asset_id: str
    workbook_path: str
    workbook_hash: str
    sheet_name: str
    row_number: int
    row_hash: str
    raw_fields: dict[str, str]
