"""Unit tests for Phase 18.2.4 Story Knowledge Graph construction."""

import pytest
from pydantic import ValidationError

from vscs.application.story_analysis import (
    DeterministicStoryAnalyzer,
    StoryAnalysisRequest,
    StoryKnowledgeGraphBuilder,
)
from vscs.domain.story_analysis import (
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    StoryKnowledgeGraph,
)

STORY = """# Arrival

Commander James Spence stood beside Captain Cheryl Draker on the bridge.
\"Confirmed visual,\" Cheryl Draker said.
James frowned as the ship entered orbit.

# Discovery

Commander James Spence stared at the circular doorway in the mountain.
"""


def test_graph_rejects_dangling_edges() -> None:
    node = GraphNode(
        node_id="character:james",
        kind=GraphNodeKind.CHARACTER,
        label="James Spence",
        source_model_id="james",
    )
    edge = GraphEdge(
        edge_id="edge-1",
        kind=GraphEdgeKind.RELATES_TO,
        source_node_id=node.node_id,
        target_node_id="character:missing",
        label="knows",
    )

    with pytest.raises(ValidationError, match="dangling node reference"):
        StoryKnowledgeGraph(story_id="story-1", nodes=(node,), edges=(edge,))


def test_graph_rejects_duplicate_node_ids() -> None:
    first = GraphNode(
        node_id="character:james",
        kind=GraphNodeKind.CHARACTER,
        label="James Spence",
        source_model_id="james",
    )
    second = first.model_copy(update={"label": "Commander James Spence"})

    with pytest.raises(ValidationError, match="duplicate graph node identifiers"):
        StoryKnowledgeGraph(story_id="story-1", nodes=(first, second))


def test_builder_projects_analysis_into_traceable_graph() -> None:
    analysis = DeterministicStoryAnalyzer().analyze(
        StoryAnalysisRequest(story_id="xorix-trailer", source_text=STORY)
    )

    graph = StoryKnowledgeGraphBuilder().build(analysis)

    kinds = {node.kind for node in graph.nodes}
    edge_kinds = {edge.kind for edge in graph.edges}
    assert GraphNodeKind.CHARACTER in kinds
    assert GraphNodeKind.ACTION in kinds
    assert GraphNodeKind.TIMELINE_EVENT in kinds
    assert GraphEdgeKind.PARTICIPATES_IN in edge_kinds
    assert GraphEdgeKind.PRECEDES in edge_kinds
    assert all(graph.node(edge.source_node_id) is not None for edge in graph.edges)
    assert all(graph.node(edge.target_node_id) is not None for edge in graph.edges)


def test_builder_preserves_source_provenance() -> None:
    analysis = DeterministicStoryAnalyzer().analyze(
        StoryAnalysisRequest(story_id="xorix-trailer", source_text=STORY)
    )

    graph = StoryKnowledgeGraphBuilder().build(analysis)

    sourced_nodes = [node for node in graph.nodes if node.sources]
    assert sourced_nodes
    assert all(source.excerpt for node in sourced_nodes for source in node.sources)


def test_graph_navigation_returns_incoming_and_outgoing_edges() -> None:
    analysis = DeterministicStoryAnalyzer().analyze(
        StoryAnalysisRequest(story_id="xorix-trailer", source_text=STORY)
    )
    graph = StoryKnowledgeGraphBuilder().build(analysis)
    character = next(node for node in graph.nodes if node.kind is GraphNodeKind.CHARACTER)

    assert graph.outgoing(character.node_id) or graph.incoming(character.node_id)
