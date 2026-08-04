"""Tests for prompt graph builder dependency registration."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptGraphBuilder,
    PromptGraphDiagnosticsFactory,
    PromptGraphResolver,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_prompt_graph_builder_services(tmp_path: Path) -> None:
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

    resolver = context.services.require(PromptGraphResolver)
    diagnostics = context.services.require(PromptGraphDiagnosticsFactory)
    builder = context.services.require(PromptGraphBuilder)

    assert builder.resolver is resolver
    assert builder.diagnostics_factory is diagnostics
    context.shutdown()
