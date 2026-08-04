"""Structured diagnostics and reports for prompt graph construction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PromptGraphDiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PromptGraphDiagnostic:
    code: str
    severity: PromptGraphDiagnosticSeverity
    message: str
    subject: str = ""


@dataclass(frozen=True, slots=True)
class PromptGraphBuildReport:
    graph_id: str
    nodes_created: int
    edges_created: int
    diagnostics: tuple[PromptGraphDiagnostic, ...] = ()

    @property
    def passed(self) -> bool:
        return not any(
            item.severity is PromptGraphDiagnosticSeverity.ERROR
            for item in self.diagnostics
        )


class PromptGraphDiagnosticsFactory:
    """Create deterministic build reports."""

    def create(
        self,
        graph_id: str,
        nodes_created: int,
        edges_created: int,
        diagnostics: tuple[PromptGraphDiagnostic, ...] = (),
    ) -> PromptGraphBuildReport:
        return PromptGraphBuildReport(
            graph_id,
            nodes_created,
            edges_created,
            tuple(sorted(diagnostics, key=lambda item: (item.severity, item.code, item.subject))),
        )
