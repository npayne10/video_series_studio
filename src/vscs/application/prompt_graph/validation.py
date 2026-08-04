"""Production-readiness validation for renderer-neutral prompt graphs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .models import PromptGraph, PromptNodeKind


class PromptGraphValidationSeverity(StrEnum):
    """Severity assigned to one graph validation finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PromptGraphValidationIssue:
    """One structured production-readiness finding."""

    code: str
    severity: PromptGraphValidationSeverity
    message: str
    subject: str = ""
    weight: int = 0


@dataclass(frozen=True, slots=True)
class PromptGraphValidationPolicy:
    """Declarative requirements for one prompt-graph validation pass."""

    required_node_kinds: tuple[PromptNodeKind, ...] = (
        PromptNodeKind.VISUAL_INTENT,
        PromptNodeKind.CAMERA,
        PromptNodeKind.LIGHTING,
        PromptNodeKind.RENDERER,
        PromptNodeKind.QUALITY,
    )
    canonical_asset_kinds: tuple[PromptNodeKind, ...] = (
        PromptNodeKind.CHARACTER,
        PromptNodeKind.SHIP,
        PromptNodeKind.VEHICLE,
        PromptNodeKind.LOCATION,
        PromptNodeKind.ENVIRONMENT,
        PromptNodeKind.PROP,
    )
    reference_required_kinds: tuple[PromptNodeKind, ...] = (
        PromptNodeKind.CHARACTER,
        PromptNodeKind.SHIP,
        PromptNodeKind.VEHICLE,
        PromptNodeKind.LOCATION,
        PromptNodeKind.ENVIRONMENT,
    )
    require_continuity_for_references: bool = True
    require_dialogue_content: bool = True
    production_ready_threshold: int = 85

    def __post_init__(self) -> None:
        if not 0 <= self.production_ready_threshold <= 100:
            raise ValueError("production_ready_threshold must be between 0 and 100")


@dataclass(frozen=True, slots=True)
class PromptGraphResourceInventory:
    """Known canonical resources available to the validator."""

    canonical_asset_ids: frozenset[str] = frozenset()
    reference_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class PromptGraphCompleteness:
    """Weighted completeness result for a validated prompt graph."""

    score: int
    maximum_score: int
    percentage: int
    production_ready: bool


@dataclass(frozen=True, slots=True)
class PromptGraphValidationReport:
    """Complete validation outcome for one prompt graph."""

    graph_id: str
    completeness: PromptGraphCompleteness
    issues: tuple[PromptGraphValidationIssue, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(
            issue.severity is PromptGraphValidationSeverity.ERROR
            for issue in self.issues
        )


@dataclass(slots=True)
class PromptGraphValidator:
    """Validate graph integrity and production completeness without compilation."""

    policy: PromptGraphValidationPolicy = field(
        default_factory=PromptGraphValidationPolicy
    )

    def validate(
        self,
        graph: PromptGraph,
        inventory: PromptGraphResourceInventory | None = None,
    ) -> PromptGraphValidationReport:
        resources = inventory or PromptGraphResourceInventory()
        issues: list[PromptGraphValidationIssue] = []
        earned = 0
        maximum = 0

        maximum += 15
        if graph.has_cycle:
            issues.append(
                PromptGraphValidationIssue(
                    "graph.cycle",
                    PromptGraphValidationSeverity.ERROR,
                    "Prompt graph contains a directed cycle.",
                    graph.metadata.graph_id,
                    15,
                )
            )
        else:
            earned += 15

        earned_delta, maximum_delta = self._required_kinds(graph, issues)
        earned += earned_delta
        maximum += maximum_delta

        earned_delta, maximum_delta = self._mandatory_nodes(graph, issues)
        earned += earned_delta
        maximum += maximum_delta

        earned_delta, maximum_delta = self._canonical_resources(
            graph,
            resources,
            issues,
        )
        earned += earned_delta
        maximum += maximum_delta

        earned_delta, maximum_delta = self._continuity(graph, issues)
        earned += earned_delta
        maximum += maximum_delta

        earned_delta, maximum_delta = self._dialogue(graph, issues)
        earned += earned_delta
        maximum += maximum_delta

        percentage = 100 if maximum == 0 else round(earned * 100 / maximum)
        sorted_issues = tuple(
            sorted(
                issues,
                key=lambda issue: (
                    issue.severity,
                    issue.code,
                    issue.subject,
                ),
            )
        )
        passed = not any(
            issue.severity is PromptGraphValidationSeverity.ERROR
            for issue in sorted_issues
        )
        completeness = PromptGraphCompleteness(
            score=earned,
            maximum_score=maximum,
            percentage=percentage,
            production_ready=(
                passed and percentage >= self.policy.production_ready_threshold
            ),
        )
        return PromptGraphValidationReport(
            graph.metadata.graph_id,
            completeness,
            sorted_issues,
        )

    def _required_kinds(
        self,
        graph: PromptGraph,
        issues: list[PromptGraphValidationIssue],
    ) -> tuple[int, int]:
        earned = 0
        maximum = 5 * len(self.policy.required_node_kinds)
        for kind in self.policy.required_node_kinds:
            if graph.nodes_of_kind(kind):
                earned += 5
                continue
            issues.append(
                PromptGraphValidationIssue(
                    "graph.required_kind_missing",
                    PromptGraphValidationSeverity.ERROR,
                    f"Required prompt graph node kind is missing: {kind.value}.",
                    kind.value,
                    5,
                )
            )
        return earned, maximum

    @staticmethod
    def _mandatory_nodes(
        graph: PromptGraph,
        issues: list[PromptGraphValidationIssue],
    ) -> tuple[int, int]:
        mandatory = tuple(node for node in graph.nodes if node.mandatory)
        maximum = 4 * len(mandatory)
        earned = 0
        for node in mandatory:
            if node.content.strip() or node.kind is PromptNodeKind.ROOT:
                earned += 4
                continue
            issues.append(
                PromptGraphValidationIssue(
                    "graph.mandatory_content_missing",
                    PromptGraphValidationSeverity.ERROR,
                    "Mandatory node has no descriptive content.",
                    node.node_id,
                    4,
                )
            )
        return earned, maximum

    def _canonical_resources(
        self,
        graph: PromptGraph,
        inventory: PromptGraphResourceInventory,
        issues: list[PromptGraphValidationIssue],
    ) -> tuple[int, int]:
        nodes = tuple(
            node
            for node in graph.nodes
            if node.kind in self.policy.canonical_asset_kinds
        )
        earned = 0
        maximum = 0
        for node in nodes:
            maximum += 8
            if node.canonical_asset_id:
                if (
                    inventory.canonical_asset_ids
                    and node.canonical_asset_id not in inventory.canonical_asset_ids
                ):
                    issues.append(
                        PromptGraphValidationIssue(
                            "graph.canonical_asset_unresolved",
                            PromptGraphValidationSeverity.ERROR,
                            "Canonical asset is not present in the resource inventory.",
                            node.node_id,
                            4,
                        )
                    )
                else:
                    earned += 4
            else:
                issues.append(
                    PromptGraphValidationIssue(
                        "graph.canonical_asset_missing",
                        PromptGraphValidationSeverity.ERROR,
                        "Canonical production entity has no canonical asset ID.",
                        node.node_id,
                        4,
                    )
                )

            if node.kind not in self.policy.reference_required_kinds:
                earned += 4
                continue
            if not node.reference_ids:
                issues.append(
                    PromptGraphValidationIssue(
                        "graph.reference_missing",
                        PromptGraphValidationSeverity.WARNING,
                        "Canonical visual entity has no approved reference image.",
                        node.node_id,
                        4,
                    )
                )
                continue
            unresolved = tuple(
                reference_id
                for reference_id in node.reference_ids
                if inventory.reference_ids
                and reference_id not in inventory.reference_ids
            )
            if unresolved:
                issues.append(
                    PromptGraphValidationIssue(
                        "graph.reference_unresolved",
                        PromptGraphValidationSeverity.ERROR,
                        "One or more approved reference IDs are unavailable.",
                        node.node_id,
                        4,
                    )
                )
            else:
                earned += 4
        return earned, maximum

    def _continuity(
        self,
        graph: PromptGraph,
        issues: list[PromptGraphValidationIssue],
    ) -> tuple[int, int]:
        references_present = any(node.reference_ids for node in graph.nodes)
        maximum = 10 if references_present else 0
        if not references_present:
            return 0, 0
        continuity_nodes = graph.nodes_of_kind(PromptNodeKind.CONTINUITY)
        if continuity_nodes:
            return 10, maximum
        severity = (
            PromptGraphValidationSeverity.ERROR
            if self.policy.require_continuity_for_references
            else PromptGraphValidationSeverity.WARNING
        )
        issues.append(
            PromptGraphValidationIssue(
                "graph.continuity_missing",
                severity,
                "Reference-driven graph has no continuity node.",
                graph.metadata.shot_id,
                10,
            )
        )
        return 0, maximum

    def _dialogue(
        self,
        graph: PromptGraph,
        issues: list[PromptGraphValidationIssue],
    ) -> tuple[int, int]:
        dialogue_nodes = graph.nodes_of_kind(PromptNodeKind.DIALOGUE)
        maximum = 5 * len(dialogue_nodes)
        earned = 0
        for node in dialogue_nodes:
            if node.content.strip():
                earned += 5
                continue
            severity = (
                PromptGraphValidationSeverity.ERROR
                if self.policy.require_dialogue_content
                else PromptGraphValidationSeverity.WARNING
            )
            issues.append(
                PromptGraphValidationIssue(
                    "graph.dialogue_content_missing",
                    severity,
                    "Dialogue node has no spoken content.",
                    node.node_id,
                    5,
                )
            )
        return earned, maximum
