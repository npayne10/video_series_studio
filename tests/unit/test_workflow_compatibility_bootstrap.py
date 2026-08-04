"""Bootstrap coverage for workflow compatibility validation."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import WorkflowCompatibilityValidator
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_workflow_compatibility_validator(
    tmp_path: Path,
) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )

    assert isinstance(
        context.services.require(WorkflowCompatibilityValidator),
        WorkflowCompatibilityValidator,
    )
    context.shutdown()
