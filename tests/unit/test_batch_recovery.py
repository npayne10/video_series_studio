"""Tests for persistent batch recovery checkpoints."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
    BatchRecoveryService,
    BatchRecoveryStore,
    CompilationDependency,
    CompilationDependencyKind,
    PromptGraphBuildContext,
    PromptGraphResourceInventory,
)
from vscs.application.rendering import QualityLevel, RendererKind


def _item(item_id: str, shot_id: str) -> BatchCompilationItem:
    return BatchCompilationItem(
        item_id=item_id,
        context=PromptGraphBuildContext(
            graph_id=f"GRAPH-{shot_id}",
            production_id="XORIX",
            container_id="EP-001",
            scene_id="SCN-001",
            shot_id=shot_id,
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PRODUCTION,
            workflow_id="ltx23_production_v1",
        ),
        inventory=PromptGraphResourceInventory(
            canonical_asset_ids=frozenset({"CAP-SHP-IRON-HORIZON"}),
            approved_reference_ids=frozenset({"REF-SHP-IRON-HORIZON"}),
        ),
        dependencies=(
            CompilationDependency(
                CompilationDependencyKind.CANONICAL_ASSET,
                "CAP-SHP-IRON-HORIZON",
                "checksum-v1",
            ),
        ),
    )


def _request() -> BatchCompilationRequest:
    return BatchCompilationRequest.create(
        "BATCH-RECOVERY",
        (_item("ITEM-001", "SHT-001"), _item("ITEM-002", "SHT-002")),
    )


def test_recovery_store_round_trips_complete_request(tmp_path: Path) -> None:
    path = tmp_path / "recovery.json"
    service = BatchRecoveryService(BatchRecoveryStore(path))
    service.begin(_request())
    service.record_result(
        "BATCH-RECOVERY",
        BatchCompilationItemResult(
            "ITEM-001",
            "SHT-001",
            BatchCompilationItemStatus.COMPLETED,
        ),
    )

    restored = BatchRecoveryService(BatchRecoveryStore(path))
    checkpoint = restored.require("BATCH-RECOVERY")

    assert checkpoint.request.items[0].dependencies[0].checksum == "checksum-v1"
    assert checkpoint.request.items[0].inventory.canonical_asset_ids == frozenset(
        {"CAP-SHP-IRON-HORIZON"}
    )
    assert checkpoint.status_for("ITEM-001") is BatchCompilationItemStatus.COMPLETED


def test_resume_excludes_successful_items_and_can_retry_failures(tmp_path: Path) -> None:
    service = BatchRecoveryService(BatchRecoveryStore(tmp_path / "recovery.json"))
    service.begin(_request())
    service.record_result(
        "BATCH-RECOVERY",
        BatchCompilationItemResult(
            "ITEM-001",
            "SHT-001",
            BatchCompilationItemStatus.COMPLETED,
        ),
    )
    service.record_result(
        "BATCH-RECOVERY",
        BatchCompilationItemResult(
            "ITEM-002",
            "SHT-002",
            BatchCompilationItemStatus.FAILED,
        ),
    )

    retry = service.resumable_request("BATCH-RECOVERY", retry_failed=True)
    no_retry = service.resumable_request("BATCH-RECOVERY", retry_failed=False)

    assert retry is not None
    assert tuple(item.item_id for item in retry.items) == ("ITEM-002",)
    assert no_retry is None


def test_completed_checkpoint_is_not_pending(tmp_path: Path) -> None:
    service = BatchRecoveryService(BatchRecoveryStore(tmp_path / "recovery.json"))
    service.begin(_request())
    for item_id, shot_id in (("ITEM-001", "SHT-001"), ("ITEM-002", "SHT-002")):
        service.record_result(
            "BATCH-RECOVERY",
            BatchCompilationItemResult(
                item_id,
                shot_id,
                BatchCompilationItemStatus.SKIPPED,
            ),
        )

    assert service.pending_checkpoints() == ()
