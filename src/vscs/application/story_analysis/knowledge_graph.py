"""Deterministic construction of the VSCS Story Knowledge Graph."""

from __future__ import annotations

from hashlib import sha1

from vscs.domain.story_analysis import (
    Action,
    AnalysisResult,
    Character,
    Dialogue,
    Emotion,
    Location,
    Prop,
    Relationship,
    SourceSpan,
    Technology,
    TimelineEvent,
)
from vscs.domain.story_analysis.graph import (
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    StoryKnowledgeGraph,
)


class StoryKnowledgeGraphBuilder:
    """Project an AnalysisResult into a validated immutable knowledge graph."""

    def build(self, result: AnalysisResult) -> StoryKnowledgeGraph:
        nodes = self._nodes(result)
        node_by_model_id = {node.source_model_id: node.node_id for node in nodes}
        edges = self._edges(result, node_by_model_id)
        return StoryKnowledgeGraph(
            story_id=result.story_id,
            source_revision=result.source_revision,
            nodes=nodes,
            edges=edges,
        )

    def _nodes(self, result: AnalysisResult) -> tuple[GraphNode, ...]:
        nodes: list[GraphNode] = []
        for entity in result.entities:
            if isinstance(entity, Character):
                kind = GraphNodeKind.CHARACTER
            elif isinstance(entity, Location):
                kind = GraphNodeKind.LOCATION
            elif isinstance(entity, Technology):
                kind = GraphNodeKind.TECHNOLOGY
            elif isinstance(entity, Prop):
                kind = GraphNodeKind.PROP
            else:
                continue
            nodes.append(
                GraphNode(
                    node_id=self._node_id(kind, entity.entity_id),
                    kind=kind,
                    label=entity.name,
                    source_model_id=entity.entity_id,
                    sources=entity.sources,
                    confidence=entity.confidence,
                )
            )

        nodes.extend(self._dialogue_nodes(result.dialogues))
        nodes.extend(self._action_nodes(result.actions))
        nodes.extend(self._emotion_nodes(result.emotions))
        nodes.extend(self._timeline_nodes(result.timeline_events))
        return tuple(nodes)

    def _dialogue_nodes(self, items: tuple[Dialogue, ...]) -> list[GraphNode]:
        return [
            GraphNode(
                node_id=self._node_id(GraphNodeKind.DIALOGUE, item.dialogue_id),
                kind=GraphNodeKind.DIALOGUE,
                label=item.text,
                source_model_id=item.dialogue_id,
                sources=(item.source,),
                confidence=item.confidence,
            )
            for item in items
        ]

    def _action_nodes(self, items: tuple[Action, ...]) -> list[GraphNode]:
        return [
            GraphNode(
                node_id=self._node_id(GraphNodeKind.ACTION, item.action_id),
                kind=GraphNodeKind.ACTION,
                label=item.summary,
                source_model_id=item.action_id,
                sources=(item.source,),
                confidence=item.confidence,
            )
            for item in items
        ]

    def _emotion_nodes(self, items: tuple[Emotion, ...]) -> list[GraphNode]:
        return [
            GraphNode(
                node_id=self._node_id(GraphNodeKind.EMOTION, item.emotion_id),
                kind=GraphNodeKind.EMOTION,
                label=item.emotion,
                source_model_id=item.emotion_id,
                sources=(item.source,),
                confidence=item.confidence,
            )
            for item in items
        ]

    def _timeline_nodes(self, items: tuple[TimelineEvent, ...]) -> list[GraphNode]:
        return [
            GraphNode(
                node_id=self._node_id(GraphNodeKind.TIMELINE_EVENT, item.event_id),
                kind=GraphNodeKind.TIMELINE_EVENT,
                label=item.summary,
                source_model_id=item.event_id,
                sources=item.sources,
                confidence=item.confidence,
            )
            for item in items
        ]

    def _edges(
        self,
        result: AnalysisResult,
        node_by_model_id: dict[str, str],
    ) -> tuple[GraphEdge, ...]:
        edges: list[GraphEdge] = []
        edges.extend(self._relationship_edges(result.relationships, node_by_model_id))
        edges.extend(self._dialogue_edges(result.dialogues, node_by_model_id))
        edges.extend(self._action_edges(result.actions, node_by_model_id))
        edges.extend(self._emotion_edges(result.emotions, node_by_model_id))
        edges.extend(self._timeline_edges(result.timeline_events, node_by_model_id))
        return tuple(edges)

    def _relationship_edges(
        self,
        items: tuple[Relationship, ...],
        index: dict[str, str],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for item in items:
            source = index.get(item.source_entity_id)
            target = index.get(item.target_entity_id)
            if source is None or target is None:
                continue
            edges.append(
                self._edge(
                    item.relationship_id,
                    GraphEdgeKind.RELATES_TO,
                    source,
                    target,
                    item.relationship_type,
                    item.sources,
                    item.confidence,
                )
            )
        return edges

    def _dialogue_edges(
        self,
        items: tuple[Dialogue, ...],
        index: dict[str, str],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for item in items:
            dialogue = index[item.dialogue_id]
            speaker = item.speaker_entity_id
            if speaker is not None and speaker in index:
                edges.append(
                    self._edge(
                        f"{item.dialogue_id}:speaker",
                        GraphEdgeKind.SPEAKS,
                        index[speaker],
                        dialogue,
                        "speaks",
                        (item.source,),
                        item.confidence,
                    )
                )
            for addressee in item.addressee_entity_ids:
                if addressee not in index:
                    continue
                edges.append(
                    self._edge(
                        f"{item.dialogue_id}:addressee:{addressee}",
                        GraphEdgeKind.ADDRESSES,
                        dialogue,
                        index[addressee],
                        "addresses",
                        (item.source,),
                        item.confidence,
                    )
                )
        return edges

    def _action_edges(
        self,
        items: tuple[Action, ...],
        index: dict[str, str],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for item in items:
            action = index[item.action_id]
            for actor in item.actor_entity_ids:
                if actor in index:
                    edges.append(
                        self._edge(
                            f"{item.action_id}:actor:{actor}",
                            GraphEdgeKind.ACTS_IN,
                            index[actor],
                            action,
                            "acts in",
                            (item.source,),
                            item.confidence,
                        )
                    )
            for target in item.target_entity_ids:
                if target in index:
                    edges.append(
                        self._edge(
                            f"{item.action_id}:target:{target}",
                            GraphEdgeKind.TARGETS,
                            action,
                            index[target],
                            "targets",
                            (item.source,),
                            item.confidence,
                        )
                    )
            location = item.location_entity_id
            if location is not None and location in index:
                edges.append(
                    self._edge(
                        f"{item.action_id}:location",
                        GraphEdgeKind.LOCATED_AT,
                        action,
                        index[location],
                        "located at",
                        (item.source,),
                        item.confidence,
                    )
                )
        return edges

    def _emotion_edges(
        self,
        items: tuple[Emotion, ...],
        index: dict[str, str],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for item in items:
            subject = index.get(item.subject_entity_id)
            emotion = index[item.emotion_id]
            if subject is None:
                continue
            edges.append(
                self._edge(
                    f"{item.emotion_id}:subject",
                    GraphEdgeKind.FEELS,
                    subject,
                    emotion,
                    "feels",
                    (item.source,),
                    item.confidence,
                )
            )
        return edges

    def _timeline_edges(
        self,
        items: tuple[TimelineEvent, ...],
        index: dict[str, str],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        ordered = tuple(sorted(items, key=lambda item: item.sequence_index))
        for item in ordered:
            event = index[item.event_id]
            for participant in item.participant_entity_ids:
                if participant in index:
                    edges.append(
                        self._edge(
                            f"{item.event_id}:participant:{participant}",
                            GraphEdgeKind.PARTICIPATES_IN,
                            index[participant],
                            event,
                            "participates in",
                            item.sources,
                            item.confidence,
                        )
                    )
            location = item.location_entity_id
            if location is not None and location in index:
                edges.append(
                    self._edge(
                        f"{item.event_id}:location",
                        GraphEdgeKind.LOCATED_AT,
                        event,
                        index[location],
                        "located at",
                        item.sources,
                        item.confidence,
                    )
                )
        for current, following in zip(ordered, ordered[1:], strict=False):
            edges.append(
                self._edge(
                    f"timeline:{current.event_id}:{following.event_id}",
                    GraphEdgeKind.PRECEDES,
                    index[current.event_id],
                    index[following.event_id],
                    "precedes",
                    current.sources,
                    min(current.confidence, following.confidence),
                )
            )
        return edges

    @staticmethod
    def _node_id(kind: GraphNodeKind, source_model_id: str) -> str:
        return f"{kind.value}:{source_model_id}"

    @staticmethod
    def _edge(
        seed: str,
        kind: GraphEdgeKind,
        source: str,
        target: str,
        label: str,
        sources: tuple[SourceSpan, ...],
        confidence: float,
    ) -> GraphEdge:
        digest = sha1(
            f"{kind.value}|{source}|{target}|{seed}".encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()[:12]
        return GraphEdge(
            edge_id=f"edge:{kind.value}:{digest}",
            kind=kind,
            source_node_id=source,
            target_node_id=target,
            label=label,
            sources=sources,
            confidence=confidence,
        )
