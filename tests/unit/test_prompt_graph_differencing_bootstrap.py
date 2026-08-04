"""Bootstrap tests for prompt graph snapshot and differencing services."""

from __future__ import annotations

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptGraphDiffer,
    PromptGraphSnapshotRegistry,
    PromptGraphSnapshotService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_snapshot_and_differencing_services(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.toml",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        registry = context.services.require(PromptGraphSnapshotRegistry)
        service = context.services.require(PromptGraphSnapshotService)
        differ = context.services.require(PromptGraphDiffer)

        assert service.registry is registry
        assert isinstance(differ, PromptGraphDiffer)
    finally:
        context.shutdown()
