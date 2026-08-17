"""Compatibility projection from ProductionTask authority to the legacy render pipeline."""

from __future__ import annotations

from dataclasses import replace

from vscs.application.production_pipeline import (
    ProductionNode,
    ProductionPipeline,
    ProductionStage,
    ProductionState,
    RenderQueueEntry,
)

from .models import ProductionTask, ProductionTaskState


PRODUCTION_TASK_ID_METADATA_KEY = "production_task_id"


class ProductionTaskLegacyBridge:
    """Project authoritative ProductionTask state into existing render orchestration.

    The bridge is intentionally one-way: legacy pipeline and queue records do not own
    ProductionTask state. They remain compatibility projections while downstream
    execution is migrated incrementally.
    """

    _STATE_MAP: dict[ProductionTaskState, ProductionState] = {
        ProductionTaskState.PLANNED: ProductionState.PENDING,
        ProductionTaskState.READY: ProductionState.READY,
        ProductionTaskState.BLOCKED: ProductionState.BLOCKED,
        ProductionTaskState.RUNNING: ProductionState.RUNNING,
        ProductionTaskState.COMPLETED: ProductionState.COMPLETED,
        ProductionTaskState.FAILED: ProductionState.FAILED,
        ProductionTaskState.CANCELLED: ProductionState.CANCELLED,
        ProductionTaskState.SUPERSEDED: ProductionState.CANCELLED,
    }

    def bind_queue_entry(
        self,
        entry: RenderQueueEntry,
        task: ProductionTask,
    ) -> RenderQueueEntry:
        """Attach a ProductionTask identity to an existing queue entry via metadata."""
        metadata = dict(entry.metadata)
        existing = metadata.get(PRODUCTION_TASK_ID_METADATA_KEY)
        if existing is not None and existing != task.task_id:
            raise ValueError(
                f"Queue entry {entry.entry_id} is already bound to ProductionTask {existing}"
            )
        metadata[PRODUCTION_TASK_ID_METADATA_KEY] = task.task_id
        return replace(entry, metadata=tuple(sorted(metadata.items())))

    @staticmethod
    def task_id_for_entry(entry: RenderQueueEntry) -> str | None:
        """Return the ProductionTask identity carried by one legacy queue entry."""
        value = dict(entry.metadata).get(PRODUCTION_TASK_ID_METADATA_KEY)
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def reconcile_pipeline(
        self,
        pipeline: ProductionPipeline,
        task: ProductionTask,
        *,
        clip_id: str,
    ) -> ProductionPipeline:
        """Mirror authoritative task state into the matching legacy rendering node."""
        legacy_state = self._STATE_MAP[task.state]
        nodes: list[ProductionNode] = []
        for node in pipeline.nodes:
            if node.stage is ProductionStage.RENDERING and node.clip_id == clip_id:
                nodes.append(replace(node, state=legacy_state))
            else:
                nodes.append(node)
        return replace(pipeline, nodes=tuple(nodes))
