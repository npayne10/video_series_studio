"""Integration coverage for build, snapshot and graph differencing."""

from __future__ import annotations

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphChangeArea,
    PromptGraphDiffer,
    PromptGraphResolver,
    PromptGraphSnapshotRegistry,
    PromptGraphSnapshotService,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_built_graph_versions_can_be_snapshotted_and_compared(tmp_path) -> None:  # type: ignore[no-untyped-def]
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
        resolver = context.services.require(PromptGraphResolver)
        builder = context.services.require(PromptGraphBuilder)
        snapshots = context.services.require(PromptGraphSnapshotService)
        differ = context.services.require(PromptGraphDiffer)
        context_data = PromptGraphBuildContext(
            "GRAPH-001",
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PREVIEW,
            workflow_id="ltx23_preview_v1",
        )
        resolver.register(
            "SHT-001",
            (
                PromptGraphSource(
                    "continuity",
                    PromptNodeKind.CONTINUITY,
                    "Continuity",
                    "Maintain hull orientation.",
                    sequence=1,
                ),
            ),
        )
        first = snapshots.capture(builder.build(context_data).graph, snapshot_id="SNAP-001")
        resolver.register(
            "SHT-001",
            (
                PromptGraphSource(
                    "continuity",
                    PromptNodeKind.CONTINUITY,
                    "Continuity",
                    "Maintain hull orientation and blue-white engine trails.",
                    sequence=1,
                ),
            ),
        )
        second = snapshots.capture(builder.build(context_data).graph, snapshot_id="SNAP-002")

        diff = differ.compare_snapshots(first, second)

        assert snapshots.history("GRAPH-001") == (first, second)
        assert any(
            change.area is PromptGraphChangeArea.NODE
            and change.subject == "continuity"
            and change.continuity_sensitive
            for change in diff.changes
        )
        assert context.services.require(PromptGraphSnapshotRegistry) is snapshots.registry
    finally:
        context.shutdown()
