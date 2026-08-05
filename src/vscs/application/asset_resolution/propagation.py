"""Track asset dependencies and propagate canonical changes to affected shots."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from vscs.application.prompt_graph import IncrementalCompilationHistory

from .prompt_enrichment import (
    PromptAssetDependency,
    PromptAssetEnrichmentRequest,
    PromptAssetEnrichmentResult,
    PromptGraphAssetEnrichmentService,
)


class AssetDependencyChangeKind(StrEnum):
    """Canonical dependency component that changed."""

    ASSET = "asset"
    CAP = "cap"
    REFERENCE = "reference"
    REMOVED = "removed"


@dataclass(frozen=True, slots=True)
class ShotAssetDependencyRecord:
    """Latest authoritative dependency state for one enriched shot."""

    shot_id: str
    asset_ids: tuple[str, ...]
    dependencies: tuple[PromptAssetDependency, ...]
    mandatory: bool = True

    def dependency(self, asset_id: str) -> PromptAssetDependency | None:
        normalized = asset_id.strip().upper()
        return next(
            (item for item in self.dependencies if item.asset_id == normalized),
            None,
        )


@dataclass(frozen=True, slots=True)
class AssetDependencyChange:
    """One detected difference between recorded and current dependencies."""

    shot_id: str
    asset_id: str
    kinds: tuple[AssetDependencyChangeKind, ...]


@dataclass(frozen=True, slots=True)
class AssetPropagationReport:
    """Immutable outcome of one dependency propagation operation."""

    asset_id: str
    affected_shot_ids: tuple[str, ...]
    refreshed_shot_ids: tuple[str, ...]
    invalidated_item_ids: tuple[str, ...]
    changes: tuple[AssetDependencyChange, ...]

    @property
    def changed(self) -> bool:
        return bool(self.changes)


@dataclass(slots=True)
class AssetDependencyIndex:
    """In-memory reverse index from production assets to enriched shots."""

    _records: dict[str, ShotAssetDependencyRecord] = field(default_factory=dict)

    def register(self, result: PromptAssetEnrichmentResult) -> ShotAssetDependencyRecord:
        record = ShotAssetDependencyRecord(
            result.request.shot_id,
            result.request.asset_ids,
            result.dependencies,
            result.request.mandatory,
        )
        self._records[record.shot_id] = record
        return record

    def get(self, shot_id: str) -> ShotAssetDependencyRecord | None:
        return self._records.get(shot_id)

    def affected_shots(self, asset_id: str) -> tuple[str, ...]:
        normalized = asset_id.strip().upper()
        return tuple(
            sorted(
                record.shot_id
                for record in self._records.values()
                if normalized in record.asset_ids
            )
        )

    def remove(self, shot_id: str) -> bool:
        return self._records.pop(shot_id, None) is not None

    def all(self) -> tuple[ShotAssetDependencyRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))


@dataclass(slots=True)
class AssetChangePropagationService:
    """Refresh affected Prompt Graph sources and invalidate compiled items."""

    index: AssetDependencyIndex
    enrichment: PromptGraphAssetEnrichmentService
    compilation_history: IncrementalCompilationHistory

    def track(self, result: PromptAssetEnrichmentResult) -> ShotAssetDependencyRecord:
        """Record dependencies emitted by successful Prompt Graph enrichment."""
        return self.index.register(result)

    def propagate(self, asset_id: str) -> AssetPropagationReport:
        """Refresh every indexed shot using an asset and invalidate changed outputs."""
        normalized = asset_id.strip().upper()
        affected = self.index.affected_shots(normalized)
        refreshed: list[str] = []
        changes: list[AssetDependencyChange] = []

        for shot_id in affected:
            previous = self.index.get(shot_id)
            if previous is None:
                continue
            result = self.enrichment.enrich(
                PromptAssetEnrichmentRequest(
                    shot_id,
                    previous.asset_ids,
                    previous.mandatory,
                )
            )
            refreshed.append(shot_id)
            current = result.dependencies
            kinds = self._changed_kinds(
                previous.dependency(normalized),
                next((item for item in current if item.asset_id == normalized), None),
            )
            self.index.register(result)
            if kinds:
                changes.append(AssetDependencyChange(shot_id, normalized, kinds))

        changed_shots = {change.shot_id for change in changes}
        invalidated = tuple(
            sorted(
                record.item_id
                for record in self.compilation_history.all()
                if record.shot_id in changed_shots
                and self.compilation_history.invalidate_item(record.item_id)
            )
        )
        return AssetPropagationReport(
            normalized,
            affected,
            tuple(refreshed),
            invalidated,
            tuple(changes),
        )

    @staticmethod
    def _changed_kinds(
        previous: PromptAssetDependency | None,
        current: PromptAssetDependency | None,
    ) -> tuple[AssetDependencyChangeKind, ...]:
        if previous is None:
            return ()
        if current is None:
            return (AssetDependencyChangeKind.REMOVED,)
        kinds: list[AssetDependencyChangeKind] = []
        if previous.asset_checksum != current.asset_checksum:
            kinds.append(AssetDependencyChangeKind.ASSET)
        if previous.cap_checksum != current.cap_checksum:
            kinds.append(AssetDependencyChangeKind.CAP)
        if previous.reference_checksums != current.reference_checksums:
            kinds.append(AssetDependencyChangeKind.REFERENCE)
        return tuple(kinds)
