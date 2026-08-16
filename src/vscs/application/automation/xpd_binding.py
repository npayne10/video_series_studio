"""Canonical library matching and Shot asset binding for Phase 19.5.12."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import ClassVar

from vscs.application.assets import AssetService, XPDWorkbookImportService
from vscs.domain.assets import Asset, XPDImportDisposition

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
class CanonicalMatchCandidate:
    asset_id: str
    asset_name: str
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class CanonicalMatchDiagnostic:
    entity_name: str
    entity_category: str
    resolution_kind: str
    current_asset_id: str
    current_asset_name: str
    status: str
    suggestions: tuple[CanonicalMatchCandidate, ...]


@dataclass(frozen=True, slots=True)
class CanonicalMatchDiagnosticReport:
    story_id: str
    source_revision: str
    entity_count: int
    resolved_count: int
    suggested_count: int
    ambiguous_count: int
    no_match_count: int
    diagnostics: tuple[CanonicalMatchDiagnostic, ...]


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


class CanonicalMatchDiagnosticService:
    """Explain current XPD matches and suggest near matches without mutating canon."""

    _CHARACTER_TITLES: ClassVar[frozenset[str]] = frozenset(
        {
            "high",
            "commander",
            "captain",
            "major",
            "ambassador",
            "admiral",
            "general",
            "colonel",
            "lieutenant",
            "doctor",
            "professor",
            "cmdr",
            "capt",
            "maj",
            "adm",
            "gen",
            "col",
            "lt",
            "dr",
            "prof",
        }
    )

    def __init__(self, assets: AssetService, proposals: AutomationProposalService) -> None:
        self._assets = assets
        self._proposals = proposals

    def review(self, *, story_id: str, source_revision: str) -> CanonicalMatchDiagnosticReport:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        proposals = tuple(
            item
            for item in self._proposals.list_proposals()
            if item.proposal_type is AutomationProposalType.ASSET
            and item.provenance.source_story_id == story
            and item.provenance.source_revision == revision
        )
        assets = self._assets.list()
        diagnostics = tuple(self._diagnostic(item, assets) for item in proposals)
        return CanonicalMatchDiagnosticReport(
            story_id=story,
            source_revision=revision,
            entity_count=len(diagnostics),
            resolved_count=sum(item.status == "resolved" for item in diagnostics),
            suggested_count=sum(item.status == "suggested" for item in diagnostics),
            ambiguous_count=sum(item.status == "ambiguous" for item in diagnostics),
            no_match_count=sum(item.status == "no_match" for item in diagnostics),
            diagnostics=diagnostics,
        )

    def _diagnostic(
        self, proposal: AutomationProposal, assets: tuple[Asset, ...]
    ) -> CanonicalMatchDiagnostic:
        payload = proposal.payload
        entity_name = str(payload.get("name", ""))
        category = str(payload.get("expected_asset_category", ""))
        resolution_kind = str(payload.get("resolution_kind", ""))
        current_asset_id = str(payload.get("matched_asset_id", ""))
        current_asset_name = str(payload.get("matched_asset_name", ""))
        if resolution_kind == "existing_canonical_asset" and current_asset_id:
            return CanonicalMatchDiagnostic(
                entity_name=entity_name,
                entity_category=category,
                resolution_kind=resolution_kind,
                current_asset_id=current_asset_id,
                current_asset_name=current_asset_name,
                status="resolved",
                suggestions=(),
            )

        rejected = {
            str(item).strip().upper()
            for item in payload.get("rejected_canonical_asset_ids", [])
            if str(item).strip()
        }
        compatible = tuple(
            asset
            for asset in assets
            if asset.category.value == category and asset.asset_id.upper() not in rejected
        )
        scored = sorted(
            (
                candidate
                for asset in compatible
                if (candidate := self._score(entity_name, asset)) is not None
            ),
            key=lambda item: (-item.score, item.asset_name.casefold()),
        )
        suggestions = tuple(scored[:3])
        if not suggestions or suggestions[0].score < 0.58:
            status = "no_match"
            suggestions = tuple(item for item in suggestions if item.score >= 0.45)
        elif len(suggestions) > 1 and suggestions[0].score - suggestions[1].score < 0.08:
            status = "ambiguous"
        else:
            status = "suggested"
        return CanonicalMatchDiagnostic(
            entity_name=entity_name,
            entity_category=category,
            resolution_kind=resolution_kind,
            current_asset_id=current_asset_id,
            current_asset_name=current_asset_name,
            status=status,
            suggestions=suggestions,
        )

    @classmethod
    def _score(cls, entity_name: str, asset: Asset) -> CanonicalMatchCandidate | None:
        entity_tokens = cls._tokens(entity_name)
        asset_tokens = cls._tokens(asset.name)
        if not entity_tokens or not asset_tokens:
            return None
        if entity_tokens == asset_tokens:
            return CanonicalMatchCandidate(asset.asset_id, asset.name, 1.0, "normalized exact name")

        entity_core = cls._core_tokens(entity_tokens, asset.category.value)
        asset_core = cls._core_tokens(asset_tokens, asset.category.value)
        if entity_core and entity_core == asset_core:
            return CanonicalMatchCandidate(
                asset.asset_id, asset.name, 0.98, "rank/title-normalized exact name"
            )
        if len(entity_core) >= 2 and entity_core.issubset(asset_core):
            return CanonicalMatchCandidate(
                asset.asset_id, asset.name, 0.92, "all entity name tokens occur in canonical name"
            )
        if len(asset_core) >= 2 and asset_core.issubset(entity_core):
            return CanonicalMatchCandidate(
                asset.asset_id,
                asset.name,
                0.88,
                "canonical name occurs within longer Story entity name",
            )
        if (
            asset.category.value == "character"
            and len(entity_core) == 1
            and entity_core.issubset(asset_core)
        ):
            return CanonicalMatchCandidate(
                asset.asset_id,
                asset.name,
                0.74,
                "single character-name token occurs in canonical name",
            )

        overlap = len(entity_core & asset_core)
        union = len(entity_core | asset_core)
        token_score = overlap / union if union else 0.0
        sequence_score = SequenceMatcher(
            None, " ".join(sorted(entity_core)), " ".join(sorted(asset_core))
        ).ratio()
        score = round(max(token_score, sequence_score * 0.82), 3)
        if score < 0.45:
            return None
        reason = "token overlap" if token_score >= sequence_score * 0.82 else "name similarity"
        return CanonicalMatchCandidate(asset.asset_id, asset.name, score, reason)

    @classmethod
    def _core_tokens(cls, tokens: frozenset[str], category: str) -> frozenset[str]:
        if category != "character":
            return tokens
        return frozenset(token for token in tokens if token not in cls._CHARACTER_TITLES)

    @staticmethod
    def _tokens(value: str) -> frozenset[str]:
        normalized = "".join(
            character if character.isalnum() else " " for character in value.casefold()
        )
        return frozenset(token for token in normalized.split() if len(token) >= 2)


class ShotAssetBindingService:
    """Bind resolved Story entities to Shots without creating governed Asset Plans."""

    _NON_GLOBAL_SCOPES: ClassVar[frozenset[str]] = frozenset(
        {"prompt_element", "scene_continuity"}
    )

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
            p.payload.get("resolution_kind") != "existing_canonical_asset"
            and str(p.payload.get("canonical_scope", "")) not in self._NON_GLOBAL_SCOPES
            for p in assets
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
