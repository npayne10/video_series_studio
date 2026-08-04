"""Tests for deterministic prompt graph construction."""

from vscs.application.prompt_graph import (
    PromptEdgeKind,
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphDiagnosticSeverity,
    PromptGraphDiagnosticsFactory,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)


def _context() -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        graph_id="GRAPH-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        workflow_id="ltx23_preview_v1",
    )


def test_builder_expands_registered_sources_deterministically() -> None:
    resolver = PromptGraphResolver()
    resolver.register(
        "SHT-001",
        (
            PromptGraphSource(
                source_id="ship",
                kind=PromptNodeKind.SHIP,
                label="Iron Horizon",
                content="145-metre Guild survey vessel",
                canonical_asset_id="SHP-IRON-HORIZON",
                reference_ids=("REF-EXT",),
                attributes=(("engine_trail", "blue-white"),),
                mandatory=True,
                sequence=20,
            ),
            PromptGraphSource(
                source_id="intent",
                kind=PromptNodeKind.VISUAL_INTENT,
                label="Orbital arrival",
                content="The vessel crosses Xorix orbit.",
                sequence=10,
            ),
            PromptGraphSource(
                source_id="effect",
                kind=PromptNodeKind.EFFECT,
                label="Fusion exhaust",
                content="Four controlled blue-white engine trails.",
                parent_source_id="ship",
                relationship=PromptEdgeKind.DESCRIBES,
                sequence=30,
            ),
        ),
    )
    result = PromptGraphBuilder(
        resolver,
        PromptGraphDiagnosticsFactory(),
    ).build(_context())

    assert result.report.passed
    assert result.report.nodes_created == 4
    assert result.graph.require_node("ship").canonical_asset_id == "SHP-IRON-HORIZON"
    assert result.graph.require_node("ship").attribute("engine_trail") == "blue-white"
    assert result.graph.incoming("effect")[0].source_id == "ship"
    assert tuple(node.node_id for node in result.graph.topological_nodes()) == (
        "root",
        "intent",
        "ship",
        "effect",
    )


def test_builder_falls_back_to_root_for_missing_parent() -> None:
    resolver = PromptGraphResolver()
    resolver.register(
        "SHT-001",
        (
            PromptGraphSource(
                source_id="prop",
                kind=PromptNodeKind.PROP,
                label="Command tablet",
                parent_source_id="missing-character",
            ),
        ),
    )
    result = PromptGraphBuilder(
        resolver,
        PromptGraphDiagnosticsFactory(),
    ).build(_context())

    assert result.graph.incoming("prop")[0].source_id == "root"
    assert result.report.diagnostics[0].severity is PromptGraphDiagnosticSeverity.WARNING
    assert result.report.diagnostics[0].code == "builder.parent_missing"
