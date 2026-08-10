"""Tests for deterministic prompt graph snapshots and registries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.prompt_graph import (
    PromptGraph,
    PromptGraphMetadata,
    PromptGraphRegistry,
    PromptGraphSnapshot,
    PromptGraphSnapshotRegistry,
    PromptNode,
    PromptNodeKind,
    graph_checksum,
)


def _graph(graph_id: str = "PG-001", shot_id: str = "SHT-001") -> PromptGraph:
    return PromptGraph(
        PromptGraphMetadata(
            graph_id=graph_id,
            production_id="XORIX",
            container_id="EP-001",
            scene_id="SCN-001",
            shot_id=shot_id,
        ),
        (PromptNode("ROOT", PromptNodeKind.ROOT, "Prompt root"),),
        root_node_id="ROOT",
    )


def test_snapshot_checksum_is_stable_and_validated() -> None:
    graph = _graph()
    created = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)
    snapshot = PromptGraphSnapshot.capture(
        graph,
        snapshot_id="SNAP-001",
        created_at=created,
    )

    assert snapshot.checksum == graph_checksum(graph)
    assert len(snapshot.checksum) == 64
    assert PromptGraph.from_dict(graph.to_dict()) == graph

    with pytest.raises(ValueError, match="checksum"):
        PromptGraphSnapshot("SNAP-BAD", graph, created, "bad")


def test_graph_and_snapshot_registries_are_deterministic() -> None:
    graphs = PromptGraphRegistry()
    first = graphs.register(_graph("PG-002", "SHT-001"))
    second = graphs.register(_graph("PG-001", "SHT-001"))
    graphs.register(_graph("PG-003", "SHT-002"))

    assert tuple(graph.metadata.graph_id for graph in graphs.list()) == (
        "PG-001",
        "PG-002",
        "PG-003",
    )
    assert graphs.require("PG-002") is first
    assert graphs.require("PG-001") is second
    assert len(graphs.for_shot("SHT-001")) == 2

    snapshots = PromptGraphSnapshotRegistry()
    later = datetime(2026, 8, 4, 13, 0, tzinfo=UTC)
    earlier = later - timedelta(hours=1)
    snapshots.register(
        PromptGraphSnapshot.capture(
            second,
            snapshot_id="SNAP-002",
            created_at=later,
        )
    )
    snapshots.register(
        PromptGraphSnapshot.capture(
            second,
            snapshot_id="SNAP-001",
            created_at=earlier,
        )
    )

    assert tuple(item.snapshot_id for item in snapshots.list_for_graph("PG-001")) == (
        "SNAP-001",
        "SNAP-002",
    )
