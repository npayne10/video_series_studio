"""Tests for persistent batch recovery checkpoints."""

from pathlib import Path

import pytest

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
            reference_ids=frozenset({"REF-SHP-IRON-HORIZON"}),
        ),
        dependencies=(
            CompilationDependency(
                CompilationDependencyKind.CANONICAL_ASSET,
                "CAP-SHP-IRON-HORIZON",
                "checksum-v1",
            ),
        ),
    )


def _request(
    batch_id: str = "BATCH-RECOVERY",
    shot_ids: tuple[str, ...] = ("SHT-001", "SHT-002"),
) -> BatchCompilationRequest:
    return BatchCompilationRequest.create(
        batch_id,
        tuple(
            _item(f"ITEM-{index:03d}", shot_id)
            for index, shot_id in enumerate(shot_ids, start=1)
        ),
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
    inventory = checkpoint.request.items[0].inventory

    assert checkpoint.request.items[0].dependencies[0].checksum == "checksum-v1"
    assert inventory.canonical_asset_ids == frozenset({"CAP-SHP-IRON-HORIZON"})
    assert inventory.reference_ids == frozenset({"REF-SHP-IRON-HORIZON"})
    assert checkpoint.status_for("ITEM-001") is BatchCompilationItemStatus.COMPLETED


def test_resource_inventory_serialization_is_deterministic() -> None:
    inventory = PromptGraphResourceInventory(
        canonical_asset_ids=frozenset({"CAP-002", "CAP-001"}),
        reference_ids=frozenset({"REF-002", "REF-001"}),
    )

    serialized = inventory.to_dict()
    restored = PromptGraphResourceInventory.from_dict(serialized)

    assert serialized == {
        "canonical_asset_ids": ["CAP-001", "CAP-002"],
        "reference_ids": ["REF-001", "REF-002"],
    }
    assert restored == inventory


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


def test_completed_checkpoint_can_be_replaced_for_reused_batch_id(
    tmp_path: Path,
) -> None:
    service = BatchRecoveryService(BatchRecoveryStore(tmp_path / "recovery.json"))
    original = _request()
    service.begin(original)
    for item in original.items:
        service.record_result(
            original.batch_id,
            BatchCompilationItemResult(
                item.item_id,
                item.context.shot_id,
                BatchCompilationItemStatus.COMPLETED,
            ),
        )

    replacement = _request(shot_ids=("SHT-003",))
    checkpoint = service.begin(replacement)

    assert checkpoint.request == replacement
    assert checkpoint.item_statuses == ()


def test_incomplete_checkpoint_rejects_changed_request(tmp_path: Path) -> None:
    service = BatchRecoveryService(BatchRecoveryStore(tmp_path / "recovery.json"))
    service.begin(_request())

    with pytest.raises(ValueError, match="Recovery request changed"):
        service.begin(_request(shot_ids=("SHT-003",)))
