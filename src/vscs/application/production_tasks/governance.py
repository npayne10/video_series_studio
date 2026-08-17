"""Governance policy for provider-neutral ProductionTask authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import ProductionAuthorityType, ProductionTask, ProductionTaskState


class ProductionTaskGovernanceSeverity(StrEnum):
    """Severity of one ProductionTask governance finding."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ProductionTaskGovernanceIssue:
    """One deterministic ProductionTask governance finding."""

    code: str
    message: str
    severity: ProductionTaskGovernanceSeverity = ProductionTaskGovernanceSeverity.ERROR


@dataclass(frozen=True, slots=True)
class ProductionTaskGovernanceResult:
    """Deterministic validation result for one ProductionTask."""

    task_id: str
    issues: tuple[ProductionTaskGovernanceIssue, ...]

    @property
    def valid(self) -> bool:
        """Return whether the task satisfies all blocking governance rules."""
        return not any(
            issue.severity is ProductionTaskGovernanceSeverity.ERROR for issue in self.issues
        )


class ProductionTaskGovernanceError(ValueError):
    """Raised when a ProductionTask violates a blocking governance rule."""


class ProductionTaskGovernanceService:
    """Enforce vNext authority and provider-neutrality rules for ProductionTasks."""

    _EXECUTION_METADATA_TOKENS = frozenset(
        {
            "adapter",
            "endpoint",
            "model",
            "node",
            "provider",
            "renderer",
            "workflow",
        }
    )

    def validate(self, task: ProductionTask) -> ProductionTaskGovernanceResult:
        """Validate one task without mutating production authority or execution state."""
        issues: list[ProductionTaskGovernanceIssue] = []
        authority = task.authority

        if authority.authority_type is not ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION:
            issues.append(
                ProductionTaskGovernanceIssue(
                    code="unsupported-authority",
                    message="Phase 19.6.1 ProductionTasks must originate from an approved UPD.",
                )
            )
        if not authority.approved:
            issues.append(
                ProductionTaskGovernanceIssue(
                    code="authority-not-approved",
                    message="ProductionTask source authority must be explicitly approved.",
                )
            )
        if authority.approved and not authority.approved_by:
            issues.append(
                ProductionTaskGovernanceIssue(
                    code="missing-human-approval",
                    message="Approved ProductionTask authority must identify the human approver.",
                )
            )
        if task.state is not ProductionTaskState.PLANNED:
            issues.append(
                ProductionTaskGovernanceIssue(
                    code="invalid-initial-state",
                    message=(
                        "Phase 19.6.1 task derivation may create only PLANNED tasks; scheduling "
                        "and execution own later state transitions."
                    ),
                )
            )

        for source_name, values in (("metadata", task.metadata), ("provenance", task.provenance)):
            for key, _value in values:
                normalized = key.casefold().replace("-", "_")
                tokens = set(normalized.split("_"))
                if tokens & self._EXECUTION_METADATA_TOKENS:
                    issues.append(
                        ProductionTaskGovernanceIssue(
                            code="provider-specific-data",
                            message=(
                                f"ProductionTask {source_name} key {key!r} leaks provider/execution "
                                "detail into provider-neutral task authority."
                            ),
                        )
                    )

        return ProductionTaskGovernanceResult(task_id=task.task_id, issues=tuple(issues))

    def require_valid(self, task: ProductionTask) -> None:
        """Raise a deterministic error if the task violates governance."""
        result = self.validate(task)
        if result.valid:
            return
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in result.issues)
        raise ProductionTaskGovernanceError(
            f"ProductionTask {task.task_id!r} failed governance: {details}"
        )
