"""Tests for workflow manifest services in the dependency graph."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import WorkflowRegistry
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_workflow_registry_is_registered_empty(
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

    registry = context.services.require(WorkflowRegistry)
    assert registry.list() == ()

    context.shutdown()
