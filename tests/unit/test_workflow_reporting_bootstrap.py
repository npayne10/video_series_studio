"""Bootstrap coverage for workflow diagnostics reporting."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import WorkflowDiagnosticsFormatter
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_workflow_diagnostics_formatter(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "config.yaml",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        formatter = context.services.require(WorkflowDiagnosticsFormatter)
        assert isinstance(formatter, WorkflowDiagnosticsFormatter)
    finally:
        context.shutdown()
