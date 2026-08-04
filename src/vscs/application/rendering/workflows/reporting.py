"""Human-readable reports for workflow discovery and compatibility."""

from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import CompatibilitySeverity, WorkflowCompatibilityReport
from .loader import ManifestDiagnosticLevel, ManifestDiscoveryResult
from .manifest import WorkflowManifest


@dataclass(frozen=True, slots=True)
class WorkflowDiagnosticsFormatter:
    """Format structured workflow diagnostics for users and logs."""

    def format_compatibility(
        self,
        report: WorkflowCompatibilityReport,
        manifest: WorkflowManifest | None = None,
    ) -> str:
        """Return a deterministic human-readable compatibility report."""
        status = "PASS" if report.passed else "FAIL"
        lines = [
            f"Workflow compatibility: {status}",
            f"Workflow: {report.workflow_id}",
            f"Request: {report.request_id}",
        ]
        if manifest is not None:
            lines.extend(
                (
                    f"Name: {manifest.metadata.display_name}",
                    f"Renderer: {manifest.metadata.renderer.value}",
                    "Quality levels: "
                    + ", ".join(level.value for level in manifest.quality_levels),
                )
            )
        grouped = (
            (CompatibilitySeverity.ERROR, "Errors"),
            (CompatibilitySeverity.WARNING, "Warnings"),
            (CompatibilitySeverity.INFO, "Information"),
        )
        for severity, heading in grouped:
            items = tuple(
                item for item in report.diagnostics if item.severity is severity
            )
            if not items:
                continue
            lines.extend(("", f"{heading}:"))
            for item in items:
                subject = f" [{item.subject}]" if item.subject else ""
                lines.append(f"- {item.code}{subject}: {item.message}")
        return "\n".join(lines)

    def format_discovery(self, result: ManifestDiscoveryResult) -> str:
        """Return a deterministic human-readable discovery report."""
        lines = [
            "Workflow manifest discovery",
            f"Files discovered: {result.discovered_files}",
            f"Manifests loaded: {result.loaded_count}",
            f"Errors: {result.error_count}",
        ]
        if result.loaded_workflow_ids:
            lines.extend(
                (
                    "",
                    "Loaded workflows:",
                    *(f"- {workflow_id}" for workflow_id in result.loaded_workflow_ids),
                )
            )
        grouped = (
            (ManifestDiagnosticLevel.ERROR, "Errors"),
            (ManifestDiagnosticLevel.WARNING, "Warnings"),
            (ManifestDiagnosticLevel.INFO, "Information"),
        )
        for level, heading in grouped:
            items = tuple(
                item for item in result.diagnostics if item.level is level
            )
            if not items:
                continue
            lines.extend(("", f"{heading}:"))
            for item in items:
                workflow = f" [{item.workflow_id}]" if item.workflow_id else ""
                lines.append(f"- {item.path}{workflow}: {item.message}")
        return "\n".join(lines)
