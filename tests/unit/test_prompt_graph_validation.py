"""Tests for prompt graph production-readiness validation."""

from __future__ import annotations

from vscs.application.prompt_graph import (
    PromptEdge,
    PromptEdgeKind,
    PromptGraph,
    PromptGraphMetadata,
    PromptGraphResourceInventory,
    PromptGraphValidationPolicy,
    PromptGraphValidationSeverity,
    PromptGraphValidator,
    PromptNode,
    PromptNodeKind,
)


def _graph(*, include_continuity: bool = True) -> PromptGraph:
    nodes = [
        PromptNode("root", PromptNodeKind.ROOT, "Root", mandatory=True),
        PromptNode(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            "Iron Horizon enters Xorix orbit.",
            mandatory=True,
        ),
        PromptNode("camera", PromptNodeKind.CAMERA, "Camera", "Wide orbital view."),
        PromptNode(
            "lighting",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural sunlight from frame left.",
        ),
        PromptNode(
            "renderer",
            PromptNodeKind.RENDERER,
            "Renderer",
            "ComfyUI LTX 2.3.",
        ),
        PromptNode(
            "quality",
            PromptNodeKind.QUALITY,
            "Quality",
            "Production quality.",
        ),
        PromptNode(
            "ship",
            PromptNodeKind.SHIP,
            "Iron Horizon",
            "145-metre Guild survey vessel with four rear fusion engines.",
            canonical_asset_id="SHP-IRON-HORIZON",
            reference_ids=("REF-IRON-HORIZON",),
            mandatory=True,
        ),
    ]
    if include_continuity:
        nodes.append(
            PromptNode(
                "continuity",
                PromptNodeKind.CONTINUITY,
                "Continuity",
                "Match the approved previous end frame.",
            )
        )
    edges = tuple(
        PromptEdge(
            f"edge-{index}",
            "root",
            node.node_id,
            PromptEdgeKind.CONTAINS,
            sequence=index,
        )
        for index, node in enumerate(nodes[1:], start=1)
    )
    return PromptGraph(
        PromptGraphMetadata("GRAPH-001", "XORIX", "EP-001", "SCN-001", "SHT-001"),
        tuple(nodes),
        edges,
        "root",
    )


def _inventory() -> PromptGraphResourceInventory:
    return PromptGraphResourceInventory(
        canonical_asset_ids=frozenset({"SHP-IRON-HORIZON"}),
        reference_ids=frozenset({"REF-IRON-HORIZON"}),
    )


def test_complete_graph_is_production_ready() -> None:
    report = PromptGraphValidator().validate(_graph(), _inventory())

    assert report.passed
    assert report.completeness.percentage == 100
    assert report.completeness.production_ready
    assert report.issues == ()


def test_missing_required_kinds_and_mandatory_content_are_errors() -> None:
    graph = PromptGraph(
        PromptGraphMetadata("GRAPH-002", "XORIX", "EP-001", "SCN-001", "SHT-001"),
        (
            PromptNode("root", PromptNodeKind.ROOT, "Root", mandatory=True),
            PromptNode(
                "intent",
                PromptNodeKind.VISUAL_INTENT,
                "Intent",
                mandatory=True,
            ),
        ),
        (
            PromptEdge(
                "edge-1",
                "root",
                "intent",
                PromptEdgeKind.CONTAINS,
            ),
        ),
        "root",
    )

    report = PromptGraphValidator().validate(graph)
    codes = {issue.code for issue in report.issues}

    assert not report.passed
    assert not report.completeness.production_ready
    assert "graph.required_kind_missing" in codes
    assert "graph.mandatory_content_missing" in codes


def test_unresolved_canonical_resources_are_reported() -> None:
    report = PromptGraphValidator().validate(
        _graph(),
        PromptGraphResourceInventory(
            canonical_asset_ids=frozenset({"SHP-MAURITANIA"}),
            reference_ids=frozenset({"REF-MAURITANIA"}),
        ),
    )
    codes = {issue.code for issue in report.issues}

    assert not report.passed
    assert "graph.canonical_asset_unresolved" in codes
    assert "graph.reference_unresolved" in codes


def test_missing_continuity_blocks_reference_driven_graph() -> None:
    report = PromptGraphValidator().validate(
        _graph(include_continuity=False),
        _inventory(),
    )

    issue = next(
        item for item in report.issues if item.code == "graph.continuity_missing"
    )
    assert issue.severity is PromptGraphValidationSeverity.ERROR
    assert not report.passed


def test_dialogue_requires_spoken_content() -> None:
    graph = _graph()
    dialogue = PromptNode(
        "dialogue",
        PromptNodeKind.DIALOGUE,
        "James dialogue",
    )
    extended = PromptGraph(
        graph.metadata,
        (*graph.nodes, dialogue),
        (
            *graph.edges,
            PromptEdge(
                "edge-dialogue",
                "root",
                "dialogue",
                PromptEdgeKind.CONTAINS,
            ),
        ),
        graph.root_node_id,
    )

    report = PromptGraphValidator().validate(extended, _inventory())

    assert any(
        issue.code == "graph.dialogue_content_missing"
        for issue in report.issues
    )
    assert not report.passed


def test_policy_can_make_continuity_warning_only() -> None:
    validator = PromptGraphValidator(
        PromptGraphValidationPolicy(
            require_continuity_for_references=False,
            production_ready_threshold=90,
        )
    )
    report = validator.validate(_graph(include_continuity=False), _inventory())

    issue = next(
        item for item in report.issues if item.code == "graph.continuity_missing"
    )
    assert issue.severity is PromptGraphValidationSeverity.WARNING
    assert report.passed
    assert not report.completeness.production_ready


def test_cycle_is_detected_without_raising() -> None:
    graph = _graph()
    cyclic = PromptGraph(
        graph.metadata,
        graph.nodes,
        (
            *graph.edges,
            PromptEdge(
                "edge-cycle",
                "ship",
                "root",
                PromptEdgeKind.DEPENDS_ON,
            ),
        ),
        graph.root_node_id,
    )

    report = PromptGraphValidator().validate(cyclic, _inventory())

    assert any(issue.code == "graph.cycle" for issue in report.issues)
    assert not report.passed
