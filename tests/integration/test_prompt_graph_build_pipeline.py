"""Integration test for the Phase 17.4.1.2 graph build pipeline."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_builder_assembles_canonical_and_continuity_sources(
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
    resolver = context.services.require(PromptGraphResolver)
    resolver.register(
        "SHT-001",
        (
            PromptGraphSource(
                "ship",
                PromptNodeKind.SHIP,
                "Iron Horizon",
                "145-metre Guild survey vessel with four rear fusion engines.",
                canonical_asset_id="SHP-IRON-HORIZON",
                reference_ids=("REF-IRON-HORIZON",),
                mandatory=True,
                sequence=10,
            ),
            PromptGraphSource(
                "continuity",
                PromptNodeKind.CONTINUITY,
                "Previous approved frame",
                "Preserve hull orientation and blue-white engine trails.",
                reference_ids=("FRAME-PREVIOUS",),
                sequence=20,
            ),
        ),
    )
    result = context.services.require(PromptGraphBuilder).build(
        PromptGraphBuildContext(
            "GRAPH-001",
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
            workflow_id="ltx23_production_v1",
        )
    )

    assert result.report.passed
    assert result.graph.require_node("ship").canonical_asset_id == "SHP-IRON-HORIZON"
    assert result.graph.require_node("continuity").reference_ids == ("FRAME-PREVIOUS",)
    context.shutdown()
