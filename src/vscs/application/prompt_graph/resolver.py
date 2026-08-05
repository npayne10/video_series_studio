"""Read-only source resolution for prompt graph construction."""

from __future__ import annotations

from dataclasses import dataclass, field

from .context import PromptGraphBuildContext
from .models import PromptEdgeKind, PromptNodeKind


@dataclass(frozen=True, slots=True)
class PromptGraphSource:
    """One authoritative production contribution resolved for a graph."""

    source_id: str
    kind: PromptNodeKind
    label: str
    content: str = ""
    canonical_asset_id: str | None = None
    reference_ids: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    mandatory: bool = False
    sequence: int = 0
    parent_source_id: str | None = None
    relationship: PromptEdgeKind = PromptEdgeKind.CONTAINS

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.label.strip():
            raise ValueError("source_id and label are required")


@dataclass(slots=True)
class PromptGraphResolver:
    """Resolve production sources without exposing persistence to the builder."""

    _sources: dict[str, tuple[PromptGraphSource, ...]] = field(default_factory=dict)

    def register(
        self,
        shot_id: str,
        sources: tuple[PromptGraphSource, ...],
    ) -> None:
        """Replace deterministic source data for one shot."""
        self._sources[shot_id] = self._ordered(sources)

    def extend(
        self,
        shot_id: str,
        sources: tuple[PromptGraphSource, ...],
    ) -> None:
        """Add or replace sources by source ID without discarding other contributors."""
        merged = {source.source_id: source for source in self._sources.get(shot_id, ())}
        merged.update({source.source_id: source for source in sources})
        self._sources[shot_id] = self._ordered(tuple(merged.values()))

    def resolve(self, context: PromptGraphBuildContext) -> tuple[PromptGraphSource, ...]:
        """Resolve all authoritative sources currently available for a shot."""
        return self._sources.get(context.shot_id, ())

    @staticmethod
    def _ordered(
        sources: tuple[PromptGraphSource, ...],
    ) -> tuple[PromptGraphSource, ...]:
        return tuple(sorted(sources, key=lambda item: (item.sequence, item.source_id)))
