"""Tests for human-readable workflow diagnostics."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import (
    CompatibilityDiagnostic,
    CompatibilitySeverity,
    ManifestDiagnostic,
    ManifestDiagnosticLevel,
    ManifestDiscoveryResult,
    WorkflowCompatibilityReport,
    WorkflowDiagnosticsFormatter,
)


def test_compatibility_report_groups_findings_by_severity() -> None:
    report = WorkflowCompatibilityReport(
        workflow_id="ltx23_preview_v1",
        request_id="REQ-001",
        diagnostics=(
            CompatibilityDiagnostic(
                "workflow.resource_missing",
                CompatibilitySeverity.ERROR,
                "Required video model is not installed.",
                "ltx-2.3",
            ),
            CompatibilityDiagnostic(
                "workflow.resources_unverified",
                CompatibilitySeverity.WARNING,
                "Optional resources were not checked.",
            ),
        ),
    )

    text = WorkflowDiagnosticsFormatter().format_compatibility(report)

    assert text.startswith("Workflow compatibility: FAIL")
    assert "Errors:" in text
    assert "Warnings:" in text
    assert "[ltx-2.3]" in text


def test_discovery_report_lists_loaded_workflows_and_errors(tmp_path: Path) -> None:
    result = ManifestDiscoveryResult(
        discovered_files=2,
        loaded_workflow_ids=("ltx23_preview_v1",),
        diagnostics=(
            ManifestDiagnostic(
                ManifestDiagnosticLevel.INFO,
                tmp_path / "preview.json",
                "workflow manifest loaded",
                workflow_id="ltx23_preview_v1",
            ),
            ManifestDiagnostic(
                ManifestDiagnosticLevel.ERROR,
                tmp_path / "broken.json",
                "invalid JSON",
            ),
        ),
    )

    text = WorkflowDiagnosticsFormatter().format_discovery(result)

    assert "Files discovered: 2" in text
    assert "Manifests loaded: 1" in text
    assert "Errors: 1" in text
    assert "ltx23_preview_v1" in text
    assert "broken.json" in text
