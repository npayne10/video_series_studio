"""Immutable renderer-neutral prompt graph contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class PromptNodeKind(StrEnum):
    """Production concepts represented by prompt graph nodes."""

    ROOT = "root"
    SCENE = "scene"
    SHOT = "shot"
    VISUAL_INTENT = "visual_intent"
    CHARACTER = "character"
    SHIP = "ship"
    VEHICLE = "vehicle"
    LOCATION = "location"
    ENVIRONMENT = "environment"
    PROP = "prop"
    CAMERA = "camera"
    LIGHTING = "lighting"
    MOVEMENT = "movement"
    EFFECT = "effect"
    CONTINUITY = "continuity"
    DIALOGUE = "dialogue"
    AUDIO = "audio"
    STYLE = "style"
    QUALITY = "quality"
    RESTRICTION = "restriction"
    NEGATIVE = "negative"
    RENDERER = "renderer"
    OTHER = "other"


class PromptEdgeKind(StrEnum):
    """Semantic relationships between production concepts."""

    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    DESCRIBES = "describes"
    LOCATED_AT = "located_at"
    USES = "uses"
    AFFECTS = "affects"
    FOLLOWS = "follows"
    PRECEDES = "precedes"
    SPEAKS = "speaks"
    TARGETS = "targets"
    REFERENCES = "references"
    CONSTRAINS = "constrains"
    OVERRIDES = "overrides"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class PromptGraphMetadata:
    """Ownership and version information for one prompt graph."""

    graph_id: str
    production_id: str
    container_id: str
    scene_id: str
    shot_id: str
    clip_id: str | None = None
    version: str = "1.0"

    def __post_init__(self) -> None:
        for name, value in (
            ("graph_id", self.graph_id),
            ("production_id", self.production_id),
            ("container_id", self.container_id),
            ("scene_id", self.scene_id),
            ("shot_id", self.shot_id),
            ("version", self.version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class PromptNode:
    """One immutable production-knowledge node."""

    node_id: str
    kind: PromptNodeKind
    label: str
    content: str = ""
    canonical_asset_id: str | None = None
    reference_ids: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    mandatory: bool = False
    sequence: int = 0

    def __post_init__(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id is required")
        if not self.label.strip():
            raise ValueError("node label is required")
        if self.sequence < 0:
            raise ValueError("node sequence cannot be negative")
        keys = [key for key, _value in self.attributes]
        if any(not key.strip() for key in keys):
            raise ValueError("node attribute keys may not be empty")
        if len(keys) != len(set(keys)):
            raise ValueError("node attribute keys must be unique")
        if len(self.reference_ids) != len(set(self.reference_ids)):
            raise ValueError("node reference IDs must be unique")

    def attribute(self, key: str) -> str | None:
        """Return one named node attribute."""
        return next(
            (value for name, value in self.attributes if name == key),
            None,
        )


@dataclass(frozen=True, slots=True)
class PromptEdge:
    """One directed semantic relationship between two nodes."""

    edge_id: str
    source_id: str
    target_id: str
    kind: PromptEdgeKind
    label: str = ""
    attributes: tuple[tuple[str, str], ...] = ()
    sequence: int = 0

    def __post_init__(self) -> None:
        for name, value in (
            ("edge_id", self.edge_id),
            ("source_id", self.source_id),
            ("target_id", self.target_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if self.source_id == self.target_id:
            raise ValueError("prompt graph edges may not target their source")
        if self.sequence < 0:
            raise ValueError("edge sequence cannot be negative")
        keys = [key for key, _value in self.attributes]
        if len(keys) != len(set(keys)):
            raise ValueError("edge attribute keys must be unique")


class PromptGraphCycleError(ValueError):
    """Raised when a topological traversal encounters a cycle."""


@dataclass(frozen=True, slots=True)
class PromptGraph:
    """Immutable directed graph of production knowledge."""

    metadata: PromptGraphMetadata
    nodes: tuple[PromptNode, ...]
    edges: tuple[PromptEdge, ...] = ()
    root_node_id: str | None = None

    def __post_init__(self) -> None:
        node_ids = [node.node_id for node in self.nodes]
        edge_ids = [edge.edge_id for edge in self.edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("prompt graph node IDs must be unique")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("prompt graph edge IDs must be unique")
        known_nodes = set(node_ids)
        for edge in self.edges:
            if edge.source_id not in known_nodes or edge.target_id not in known_nodes:
                raise ValueError(f"edge {edge.edge_id} references an unknown prompt node")
        if self.root_node_id is not None and self.root_node_id not in known_nodes:
            raise ValueError("root_node_id must reference an existing node")

    def node(self, node_id: str) -> PromptNode | None:
        """Return one node by stable identity."""
        return next((node for node in self.nodes if node.node_id == node_id), None)

    def require_node(self, node_id: str) -> PromptNode:
        """Return one node or raise when unavailable."""
        node = self.node(node_id)
        if node is None:
            raise KeyError(f"Prompt graph node not found: {node_id}")
        return node

    def nodes_of_kind(self, kind: PromptNodeKind) -> tuple[PromptNode, ...]:
        """Return matching nodes in deterministic production order."""
        return tuple(
            sorted(
                (node for node in self.nodes if node.kind is kind),
                key=lambda node: (node.sequence, node.node_id),
            )
        )

    def outgoing(self, node_id: str) -> tuple[PromptEdge, ...]:
        """Return outgoing edges in deterministic order."""
        self.require_node(node_id)
        return tuple(
            sorted(
                (edge for edge in self.edges if edge.source_id == node_id),
                key=lambda edge: (edge.sequence, edge.edge_id),
            )
        )

    def incoming(self, node_id: str) -> tuple[PromptEdge, ...]:
        """Return incoming edges in deterministic order."""
        self.require_node(node_id)
        return tuple(
            sorted(
                (edge for edge in self.edges if edge.target_id == node_id),
                key=lambda edge: (edge.sequence, edge.edge_id),
            )
        )

    def reachable_from(self, node_id: str) -> tuple[PromptNode, ...]:
        """Return breadth-first reachable nodes without looping on cycles."""
        self.require_node(node_id)
        visited = {node_id}
        pending = [node_id]
        ordered: list[PromptNode] = []
        while pending:
            source_id = pending.pop(0)
            for edge in self.outgoing(source_id):
                if edge.target_id in visited:
                    continue
                visited.add(edge.target_id)
                pending.append(edge.target_id)
                ordered.append(self.require_node(edge.target_id))
        return tuple(ordered)

    def topological_nodes(self) -> tuple[PromptNode, ...]:
        """Return a deterministic topological order or raise for cycles."""
        indegree = {node.node_id: 0 for node in self.nodes}
        for edge in self.edges:
            indegree[edge.target_id] += 1
        ready = sorted(
            (node for node in self.nodes if indegree[node.node_id] == 0),
            key=lambda node: (node.sequence, node.node_id),
        )
        ordered: list[PromptNode] = []
        while ready:
            node = ready.pop(0)
            ordered.append(node)
            for edge in self.outgoing(node.node_id):
                indegree[edge.target_id] -= 1
                if indegree[edge.target_id] == 0:
                    ready.append(self.require_node(edge.target_id))
                    ready.sort(key=lambda item: (item.sequence, item.node_id))
        if len(ordered) != len(self.nodes):
            raise PromptGraphCycleError("prompt graph contains a directed cycle")
        return tuple(ordered)

    @property
    def has_cycle(self) -> bool:
        """Return whether the graph contains a directed cycle."""
        try:
            self.topological_nodes()
        except PromptGraphCycleError:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize into deterministic JSON-compatible primitives."""
        return _primitive(asdict(self))

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> PromptGraph:
        """Reconstruct and validate a graph from serialized data."""
        metadata_raw = _mapping(raw, "metadata")
        metadata = PromptGraphMetadata(
            graph_id=str(metadata_raw.get("graph_id", "")),
            production_id=str(metadata_raw.get("production_id", "")),
            container_id=str(metadata_raw.get("container_id", "")),
            scene_id=str(metadata_raw.get("scene_id", "")),
            shot_id=str(metadata_raw.get("shot_id", "")),
            clip_id=_optional_string(metadata_raw.get("clip_id")),
            version=str(metadata_raw.get("version", "1.0")),
        )
        nodes = tuple(_node_from_dict(item) for item in _mappings(raw, "nodes"))
        edges = tuple(_edge_from_dict(item) for item in _mappings(raw, "edges"))
        return cls(
            metadata=metadata,
            nodes=nodes,
            edges=edges,
            root_node_id=_optional_string(raw.get("root_node_id")),
        )


def _node_from_dict(raw: dict[str, Any]) -> PromptNode:
    return PromptNode(
        node_id=str(raw.get("node_id", "")),
        kind=PromptNodeKind(str(raw.get("kind", ""))),
        label=str(raw.get("label", "")),
        content=str(raw.get("content", "")),
        canonical_asset_id=_optional_string(raw.get("canonical_asset_id")),
        reference_ids=tuple(str(value) for value in raw.get("reference_ids", ())),
        attributes=_pairs(raw.get("attributes", ())),
        mandatory=bool(raw.get("mandatory", False)),
        sequence=int(raw.get("sequence", 0)),
    )


def _edge_from_dict(raw: dict[str, Any]) -> PromptEdge:
    return PromptEdge(
        edge_id=str(raw.get("edge_id", "")),
        source_id=str(raw.get("source_id", "")),
        target_id=str(raw.get("target_id", "")),
        kind=PromptEdgeKind(str(raw.get("kind", ""))),
        label=str(raw.get("label", "")),
        attributes=_pairs(raw.get("attributes", ())),
        sequence=int(raw.get("sequence", 0)),
    )


def _primitive(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _primitive(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_primitive(item) for item in value]
    return value


def _mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _mappings(raw: dict[str, Any], key: str) -> tuple[dict[str, Any], ...]:
    value = raw.get(key, ())
    if not isinstance(value, list | tuple) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be an array of objects")
    return tuple(value)


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list | tuple):
        raise ValueError("attributes must be an array of pairs")
    pairs: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise ValueError("attributes must contain two-item pairs")
        pairs.append((str(item[0]), str(item[1])))
    return tuple(pairs)


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)
