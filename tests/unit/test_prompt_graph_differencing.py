"""Tests for prompt graph snapshot history and deterministic differencing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vscs.application.prompt_graph import (
    PromptEdge,
    PromptEdgeKind,
    PromptGraph,
    PromptGraphChangeArea,
    PromptGraphChangeKind,
    PromptGraphDiffer,
    PromptGraphMetadata,
    PromptGraphSnapshot,
    PromptGraphSnapshotRegistry,
    PromptGraphSnapshotService,
    PromptNode,
    PromptNodeKind,
)


def _graph(*, continuity: str = "Maintain orientation.", include_prop: bool = False) -> PromptGraph:
    nodes = [
        PromptNode("root", PromptNodeKind.ROOT, "Root", mandatory=True),
        PromptNode("intent", PromptNodeKind.VISUAL_INTENT, "Intent", "Orbital approach."),
        PromptNode("continuity", PromptNodeKind.CONTINUITY, "Continuity", continuity),
    ]
    if include_prop:
        nodes.append(
            PromptNode(
                "prop",
                PromptNodeKind.PROP,
                "Navigation console",
                "Low-profile graphite console.",
                canonical_asset_id="CAP-PROP-CONSOLE",
            )
        )
    edges = tuple(
        PromptEdge(
            f"edge-{index}",
            "root",
            node.node_id,
            PromptEdgeKind.CONTAINS,
            sequence=index,
        )
        for index, node in enumerate(nodes[1:], start=1)
    )
    return PromptGraph(
        PromptGraphMetadata("GRAPH-001", "XORIX", "EP-001", "SCN-001", "SHT-001"),
        tuple(nodes),
        edges,
        "root",
    )


def test_snapshot_service_captures_ordered_history() -> None:
    registry = PromptGraphSnapshotRegistry()
    service = PromptGraphSnapshotService(registry)
    first = PromptGraphSnapshot.capture(
        _graph(),
        snapshot_id="SNAP-001",
        created_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
    )
    second = PromptGraphSnapshot.capture(
        _graph(continuity="Maintain orientation and engine state."),
        snapshot_id="SNAP-002",
        created_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC) + timedelta(minutes=1),
    )
    registry.register(second)
    registry.register(first)

    assert service.history("GRAPH-001") == (first, second)
    assert service.latest("GRAPH-001") is second


def test_snapshot_diff_classifies_added_and_modified_nodes() -> None:
    before = PromptGraphSnapshot.capture(_graph(), snapshot_id="SNAP-001")
    after = PromptGraphSnapshot.capture(
        _graph(continuity="Maintain orientation and engine state.", include_prop=True),
        snapshot_id="SNAP-002",
    )

    diff = PromptGraphDiffer().compare_snapshots(before, after)

    assert diff.changed
    assert any(
        change.area is PromptGraphChangeArea.NODE
        and change.subject == "prop"
        and change.kind is PromptGraphChangeKind.ADDED
        for change in diff.changes
    )
    continuity = next(
        change
        for change in diff.changes
        if change.area is PromptGraphChangeArea.NODE and change.subject == "continuity"
    )
    assert continuity.kind is PromptGraphChangeKind.MODIFIED
    assert continuity.continuity_sensitive
    assert diff.continuity_changes == (continuity,)


def test_identical_snapshots_have_no_changes() -> None:
    graph = _graph()
    before = PromptGraphSnapshot.capture(graph, snapshot_id="SNAP-001")
    after = PromptGraphSnapshot.capture(graph, snapshot_id="SNAP-002")

    diff = PromptGraphDiffer().compare_snapshots(before, after)

    assert not diff.changed
    assert diff.changes == ()
