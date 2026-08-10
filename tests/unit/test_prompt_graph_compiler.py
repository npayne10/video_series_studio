"""Tests for renderer-neutral prompt graph compilation."""

from __future__ import annotations

import pytest

from vscs.application.prompt_graph import (
    PromptEdge,
    PromptEdgeKind,
    PromptGraph,
    PromptGraphCompilationError,
    PromptGraphCompiler,
    PromptGraphMetadata,
    PromptGraphResourceInventory,
    PromptGraphValidationPolicy,
    PromptGraphValidator,
    PromptNode,
    PromptNodeKind,
    PromptSectionKind,
)


def _graph(*, include_negative: bool = True) -> PromptGraph:
    nodes = [
        PromptNode("root", PromptNodeKind.ROOT, "Root", mandatory=True),
        PromptNode(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Visual intent",
            "The Iron Horizon approaches Xorix in controlled orbital flight.",
            mandatory=True,
            sequence=1,
        ),
        PromptNode(
            "ship",
            PromptNodeKind.SHIP,
            "Iron Horizon",
            "The 145 metre Guild survey spacecraft has four rear fusion engines "
            "producing controlled blue-white engine trails.",
            canonical_asset_id="CAP-SHP-IRON-HORIZON",
            reference_ids=("REF-SHP-IRON-HORIZON-01",),
            mandatory=True,
            sequence=2,
        ),
        PromptNode(
            "camera",
            PromptNodeKind.CAMERA,
            "Camera",
            "Wide orbital tracking shot with restrained movement.",
            mandatory=True,
            sequence=3,
        ),
        PromptNode(
            "lighting",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural sunlight with physically accurate planetary bounce.",
            mandatory=True,
            sequence=4,
        ),
        PromptNode(
            "continuity",
            PromptNodeKind.CONTINUITY,
            "Continuity",
            "Maintain hull orientation and engine state from the previous shot.",
            mandatory=True,
            sequence=5,
        ),
        PromptNode(
            "renderer",
            PromptNodeKind.RENDERER,
            "Renderer",
            "Renderer-neutral cinematic video intent.",
            mandatory=True,
            sequence=6,
        ),
        PromptNode(
            "quality",
            PromptNodeKind.QUALITY,
            "Quality",
            "Production quality at 24 fps.",
            mandatory=True,
            sequence=7,
        ),
    ]
    if include_negative:
        nodes.extend(
            (
                PromptNode(
                    "restriction",
                    PromptNodeKind.RESTRICTION,
                    "Restriction",
                    "No side-mounted engines and no uncontrolled fireball.",
                    sequence=8,
                ),
                PromptNode(
                    "negative",
                    PromptNodeKind.NEGATIVE,
                    "Negative",
                    "No fantasy architecture, excessive glow or visual clutter.",
                    sequence=9,
                ),
            )
        )
    edges = tuple(
        PromptEdge(
            f"edge-{index}",
            "root",
            node.node_id,
            PromptEdgeKind.CONTAINS,
            sequence=node.sequence,
        )
        for index, node in enumerate(nodes[1:], start=1)
    )
    return PromptGraph(
        PromptGraphMetadata(
            "GRAPH-001",
            "XORIX",
            "EP-001",
            "SCN-001",
            "SHT-001",
        ),
        tuple(nodes),
        edges,
        "root",
    )


def _inventory() -> PromptGraphResourceInventory:
    return PromptGraphResourceInventory(
        canonical_asset_ids=frozenset({"CAP-SHP-IRON-HORIZON"}),
        reference_ids=frozenset({"REF-SHP-IRON-HORIZON-01"}),
    )


def test_compiler_creates_deterministic_structured_package() -> None:
    package = PromptGraphCompiler(PromptGraphValidator()).compile(
        _graph(),
        _inventory(),
    )

    assert package.package_id == "GRAPH-001:prompt"
    assert tuple(section.kind for section in package.sections) == (
        PromptSectionKind.VISUAL_INTENT,
        PromptSectionKind.ENVIRONMENT,
        PromptSectionKind.CAMERA,
        PromptSectionKind.LIGHTING,
        PromptSectionKind.CONTINUITY,
        PromptSectionKind.QUALITY,
        PromptSectionKind.RESTRICTIONS,
        PromptSectionKind.NEGATIVE,
        PromptSectionKind.RENDERER,
    )
    assert "145 metre Guild survey spacecraft" in package.positive_prompt
    assert "controlled blue-white engine trails" in package.positive_prompt
    assert "No side-mounted engines" not in package.positive_prompt
    assert "No side-mounted engines" in package.negative_prompt
    assert "No fantasy architecture" in package.negative_prompt


def test_compiler_preserves_assets_references_and_provenance() -> None:
    graph = _graph()
    package = PromptGraphCompiler(PromptGraphValidator()).compile(
        graph,
        _inventory(),
    )

    assert package.canonical_asset_ids == ("CAP-SHP-IRON-HORIZON",)
    assert package.reference_ids == ("REF-SHP-IRON-HORIZON-01",)
    assert package.provenance.graph_id == graph.metadata.graph_id
    assert package.provenance.shot_id == graph.metadata.shot_id
    assert len(package.provenance.graph_checksum) == 64
    environment = package.section(PromptSectionKind.ENVIRONMENT)
    assert environment is not None
    assert environment.fragments[0].canonical_asset_id == "CAP-SHP-IRON-HORIZON"


def test_compiler_rejects_validation_errors() -> None:
    graph = _graph()
    broken = PromptGraph(
        graph.metadata,
        tuple(node for node in graph.nodes if node.kind is not PromptNodeKind.CAMERA),
        tuple(edge for edge in graph.edges if edge.target_id != "camera"),
        graph.root_node_id,
    )

    with pytest.raises(PromptGraphCompilationError, match="validation issues"):
        PromptGraphCompiler(PromptGraphValidator()).compile(broken, _inventory())


def test_compiler_can_allow_valid_non_production_ready_preview() -> None:
    graph = _graph()
    preview_graph = PromptGraph(
        graph.metadata,
        tuple(node for node in graph.nodes if node.kind is not PromptNodeKind.CONTINUITY),
        tuple(edge for edge in graph.edges if edge.target_id != "continuity"),
        graph.root_node_id,
    )
    validator = PromptGraphValidator(
        PromptGraphValidationPolicy(
            require_continuity_for_references=False,
            production_ready_threshold=100,
        )
    )
    compiler = PromptGraphCompiler(validator)

    with pytest.raises(PromptGraphCompilationError, match="readiness threshold"):
        compiler.compile(preview_graph, _inventory())

    package = compiler.compile(
        preview_graph,
        _inventory(),
        require_production_ready=False,
    )
    assert package.validation.passed
    assert not package.validation.completeness.production_ready
