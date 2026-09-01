from __future__ import annotations

from pathlib import Path

from vscs.infrastructure.production_execution.segment_execution_runtime import (
    SegmentExecutionStore,
)


def _segments() -> list[dict[str, object]]:
    return [
        {
            "segment_id": "SEG-001",
            "index": 1,
            "frame_count": 176,
            "start_frame": 0,
            "end_frame": 175,
            "seed": 1001,
        },
        {
            "segment_id": "SEG-002",
            "index": 2,
            "frame_count": 176,
            "start_frame": 176,
            "end_frame": 351,
            "seed": 1002,
        },
    ]


def test_segment_execution_store_initializes_durable_records(tmp_path: Path) -> None:
    store = SegmentExecutionStore(tmp_path)
    records = store.initialize(
        task_id="PT-TEST",
        package_fingerprint="package-fingerprint",
        segments=_segments(),
    )

    assert [record.segment_id for record in records] == ["SEG-001", "SEG-002"]
    assert all(record.state == "PLANNED" for record in records)
    assert store.list_for_package("PT-TEST", "package-fingerprint") == records


def test_segment_execution_store_reuses_existing_history(tmp_path: Path) -> None:
    store = SegmentExecutionStore(tmp_path)
    records = store.initialize(
        task_id="PT-TEST",
        package_fingerprint="package-fingerprint",
        segments=_segments(),
    )
    first = records[0].with_state(
        "COMPLETED",
        provider_execution_id="PE-001",
        output_path="segment-1.mp4",
        final_frame_path="segment-1-final.png",
    )
    store.save(first)

    reloaded = store.initialize(
        task_id="PT-TEST",
        package_fingerprint="package-fingerprint",
        segments=_segments(),
    )

    assert reloaded[0].state == "COMPLETED"
    assert reloaded[0].output_path == "segment-1.mp4"
    assert reloaded[1].state == "PLANNED"
