"""Dependency analysis for production pipelines."""

from __future__ import annotations

from collections import deque

from .models import ProductionNode, ProductionPipeline, ProductionState


class ProductionGraphError(ValueError):
    """Raised when a production graph cannot be evaluated."""


class ProductionGraph:
    """Analyze dependency ordering and readiness for a production pipeline."""

    def __init__(self, pipeline: ProductionPipeline) -> None:
        self.pipeline = pipeline
        self._nodes = {node.node_id: node for node in pipeline.nodes}

    def topological_order(self) -> tuple[ProductionNode, ...]:
        """Return nodes in deterministic dependency order."""
        indegree = dict.fromkeys(self._nodes, 0)
        dependants: dict[str, list[str]] = {node_id: [] for node_id in self._nodes}
        for node in self.pipeline.nodes:
            for dependency in node.dependencies:
                if dependency not in self._nodes:
                    raise ProductionGraphError(
                        f"Unknown dependency {dependency!r} for node {node.node_id!r}"
                    )
                indegree[node.node_id] += 1
                dependants[dependency].append(node.node_id)

        ready = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
        ordered: list[ProductionNode] = []
        while ready:
            node_id = ready.popleft()
            ordered.append(self._nodes[node_id])
            for dependant in sorted(dependants[node_id]):
                indegree[dependant] -= 1
                if indegree[dependant] == 0:
                    ready.append(dependant)
        if len(ordered) != len(self._nodes):
            raise ProductionGraphError("Production graph contains a dependency cycle")
        return tuple(ordered)

    def ready_nodes(self) -> tuple[ProductionNode, ...]:
        """Return pending nodes whose dependencies are completed."""
        completed = {
            node.node_id for node in self.pipeline.nodes if node.state is ProductionState.COMPLETED
        }
        return tuple(
            node
            for node in self.topological_order()
            if node.state in {ProductionState.PENDING, ProductionState.READY}
            and all(dependency in completed for dependency in node.dependencies)
        )

    def blocked_nodes(self) -> tuple[ProductionNode, ...]:
        """Return nodes blocked by failed or cancelled dependencies."""
        terminal_failures = {
            node.node_id
            for node in self.pipeline.nodes
            if node.state in {ProductionState.FAILED, ProductionState.CANCELLED}
        }
        return tuple(
            node
            for node in self.pipeline.nodes
            if node.state not in {ProductionState.COMPLETED, ProductionState.CANCELLED}
            and any(dependency in terminal_failures for dependency in node.dependencies)
        )
