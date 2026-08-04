"""Deterministic staged construction of renderer-neutral prompt graphs."""

from __future__ import annotations

from dataclasses import dataclass

from .context import PromptGraphBuildContext
from .diagnostics import (
    PromptGraphBuildReport,
    PromptGraphDiagnostic,
    PromptGraphDiagnosticSeverity,
    PromptGraphDiagnosticsFactory,
)
from .models import (
    PromptEdge,
    PromptGraph,
    PromptGraphMetadata,
    PromptNode,
    PromptNodeKind,
)
from .resolver import PromptGraphResolver, PromptGraphSource


@dataclass(frozen=True, slots=True)
class PromptGraphBuildResult:
    graph: PromptGraph
    report: PromptGraphBuildReport


@dataclass(slots=True)
class PromptGraphBuilder:
    """Assemble graph nodes from authoritative resolver contributions."""

    resolver: PromptGraphResolver
    diagnostics_factory: PromptGraphDiagnosticsFactory

    def build(self, context: PromptGraphBuildContext) -> PromptGraphBuildResult:
        sources = self.resolver.resolve(context)
        diagnostics: list[PromptGraphDiagnostic] = []
        root = PromptNode(
            node_id="root",
            kind=PromptNodeKind.ROOT,
            label=f"{context.scene_id} / {context.shot_id}",
            attributes=(
                ("renderer", context.renderer.value),
                ("quality_level", context.quality_level.value),
                ("workflow_id", context.workflow_id),
            ),
            mandatory=True,
        )
        nodes = [root]
        edges: list[PromptEdge] = []
        known_sources = {source.source_id for source in sources}
        for index, source in enumerate(sources, start=1):
            nodes.append(self._node(source))
            parent = source.parent_source_id or root.node_id
            if parent != root.node_id and parent not in known_sources:
                diagnostics.append(
                    PromptGraphDiagnostic(
                        "builder.parent_missing",
                        PromptGraphDiagnosticSeverity.WARNING,
                        "Source parent was unavailable; attached to graph root.",
                        source.source_id,
                    )
                )
                parent = root.node_id
            edges.append(
                PromptEdge(
                    edge_id=f"edge-{index:04d}",
                    source_id=parent,
                    target_id=source.source_id,
                    kind=source.relationship,
                    sequence=source.sequence,
                )
            )
        graph = PromptGraph(
            metadata=PromptGraphMetadata(
                graph_id=context.graph_id,
                production_id=context.production_id,
                container_id=context.container_id,
                scene_id=context.scene_id,
                shot_id=context.shot_id,
                clip_id=context.clip_id,
            ),
            nodes=tuple(nodes),
            edges=tuple(edges),
            root_node_id=root.node_id,
        )
        report = self.diagnostics_factory.create(
            graph.metadata.graph_id,
            len(graph.nodes),
            len(graph.edges),
            tuple(diagnostics),
        )
        return PromptGraphBuildResult(graph, report)

    @staticmethod
    def _node(source: PromptGraphSource) -> PromptNode:
        return PromptNode(
            node_id=source.source_id,
            kind=source.kind,
            label=source.label,
            content=source.content,
            canonical_asset_id=source.canonical_asset_id,
            reference_ids=source.reference_ids,
            attributes=source.attributes,
            mandatory=source.mandatory,
            sequence=source.sequence,
        )
