"""Immutable Story Knowledge Graph domain model for VSCS."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import SourceSpan


class GraphNodeKind(StrEnum):
    """Supported node categories in the Story Knowledge Graph."""

    CHARACTER = "character"
    LOCATION = "location"
    TECHNOLOGY = "technology"
    PROP = "prop"
    DIALOGUE = "dialogue"
    ACTION = "action"
    EMOTION = "emotion"
    TIMELINE_EVENT = "timeline_event"


class GraphEdgeKind(StrEnum):
    """Supported directed relationship categories in the graph."""

    RELATES_TO = "relates_to"
    SPEAKS = "speaks"
    ADDRESSES = "addresses"
    ACTS_IN = "acts_in"
    TARGETS = "targets"
    LOCATED_AT = "located_at"
    FEELS = "feels"
    PARTICIPATES_IN = "participates_in"
    PRECEDES = "precedes"


class GraphNode(BaseModel):
    """One immutable node in the Story Knowledge Graph."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    node_id: str = Field(min_length=1, max_length=160)
    kind: GraphNodeKind
    label: str = Field(min_length=1, max_length=300)
    source_model_id: str = Field(min_length=1, max_length=160)
    sources: tuple[SourceSpan, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class GraphEdge(BaseModel):
    """One immutable directed edge in the Story Knowledge Graph."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    edge_id: str = Field(min_length=1, max_length=180)
    kind: GraphEdgeKind
    source_node_id: str = Field(min_length=1, max_length=160)
    target_node_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=200)
    sources: tuple[SourceSpan, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_endpoints(self) -> GraphEdge:
        if self.source_node_id == self.target_node_id:
            raise ValueError("graph edge endpoints must be different nodes")
        return self


class StoryKnowledgeGraph(BaseModel):
    """Validated immutable graph derived from one AnalysisResult."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    story_id: str = Field(min_length=1)
    source_revision: str | None = None
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()

    @model_validator(mode="after")
    def validate_graph(self) -> StoryKnowledgeGraph:
        node_ids = tuple(node.node_id for node in self.nodes)
        edge_ids = tuple(edge.edge_id for edge in self.edges)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate graph node identifiers are not allowed")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("duplicate graph edge identifiers are not allowed")
        known = set(node_ids)
        for edge in self.edges:
            if edge.source_node_id not in known or edge.target_node_id not in known:
                raise ValueError(f"graph edge '{edge.edge_id}' contains a dangling node reference")
        return self

    def node(self, node_id: str) -> GraphNode | None:
        """Resolve one graph node by identifier."""
        return next((node for node in self.nodes if node.node_id == node_id), None)

    def outgoing(self, node_id: str) -> tuple[GraphEdge, ...]:
        """Return deterministic outgoing edges for one node."""
        return tuple(edge for edge in self.edges if edge.source_node_id == node_id)

    def incoming(self, node_id: str) -> tuple[GraphEdge, ...]:
        """Return deterministic incoming edges for one node."""
        return tuple(edge for edge in self.edges if edge.target_node_id == node_id)
