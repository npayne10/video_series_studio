"""Tests for the Phase 14.1 production pipeline foundation."""

from dataclasses import replace

import pytest

from vscs.application.production_pipeline import (
    ProductionGraph,
    ProductionGraphError,
    ProductionNode,
    ProductionPipeline,
    ProductionPipelineSerializer,
    ProductionPipelineValidator,
    ProductionStage,
    ProductionState,
)


def _pipeline() -> ProductionPipeline:
    return ProductionPipeline(
        pipeline_id="PIPE-PROD-XORIX-EP001",
        production_id="PROD-XORIX",
        episode_id="EP-001",
        nodes=(
            ProductionNode("story", ProductionStage.STORY, ProductionState.COMPLETED),
            ProductionNode(
                "ssie",
                ProductionStage.SSIE,
                ProductionState.COMPLETED,
                dependencies=("story",),
            ),
            ProductionNode(
                "acpp",
                ProductionStage.ACPP,
                dependencies=("ssie",),
            ),
            ProductionNode(
                "render",
                ProductionStage.RENDERING,
                clip_id="CLIP-001",
                dependencies=("acpp",),
            ),
        ),
    )


def test_pipeline_validates_and_orders_dependencies() -> None:
    pipeline = _pipeline()

    result = ProductionPipelineValidator().validate(pipeline)
    ordered = ProductionGraph(pipeline).topological_order()

    assert result.passed is True
    assert [node.node_id for node in ordered] == ["story", "ssie", "acpp", "render"]


def test_graph_reports_ready_nodes() -> None:
    ready = ProductionGraph(_pipeline()).ready_nodes()

    assert tuple(node.node_id for node in ready) == ("acpp",)


def test_graph_reports_nodes_blocked_by_failure() -> None:
    pipeline = _pipeline()
    failed_acpp = replace(pipeline.nodes[2], state=ProductionState.FAILED)
    pipeline = replace(pipeline, nodes=(*pipeline.nodes[:2], failed_acpp, pipeline.nodes[3]))

    blocked = ProductionGraph(pipeline).blocked_nodes()

    assert tuple(node.node_id for node in blocked) == ("render",)


def test_validator_rejects_unknown_dependencies_and_cycles() -> None:
    unknown = replace(
        _pipeline(),
        nodes=(ProductionNode("node", ProductionStage.STORY, dependencies=("missing",)),),
    )
    cyclic = replace(
        _pipeline(),
        nodes=(
            ProductionNode("one", ProductionStage.STORY, dependencies=("two",)),
            ProductionNode("two", ProductionStage.SSIE, dependencies=("one",)),
        ),
    )

    assert ProductionPipelineValidator().validate(unknown).passed is False
    assert ProductionPipelineValidator().validate(cyclic).passed is False
    with pytest.raises(ProductionGraphError):
        ProductionGraph(cyclic).topological_order()


def test_pipeline_serialization_round_trip_is_stable() -> None:
    serializer = ProductionPipelineSerializer()
    pipeline = _pipeline()

    payload = serializer.dumps(pipeline)
    restored = serializer.loads(payload)

    assert restored == pipeline
    assert serializer.checksum(restored) == serializer.checksum(pipeline)


def test_pipeline_queries_nodes_by_identity_and_stage() -> None:
    pipeline = _pipeline()

    assert pipeline.node("acpp") == pipeline.nodes[2]
    assert pipeline.node("missing") is None
    assert pipeline.nodes_for_stage(ProductionStage.RENDERING) == (pipeline.nodes[3],)
