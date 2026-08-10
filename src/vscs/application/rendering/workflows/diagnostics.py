"""Structured diagnostics for workflow compatibility validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CompatibilitySeverity(StrEnum):
    """Severity of one workflow compatibility finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CompatibilityDiagnostic:
    """One machine-readable compatibility finding."""

    code: str
    severity: CompatibilitySeverity
    message: str
    subject: str | None = None

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("diagnostic code is required")
        if not self.message.strip():
            raise ValueError("diagnostic message is required")


@dataclass(frozen=True, slots=True)
class WorkflowCompatibilityReport:
    """Complete compatibility result for one request and workflow."""

    workflow_id: str
    request_id: str
    diagnostics: tuple[CompatibilityDiagnostic, ...] = ()

    @property
    def passed(self) -> bool:
        """Return whether no error diagnostic was produced."""
        return not any(item.severity is CompatibilitySeverity.ERROR for item in self.diagnostics)

    @property
    def errors(self) -> tuple[CompatibilityDiagnostic, ...]:
        """Return error findings only."""
        return tuple(
            item for item in self.diagnostics if item.severity is CompatibilitySeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[CompatibilityDiagnostic, ...]:
        """Return warning findings only."""
        return tuple(
            item for item in self.diagnostics if item.severity is CompatibilitySeverity.WARNING
        )
