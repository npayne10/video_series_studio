"""Validation for production pipeline definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .graph import ProductionGraph, ProductionGraphError
from .models import ProductionPipeline


class PipelineValidationSeverity(StrEnum):
    """Severity assigned to one pipeline finding."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class PipelineValidationIssue:
    """One machine-readable production pipeline finding."""

    severity: PipelineValidationSeverity
    code: str
    message: str
    node_id: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineValidationResult:
    """Complete production pipeline validation result."""

    issues: tuple[PipelineValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        """Return whether no error-level findings were emitted."""
        return not any(issue.severity is PipelineValidationSeverity.ERROR for issue in self.issues)


class ProductionPipelineValidator:
    """Validate pipeline identity, graph integrity, and node definitions."""

    def validate(self, pipeline: ProductionPipeline) -> PipelineValidationResult:
        """Validate one production pipeline."""
        issues: list[PipelineValidationIssue] = []
        for field_name, value in (
            ("pipeline_id", pipeline.pipeline_id),
            ("production_id", pipeline.production_id),
            ("episode_id", pipeline.episode_id),
            ("schema_version", pipeline.schema_version),
        ):
            if not value.strip():
                issues.append(
                    PipelineValidationIssue(
                        PipelineValidationSeverity.ERROR,
                        "MISSING_IDENTITY",
                        f"{field_name} must not be empty.",
                    )
                )
        if not pipeline.nodes:
            issues.append(
                PipelineValidationIssue(
                    PipelineValidationSeverity.ERROR,
                    "EMPTY_PIPELINE",
                    "Production pipeline must contain at least one node.",
                )
            )
            return PipelineValidationResult(tuple(issues))

        node_ids = [node.node_id for node in pipeline.nodes]
        duplicates = sorted(node_id for node_id in set(node_ids) if node_ids.count(node_id) > 1)
        for node_id in duplicates:
            issues.append(
                PipelineValidationIssue(
                    PipelineValidationSeverity.ERROR,
                    "DUPLICATE_NODE_ID",
                    f"Duplicate production node ID: {node_id}",
                    node_id,
                )
            )
        for node in pipeline.nodes:
            if not node.node_id.strip():
                issues.append(
                    PipelineValidationIssue(
                        PipelineValidationSeverity.ERROR,
                        "EMPTY_NODE_ID",
                        "Production node ID must not be empty.",
                    )
                )
            if node.node_id in node.dependencies:
                issues.append(
                    PipelineValidationIssue(
                        PipelineValidationSeverity.ERROR,
                        "SELF_DEPENDENCY",
                        "Production node may not depend on itself.",
                        node.node_id,
                    )
                )
            if len(set(node.dependencies)) != len(node.dependencies):
                issues.append(
                    PipelineValidationIssue(
                        PipelineValidationSeverity.ERROR,
                        "DUPLICATE_DEPENDENCY",
                        "Production node dependencies must be unique.",
                        node.node_id,
                    )
                )
        if not duplicates:
            try:
                ProductionGraph(pipeline).topological_order()
            except ProductionGraphError as exc:
                issues.append(
                    PipelineValidationIssue(
                        PipelineValidationSeverity.ERROR,
                        "INVALID_DEPENDENCY_GRAPH",
                        str(exc),
                    )
                )
        return PipelineValidationResult(tuple(issues))
