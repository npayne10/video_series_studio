"""Deterministic serialization for production pipelines."""

from __future__ import annotations

import hashlib
import json

from .models import ProductionNode, ProductionPipeline, ProductionStage, ProductionState
from .validator import ProductionPipelineValidator


class ProductionPipelineSerializationError(ValueError):
    """Raised when pipeline JSON cannot be restored."""


class ProductionPipelineSerializer:
    """Serialize, restore, and checksum production pipelines."""

    def dumps(self, pipeline: ProductionPipeline) -> str:
        """Serialize a valid pipeline to stable JSON."""
        result = ProductionPipelineValidator().validate(pipeline)
        if not result.passed:
            raise ProductionPipelineSerializationError("Invalid production pipeline")
        return json.dumps(self.to_dict(pipeline), indent=2, sort_keys=True) + "\n"

    def loads(self, payload: str) -> ProductionPipeline:
        """Restore and validate a pipeline from JSON text."""
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ProductionPipelineSerializationError(str(exc)) from exc
        if not isinstance(raw, dict):
            raise ProductionPipelineSerializationError("Pipeline JSON root must be an object")
        pipeline = self.from_dict(raw)
        result = ProductionPipelineValidator().validate(pipeline)
        if not result.passed:
            raise ProductionPipelineSerializationError("Invalid production pipeline")
        return pipeline

    def checksum(self, pipeline: ProductionPipeline) -> str:
        """Return a deterministic SHA-256 checksum."""
        encoded = json.dumps(
            self.to_dict(pipeline), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def to_dict(pipeline: ProductionPipeline) -> dict[str, object]:
        """Convert a pipeline into JSON-compatible primitives."""
        return {
            "pipeline_id": pipeline.pipeline_id,
            "production_id": pipeline.production_id,
            "episode_id": pipeline.episode_id,
            "schema_version": pipeline.schema_version,
            "metadata": dict(pipeline.metadata),
            "nodes": [
                {
                    "node_id": node.node_id,
                    "stage": node.stage.value,
                    "state": node.state.value,
                    "clip_id": node.clip_id,
                    "artifact_id": node.artifact_id,
                    "dependencies": list(node.dependencies),
                    "metadata": [list(item) for item in node.metadata],
                }
                for node in pipeline.nodes
            ],
        }

    @staticmethod
    def from_dict(raw: dict[str, object]) -> ProductionPipeline:
        """Restore a pipeline from JSON-compatible primitives."""
        nodes_raw = raw.get("nodes")
        if not isinstance(nodes_raw, list):
            raise ProductionPipelineSerializationError("nodes must be a list")
        nodes: list[ProductionNode] = []
        for item in nodes_raw:
            if not isinstance(item, dict):
                raise ProductionPipelineSerializationError("node must be an object")
            nodes.append(
                ProductionNode(
                    node_id=str(item["node_id"]),
                    stage=ProductionStage(str(item["stage"])),
                    state=ProductionState(str(item["state"])),
                    clip_id=None if item.get("clip_id") is None else str(item["clip_id"]),
                    artifact_id=(
                        None
                        if item.get("artifact_id") is None
                        else str(item["artifact_id"])
                    ),
                    dependencies=tuple(str(value) for value in item.get("dependencies", [])),
                    metadata=tuple(
                        (str(pair[0]), str(pair[1]))
                        for pair in item.get("metadata", [])
                    ),
                )
            )
        metadata_raw = raw.get("metadata", {})
        if not isinstance(metadata_raw, dict):
            raise ProductionPipelineSerializationError("metadata must be an object")
        return ProductionPipeline(
            pipeline_id=str(raw["pipeline_id"]),
            production_id=str(raw["production_id"]),
            episode_id=str(raw["episode_id"]),
            schema_version=str(raw.get("schema_version", "1.0")),
            nodes=tuple(nodes),
            metadata={str(key): str(value) for key, value in metadata_raw.items()},
        )
