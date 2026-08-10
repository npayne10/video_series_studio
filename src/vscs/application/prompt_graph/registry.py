"""In-memory prompt graph and snapshot registries."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import PromptGraph
from .snapshot import PromptGraphSnapshot


@dataclass(slots=True)
class PromptGraphRegistry:
    """Store prompt graphs by stable graph identity."""

    _graphs: dict[str, PromptGraph] = field(default_factory=dict)

    def register(self, graph: PromptGraph) -> PromptGraph:
        """Register or replace a graph by graph ID."""
        self._graphs[graph.metadata.graph_id] = graph
        return graph

    def get(self, graph_id: str) -> PromptGraph | None:
        """Return one graph when available."""
        return self._graphs.get(graph_id)

    def require(self, graph_id: str) -> PromptGraph:
        """Return one graph or raise when unavailable."""
        try:
            return self._graphs[graph_id]
        except KeyError as exc:
            raise KeyError(f"Prompt graph not registered: {graph_id}") from exc

    def remove(self, graph_id: str) -> PromptGraph | None:
        """Remove and return one graph."""
        return self._graphs.pop(graph_id, None)

    def list(self) -> tuple[PromptGraph, ...]:
        """Return graphs in stable graph-ID order."""
        return tuple(self._graphs[graph_id] for graph_id in sorted(self._graphs))

    def for_shot(self, shot_id: str) -> tuple[PromptGraph, ...]:
        """Return all graph versions associated with a shot."""
        return tuple(graph for graph in self.list() if graph.metadata.shot_id == shot_id)


@dataclass(slots=True)
class PromptGraphSnapshotRegistry:
    """Store immutable graph snapshots by snapshot identity."""

    _snapshots: dict[str, PromptGraphSnapshot] = field(default_factory=dict)

    def register(self, snapshot: PromptGraphSnapshot) -> PromptGraphSnapshot:
        """Register or replace one snapshot."""
        self._snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def get(self, snapshot_id: str) -> PromptGraphSnapshot | None:
        """Return one snapshot when available."""
        return self._snapshots.get(snapshot_id)

    def list_for_graph(self, graph_id: str) -> tuple[PromptGraphSnapshot, ...]:
        """Return graph snapshots in creation order then stable identity order."""
        return tuple(
            sorted(
                (
                    snapshot
                    for snapshot in self._snapshots.values()
                    if snapshot.graph.metadata.graph_id == graph_id
                ),
                key=lambda item: (item.created_at, item.snapshot_id),
            )
        )
