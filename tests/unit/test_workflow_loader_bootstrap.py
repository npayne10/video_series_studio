"""Tests for workflow manifest loader bootstrap integration."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import (
    ManifestDiscoveryResult,
    WorkflowManifestLoader,
    WorkflowRegistry,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_manifest_loader_and_discovery_result(
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

    loader = context.services.require(WorkflowManifestLoader)
    registry = context.services.require(WorkflowRegistry)
    result = context.services.require(ManifestDiscoveryResult)

    assert loader.root == (
        context.configuration.settings.environment.config_root / "workflows" / "manifests"
    ).resolve(strict=False)
    assert len(registry) == 0
    assert result.discovered_files == 0

    context.shutdown()
