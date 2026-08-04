"""Snapshot history and deterministic graph/package differencing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .compiler import PromptPackage, PromptSectionKind
from .models import PromptEdge, PromptGraph, PromptNode, PromptNodeKind
from .registry import PromptGraphSnapshotRegistry
from .snapshot import PromptGraphSnapshot


class PromptGraphChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


class PromptGraphChangeArea(StrEnum):
    METADATA = "metadata"
    NODE = "node"
    EDGE = "edge"
    PROMPT_SECTION = "prompt_section"
    POSITIVE_PROMPT = "positive_prompt"
    NEGATIVE_PROMPT = "negative_prompt"
    CANONICAL_ASSET = "canonical_asset"
    REFERENCE = "reference"


@dataclass(frozen=True, slots=True)
class PromptGraphChange:
    kind: PromptGraphChangeKind
    area: PromptGraphChangeArea
    subject: str
    before: str = ""
    after: str = ""
    continuity_sensitive: bool = False


@dataclass(frozen=True, slots=True)
class PromptGraphDiff:
    before_id: str
    after_id: str
    changes: tuple[PromptGraphChange, ...]

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    @property
    def continuity_changes(self) -> tuple[PromptGraphChange, ...]:
        return tuple(change for change in self.changes if change.continuity_sensitive)


@dataclass(slots=True)
class PromptGraphSnapshotService:
    registry: PromptGraphSnapshotRegistry

    def capture(
        self,
        graph: PromptGraph,
        *,
        snapshot_id: str,
    ) -> PromptGraphSnapshot:
        snapshot = PromptGraphSnapshot.capture(graph, snapshot_id=snapshot_id)
        return self.registry.register(snapshot)

    def history(self, graph_id: str) -> tuple[PromptGraphSnapshot, ...]:
        return self.registry.list_for_graph(graph_id)

    def latest(self, graph_id: str) -> PromptGraphSnapshot | None:
        history = self.history(graph_id)
        return history[-1] if history else None


class PromptGraphDiffer:
    """Compare immutable graph snapshots and compiled prompt packages."""

    def compare_snapshots(
        self,
        before: PromptGraphSnapshot,
        after: PromptGraphSnapshot,
    ) -> PromptGraphDiff:
        return self.compare_graphs(
            before.graph,
            after.graph,
            before_id=before.snapshot_id,
            after_id=after.snapshot_id,
        )

    def compare_graphs(
        self,
        before: PromptGraph,
        after: PromptGraph,
        *,
        before_id: str | None = None,
        after_id: str | None = None,
    ) -> PromptGraphDiff:
        changes: list[PromptGraphChange] = []
        if before.metadata != after.metadata:
            changes.append(
                PromptGraphChange(
                    PromptGraphChangeKind.MODIFIED,
                    PromptGraphChangeArea.METADATA,
                    "graph_metadata",
                    repr(before.metadata),
                    repr(after.metadata),
                )
            )
        changes.extend(self._entity_changes(before.nodes, after.nodes, node=True))
        changes.extend(self._entity_changes(before.edges, after.edges, node=False))
        return PromptGraphDiff(
            before_id or before.metadata.graph_id,
            after_id or after.metadata.graph_id,
            tuple(sorted(changes, key=self._sort_key)),
        )

    def compare_packages(
        self,
        before: PromptPackage,
        after: PromptPackage,
    ) -> PromptGraphDiff:
        changes: list[PromptGraphChange] = []
        before_sections = {section.kind: section.text for section in before.sections}
        after_sections = {section.kind: section.text for section in after.sections}
        for kind in sorted(set(before_sections) | set(after_sections), key=str):
            old = before_sections.get(kind)
            new = after_sections.get(kind)
            if old == new:
                continue
            changes.append(
                PromptGraphChange(
                    self._change_kind(old, new),
                    PromptGraphChangeArea.PROMPT_SECTION,
                    kind.value,
                    old or "",
                    new or "",
                    kind is PromptSectionKind.CONTINUITY,
                )
            )
        self._scalar_change(
            changes,
            PromptGraphChangeArea.POSITIVE_PROMPT,
            "positive_prompt",
            before.positive_prompt,
            after.positive_prompt,
        )
        self._scalar_change(
            changes,
            PromptGraphChangeArea.NEGATIVE_PROMPT,
            "negative_prompt",
            before.negative_prompt,
            after.negative_prompt,
        )
        changes.extend(
            self._set_changes(
                before.canonical_asset_ids,
                after.canonical_asset_ids,
                PromptGraphChangeArea.CANONICAL_ASSET,
            )
        )
        changes.extend(
            self._set_changes(
                before.reference_ids,
                after.reference_ids,
                PromptGraphChangeArea.REFERENCE,
            )
        )
        return PromptGraphDiff(
            before.package_id,
            after.package_id,
            tuple(sorted(changes, key=self._sort_key)),
        )

    def _entity_changes(
        self,
        before: tuple[PromptNode, ...] | tuple[PromptEdge, ...],
        after: tuple[PromptNode, ...] | tuple[PromptEdge, ...],
        *,
        node: bool,
    ) -> list[PromptGraphChange]:
        identity = "node_id" if node else "edge_id"
        old_items = {getattr(item, identity): item for item in before}
        new_items = {getattr(item, identity): item for item in after}
        area = PromptGraphChangeArea.NODE if node else PromptGraphChangeArea.EDGE
        changes: list[PromptGraphChange] = []
        for subject in sorted(set(old_items) | set(new_items)):
            old = old_items.get(subject)
            new = new_items.get(subject)
            if old == new:
                continue
            continuity = self._continuity_sensitive(old, new) if node else False
            changes.append(
                PromptGraphChange(
                    self._change_kind(old, new),
                    area,
                    subject,
                    repr(old) if old is not None else "",
                    repr(new) if new is not None else "",
                    continuity,
                )
            )
        return changes

    @staticmethod
    def _continuity_sensitive(old: object, new: object) -> bool:
        return any(
            isinstance(item, PromptNode) and item.kind is PromptNodeKind.CONTINUITY
            for item in (old, new)
        )

    @staticmethod
    def _change_kind(old: object | None, new: object | None) -> PromptGraphChangeKind:
        if old is None:
            return PromptGraphChangeKind.ADDED
        if new is None:
            return PromptGraphChangeKind.REMOVED
        return PromptGraphChangeKind.MODIFIED

    @staticmethod
    def _scalar_change(
        changes: list[PromptGraphChange],
        area: PromptGraphChangeArea,
        subject: str,
        old: str,
        new: str,
    ) -> None:
        if old != new:
            changes.append(
                PromptGraphChange(
                    PromptGraphChangeKind.MODIFIED,
                    area,
                    subject,
                    old,
                    new,
                )
            )

    def _set_changes(
        self,
        before: tuple[str, ...],
        after: tuple[str, ...],
        area: PromptGraphChangeArea,
    ) -> list[PromptGraphChange]:
        changes: list[PromptGraphChange] = []
        for value in sorted(set(before) - set(after)):
            changes.append(
                PromptGraphChange(PromptGraphChangeKind.REMOVED, area, value, value, "")
            )
        for value in sorted(set(after) - set(before)):
            changes.append(
                PromptGraphChange(PromptGraphChangeKind.ADDED, area, value, "", value)
            )
        return changes

    @staticmethod
    def _sort_key(change: PromptGraphChange) -> tuple[str, str, str]:
        return change.area.value, change.subject, change.kind.value
