"""Canonical library matching and Shot asset binding for Phase 19.5.12."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vscs.application.assets import AssetService, XPDWorkbookImportService
from vscs.domain.assets import XPDImportDisposition

from .contracts import AutomationProposal, AutomationProposalType
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class CanonicalLibraryImportReport:
    workbook_path: str
    total_rows: int
    created: int
    updated: int
    unchanged: int
    conflicts: int
    invalid: int


@dataclass(frozen=True, slots=True)
class ShotAssetBinding:
    shot_id: str
    asset_id: str
    asset_name: str
    entity_name: str
    entity_candidate_id: str


@dataclass(frozen=True, slots=True)
class ShotAssetBindingReport:
    story_id: str
    source_revision: str
    shot_count: int
    binding_count: int
    unresolved_entity_count: int
    bindings: tuple[ShotAssetBinding, ...]


class CanonicalLibraryImportService:
    """Reuse the existing governed XPD import path; never invent canonical rows."""

    def __init__(self, assets: AssetService) -> None:
        self._importer = XPDWorkbookImportService(assets)

    def import_xpd(self, workbook_path: Path) -> CanonicalLibraryImportReport:
        preview = self._importer.preview(workbook_path)
        report = self._importer.apply(preview)
        return CanonicalLibraryImportReport(
            workbook_path=report.workbook_path,
            total_rows=len(preview.items),
            created=report.created,
            updated=report.updated,
            unchanged=report.unchanged,
            conflicts=report.conflicts,
            invalid=report.invalid,
        )

    def preview_counts(self, workbook_path: Path) -> CanonicalLibraryImportReport:
        preview = self._importer.preview(workbook_path)
        counts = dict.fromkeys(XPDImportDisposition, 0)
        for item in preview.items:
            counts[item.disposition] += 1
        return CanonicalLibraryImportReport(
            workbook_path=preview.workbook_path,
            total_rows=len(preview.items),
            created=counts[XPDImportDisposition.NEW],
            updated=counts[XPDImportDisposition.UPDATE],
            unchanged=counts[XPDImportDisposition.UNCHANGED],
            conflicts=counts[XPDImportDisposition.CONFLICT],
            invalid=counts[XPDImportDisposition.INVALID],
        )


class ShotAssetBindingService:
    """Bind resolved Story entities to Shots without creating governed Asset Plans."""

    def __init__(self, proposals: AutomationProposalService) -> None:
        self._proposals = proposals

    def bind(self, *, story_id: str, source_revision: str) -> ShotAssetBindingReport:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        current = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.provenance.source_story_id == story
            and proposal.provenance.source_revision == revision
        )
        assets = tuple(p for p in current if p.proposal_type is AutomationProposalType.ASSET)
        shots = tuple(p for p in current if p.proposal_type is AutomationProposalType.SHOT)
        resolved = {
            self._normalized_name(str(p.payload.get("name", ""))): p
            for p in assets
            if p.payload.get("resolution_kind") == "existing_canonical_asset"
            and p.payload.get("matched_asset_id")
        }
        unresolved = sum(
            p.payload.get("resolution_kind") != "existing_canonical_asset" for p in assets
        )
        bindings: list[ShotAssetBinding] = []
        for shot in shots:
            searchable = self._shot_text(shot)
            for normalized_name, asset in resolved.items():
                aliases = tuple(
                    self._normalized_name(str(alias))
                    for alias in asset.payload.get("aliases", [])
                    if str(alias).strip()
                )
                if not self._mentioned(searchable, normalized_name, aliases):
                    continue
                bindings.append(
                    ShotAssetBinding(
                        shot_id=shot.target_id,
                        asset_id=str(asset.payload["matched_asset_id"]),
                        asset_name=str(asset.payload.get("matched_asset_name", "")),
                        entity_name=str(asset.payload.get("name", "")),
                        entity_candidate_id=str(asset.payload.get("candidate_id", "")),
                    )
                )
        unique = tuple(
            {(binding.shot_id, binding.asset_id): binding for binding in bindings}.values()
        )
        return ShotAssetBindingReport(
            story_id=story,
            source_revision=revision,
            shot_count=len(shots),
            binding_count=len(unique),
            unresolved_entity_count=unresolved,
            bindings=unique,
        )

    @staticmethod
    def _shot_text(proposal: AutomationProposal) -> str:
        values = [proposal.target_id]
        values.extend(str(value) for value in proposal.payload.values() if isinstance(value, str))
        return ShotAssetBindingService._normalized_name(" ".join(values))

    @staticmethod
    def _normalized_name(value: str) -> str:
        return " ".join("".join(ch if ch.isalnum() else " " for ch in value.casefold()).split())

    @staticmethod
    def _mentioned(searchable: str, name: str, aliases: tuple[str, ...]) -> bool:
        terms = tuple(term for term in (name, *aliases) if len(term) >= 3)
        return any(term in searchable for term in terms)
