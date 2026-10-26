"""Read-only CAP DOCX preview and explicitly reviewed Draft CAP import.

This module never auto-creates assets, CAPs, references, or approvals. The operator
must map a proposal to an existing Draft CAP before applying the specification.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from vscs.application.caps.structured_specification import (
    CAPSpecificationError,
    CAPStructuredSpecification,
    CAPStructuredSpecificationService,
)
from vscs.domain.assets.models import AssetCategory

_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_ID = re.compile(r"^CAP-([A-Z]{3})-(\d{3,})\s+v\d+(?:\.\d+)?$", re.IGNORECASE)
_CATEGORY_CODES = {
    "CHR": AssetCategory.CHARACTER,
    "LOC": AssetCategory.LOCATION,
    "SHP": AssetCategory.SHIP,
    "VEH": AssetCategory.VEHICLE,
    "PRP": AssetCategory.PROP,
    "ENV": AssetCategory.ENVIRONMENT,
    "UNI": AssetCategory.UNIFORM,
    "LGT": AssetCategory.LIGHTING,
}
_SECTION_NAMES = {
    "Visual Design Intent (LOCKED)": "design_intent",
    "Master Creation Prompt": "master_prompt",
    "Dependencies": "dependencies",
    "Continuity Rules": "continuity",
    "Variables": "variants",
    "Architectural Identity (LOCKED)": "location_identity",
    "Identity (LOCKED)": "character_identity",
}
_MAX_DOCUMENT_BYTES = 25_000_000
_MAX_XML_BYTES = 20_000_000


class CAPDocumentImportError(ValueError):
    """The document or proposed import cannot be accepted safely."""


@dataclass(frozen=True)
class CAPDocumentProposal:
    """Untrusted source evidence only; no lifecycle authority."""

    source_id: str
    name: str
    category: AssetCategory
    source_sha256: str
    sections: dict[str, str]
    warnings: tuple[str, ...] = ()

    def to_draft_specification(
        self,
        *,
        target_asset_id: str,
        attributes: dict[str, str],
        allowed_variants: dict[str, tuple[str, ...]] | None = None,
    ) -> CAPStructuredSpecification:
        """Human-supplied mapping: never silently infer immutable fields."""
        if target_asset_id.upper() != self.source_id:
            raise CAPDocumentImportError(
                "Source ID and project target differ; explicit remapping requires review"
            )
        design = self.sections.get("design_intent", "")
        prompt = self.sections.get("master_prompt", "")
        if not design or not prompt:
            raise CAPDocumentImportError("Source lacks Design Intent or Master Creation Prompt")
        spec = CAPStructuredSpecification(
            asset_id=target_asset_id,
            category=self.category,
            design_intent=design,
            canonical_attributes=attributes,
            allowed_variants=allowed_variants or {},
            master_prompt=prompt,
            source_document_sha256=self.source_sha256,
            source_description=f"Imported DOCX proposal {self.name} ({self.source_id})",
            origin="docx_import_reviewed",
        )
        spec.validate_category_contract()
        return spec


def _paragraphs(xml: bytes) -> tuple[str, ...]:
    root = ElementTree.fromstring(xml)
    values = []
    for paragraph in root.iter(f"{_WORD_NS}p"):
        string = "".join(node.text or "" for node in paragraph.iter(f"{_WORD_NS}t")).strip()
        if string:
            values.append(string)
    return tuple(values)


def preview_cap_docx(path: Path) -> tuple[CAPDocumentProposal, ...]:
    """Parse DOCX main-document prose into category-labelled CAP previews.

    Never extracts embedded archives/media, follows XML external references,
    writes to the project, or submits to a provider.
    """
    if path.suffix.lower() != ".docx":
        raise CAPDocumentImportError("Only DOCX CAP documents are accepted")
    if not path.is_file() or path.stat().st_size > _MAX_DOCUMENT_BYTES:
        raise CAPDocumentImportError("DOCX file is missing or exceeds the import limit")
    payload = path.read_bytes()
    try:
        with ZipFile(path) as doc:
            entry = doc.getinfo("word/document.xml")
            if entry.file_size > _MAX_XML_BYTES:
                raise CAPDocumentImportError("DOCX text is too large")
            xml = doc.read(entry)
        lines = _paragraphs(xml)
    except (BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
        raise CAPDocumentImportError("Invalid or unreadable DOCX main document") from exc

    digest = hashlib.sha256(payload).hexdigest()
    starts = [(i, match) for i, text in enumerate(lines) if (match := _ID.fullmatch(text))]
    if not starts:
        raise CAPDocumentImportError("No recognized CAP identifier/version headings found")
    proposals = []
    for number, (start, match) in enumerate(starts):
        end = starts[number + 1][0] if number + 1 < len(starts) else len(lines)
        body = lines[start + 1 : end]
        code = match.group(1).upper()
        category = _CATEGORY_CODES.get(code)
        if category is None:
            continue
        source_id = f"CAP-{code}-{match.group(2)}"
        # Name normally follows "Creation Asset Prompt" on the next paragraph.
        name = next(
            (body[i + 1] for i, line in enumerate(body[:-1]) if line == "Creation Asset Prompt"),
            source_id,
        )
        sections: dict[str, str] = {}
        active: str | None = None
        chunks: list[str] = []

        def flush() -> None:
            if active and chunks:
                sections[active] = "\n".join(chunks).strip()

        for line in body:
            if line in _SECTION_NAMES:
                flush()
                active = _SECTION_NAMES[line]
                chunks = []
            elif line in {"Revision History", "Future Production Variants", "Variant Rules"}:
                flush()
                active = None
                chunks = []
            elif active:
                chunks.append(line)
        flush()
        warnings = []
        if not sections.get("master_prompt"):
            warnings.append("Missing Master Creation Prompt")
        if not sections.get("design_intent"):
            warnings.append("Missing Visual Design Intent")
        if not sections.get("location_identity") and category is AssetCategory.LOCATION:
            warnings.append("Location identity requires manual review")
        proposals.append(CAPDocumentProposal(source_id, name, category, digest, sections, tuple(warnings)))
    if not proposals:
        raise CAPDocumentImportError("Document contains no supported CAP categories")
    return tuple(proposals)


class CAPDocumentImportService:
    """Explicit, fail-closed handoff from preview to existing Draft CAP."""

    def __init__(self, specifications: CAPStructuredSpecificationService) -> None:
        self.specifications = specifications

    def apply_reviewed(
        self, proposal: CAPDocumentProposal, *, target_asset_id: str,
        attributes: dict[str, str], allowed_variants: dict[str, tuple[str, ...]] | None = None,
    ) -> CAPStructuredSpecification:
        spec = proposal.to_draft_specification(
            target_asset_id=target_asset_id,
            attributes=attributes,
            allowed_variants=allowed_variants,
        )
        existing = self.specifications.get(target_asset_id)
        if existing is not None:
            raise CAPSpecificationError("Existing structured CAP draft requires separate revision review")
        return self.specifications.save_draft(spec)
