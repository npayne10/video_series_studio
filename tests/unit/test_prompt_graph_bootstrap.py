"""Tests for prompt graph core dependency registration."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptGraphRegistry,
    PromptGraphSnapshotRegistry,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_prompt_graph_core(tmp_path: Path) -> None:
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

    graphs = context.services.require(PromptGraphRegistry)
    snapshots = context.services.require(PromptGraphSnapshotRegistry)

    assert graphs.list() == ()
    assert snapshots.list_for_graph("PG-001") == ()

    context.shutdown()
