"""Core models for renderer-neutral production orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ProductionStage(StrEnum):
    """Logical stages in the VSCS production lifecycle."""

    STORY = "story"
    SSIE = "ssie"
    ACPP = "acpp"
    RESOURCE_RESOLUTION = "resource_resolution"
    PROMPT_COMPILATION = "prompt_compilation"
    RENDER_JOB_COMPILATION = "render_job_compilation"
    BUNDLE_VALIDATION = "bundle_validation"
    RENDERING = "rendering"
    QUALITY_CONTROL = "quality_control"
    EPISODE_ASSEMBLY = "episode_assembly"


class ProductionState(StrEnum):
    """Current lifecycle state for one production node."""

    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ProductionNode:
    """One unit of work in a production dependency graph."""

    node_id: str
    stage: ProductionStage
    state: ProductionState = ProductionState.PENDING
    clip_id: str | None = None
    artifact_id: str | None = None
    dependencies: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionPipeline:
    """Versioned graph of production work for one episode or production."""

    pipeline_id: str
    production_id: str
    episode_id: str
    nodes: tuple[ProductionNode, ...]
    schema_version: str = "1.0"
    metadata: dict[str, str] = field(default_factory=dict)

    def node(self, node_id: str) -> ProductionNode | None:
        """Return a node by identity."""
        return next((node for node in self.nodes if node.node_id == node_id), None)

    def nodes_for_stage(self, stage: ProductionStage) -> tuple[ProductionNode, ...]:
        """Return nodes assigned to one stage in graph order."""
        return tuple(node for node in self.nodes if node.stage is stage)
