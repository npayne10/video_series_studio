"""Tests for immutable prompt graph contracts and traversal."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vscs.application.prompt_graph import (
    PromptEdge,
    PromptEdgeKind,
    PromptGraph,
    PromptGraphCycleError,
    PromptGraphMetadata,
    PromptNode,
    PromptNodeKind,
)


def _metadata() -> PromptGraphMetadata:
    return PromptGraphMetadata(
        graph_id="PG-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLP-001",
    )


def _graph() -> PromptGraph:
    nodes = (
        PromptNode("ROOT", PromptNodeKind.ROOT, "Shot prompt", sequence=0),
        PromptNode(
            "SHIP",
            PromptNodeKind.SHIP,
            "Iron Horizon",
            content="145-metre Guild survey vessel",
            canonical_asset_id="SHP-IRON-HORIZON",
            reference_ids=("REF-IRON-HORIZON",),
            attributes=(("engine_count", "4 rear engines"),),
            mandatory=True,
            sequence=10,
        ),
        PromptNode(
            "EFFECT",
            PromptNodeKind.EFFECT,
            "Fusion exhaust",
            content="Controlled blue-white engine trails",
            sequence=20,
        ),
    )
    edges = (
        PromptEdge(
            "EDGE-ROOT-SHIP",
            "ROOT",
            "SHIP",
            PromptEdgeKind.CONTAINS,
            sequence=10,
        ),
        PromptEdge(
            "EDGE-SHIP-EFFECT",
            "SHIP",
            "EFFECT",
            PromptEdgeKind.USES,
            sequence=20,
        ),
    )
    return PromptGraph(_metadata(), nodes, edges, root_node_id="ROOT")


def test_prompt_graph_is_immutable_and_round_trips() -> None:
    graph = _graph()

    with pytest.raises(FrozenInstanceError):
        graph.root_node_id = "SHIP"  # type: ignore[misc]

    restored = PromptGraph.from_dict(graph.to_dict())

    assert restored == graph
    assert restored.require_node("SHIP").attribute("engine_count") == ("4 rear engines")
    assert restored.nodes_of_kind(PromptNodeKind.SHIP)[0].mandatory


def test_prompt_graph_traversal_is_deterministic() -> None:
    graph = _graph()

    assert tuple(node.node_id for node in graph.topological_nodes()) == (
        "ROOT",
        "SHIP",
        "EFFECT",
    )
    assert tuple(node.node_id for node in graph.reachable_from("ROOT")) == (
        "SHIP",
        "EFFECT",
    )
    assert graph.outgoing("SHIP")[0].target_id == "EFFECT"
    assert graph.incoming("EFFECT")[0].source_id == "SHIP"
    assert not graph.has_cycle


def test_prompt_graph_detects_cycles_without_infinite_traversal() -> None:
    graph = PromptGraph(
        _metadata(),
        (
            PromptNode("A", PromptNodeKind.ROOT, "A"),
            PromptNode("B", PromptNodeKind.OTHER, "B"),
        ),
        (
            PromptEdge("A-B", "A", "B", PromptEdgeKind.DEPENDS_ON),
            PromptEdge("B-A", "B", "A", PromptEdgeKind.DEPENDS_ON),
        ),
        root_node_id="A",
    )

    assert graph.has_cycle
    assert tuple(node.node_id for node in graph.reachable_from("A")) == ("B",)
    with pytest.raises(PromptGraphCycleError):
        graph.topological_nodes()


def test_prompt_graph_rejects_invalid_structure() -> None:
    node = PromptNode("ROOT", PromptNodeKind.ROOT, "Root")

    with pytest.raises(ValueError, match="unknown prompt node"):
        PromptGraph(
            _metadata(),
            (node,),
            (PromptEdge("BROKEN", "ROOT", "MISSING", PromptEdgeKind.USES),),
        )

    with pytest.raises(ValueError, match="node IDs must be unique"):
        PromptGraph(_metadata(), (node, node))

    with pytest.raises(ValueError, match="may not target their source"):
        PromptEdge("SELF", "ROOT", "ROOT", PromptEdgeKind.DEPENDS_ON)
