from __future__ import annotations

from vscs.application.production_pipeline import ProductionNode, ProductionStage
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskGovernanceService,
    ProductionTaskState,
    ProductionTaskType,
)


def test_vnext_task_authority_coexists_with_legacy_pipeline_without_dependency() -> None:
    legacy_node = ProductionNode(node_id="legacy-render", stage=ProductionStage.RENDERING)
    task = ProductionTask(
        task_id="task-SH001-video",
        production_id="production-EP01",
        episode_id="EP01",
        scene_id="SC01",
        shot_id="SH001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="upd-SH001",
            revision=1,
            fingerprint="fingerprint-SH001-v1",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
    )

    result = ProductionTaskGovernanceService().validate(task)

    assert result.valid
    assert task.state is ProductionTaskState.PLANNED
    assert task.task_id != legacy_node.node_id
    assert not hasattr(task, "stage")
    assert not hasattr(task, "clip_id")


def test_task_authority_contains_no_renderer_or_workflow_contract() -> None:
    fields = set(ProductionTask.__dataclass_fields__)

    assert "provider" not in fields
    assert "renderer" not in fields
    assert "workflow" not in fields
    assert "node_id" not in fields
    assert "endpoint" not in fields
