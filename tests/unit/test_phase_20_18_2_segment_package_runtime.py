from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from vscs.infrastructure.production_execution.segment_package_runtime import (
    SegmentPackageMaterializer,
)


def _parent(tmp_path: Path) -> dict:
    helper = tmp_path / "helper.png"
    helper.write_bytes(b"provider-helper")
    checksum = hashlib.sha256(helper.read_bytes()).hexdigest()
    return {
        "schema_version": "7.2.1-vscs-1",
        "frame_count": 528,
        "frames_per_second": 24,
        "seed": 1000,
        "acpp": {
            "timing": {"frames": 528, "fps": 24},
            "generation": {"seed": 1000},
            "output": {"filename_prefix": "VSCS/EP-001/PT-TEST"},
        },
        "reference_plan": {
            "bindings": [
                {
                    "reference_id": "REF-JAMES",
                    "role": "primary_identity",
                    "path": str(tmp_path / "james.png"),
                    "required": True,
                },
                {
                    "reference_id": "HELPER-001",
                    "role": "scene_composition_anchor",
                    "path": str(helper),
                    "required": True,
                    "provider_ready": True,
                    "file_checksum": checksum,
                    "reference_fingerprint": checksum,
                    "derivative_type": "provider_specific_helper",
                },
            ],
            "provider_helper": {"status": "generated"},
        },
        "provider_execution_plan": {
            "mode": "segmented",
            "governed_frame_count": 528,
            "frames_per_second": 24,
            "segments": [],
        },
        "_vscs_manifest": {"package_fingerprint": "parent-fingerprint"},
    }


def _segment(index: int, segment_id: str, seed: int) -> dict[str, object]:
    start = (index - 1) * 176
    return {
        "segment_id": segment_id,
        "index": index,
        "start_frame": start,
        "end_frame": start + 175,
        "frame_count": 176,
        "seed": seed,
        "continuity_input": (
            "governed_initial_reference" if index == 1 else "previous_segment_final_frame"
        ),
    }


def test_segment_package_narrows_provider_runtime_without_mutating_parent(tmp_path: Path) -> None:
    parent = _parent(tmp_path)
    original = copy.deepcopy(parent)
    materializer = SegmentPackageMaterializer(tmp_path)

    path = materializer.materialize(
        parent=parent,
        task_id="PT-TEST",
        segment=_segment(1, "SEG-001", 1000),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert parent == original
    assert payload["frame_count"] == 176
    assert payload["acpp"]["timing"]["frames"] == 176
    assert payload["seed"] == 1000
    assert payload["acpp"]["generation"]["seed"] == 1000
    assert payload["provider_segment"]["parent_package_fingerprint"] == "parent-fingerprint"
    assert payload["_vscs_manifest"]["parent_package_fingerprint"] == "parent-fingerprint"
    assert payload["_vscs_manifest"]["package_fingerprint"] != "parent-fingerprint"
    assert "SEG-001" in path.name


def test_next_segment_rebinds_only_provider_helper_to_previous_final_frame(tmp_path: Path) -> None:
    parent = _parent(tmp_path)
    original = copy.deepcopy(parent)
    final_frame = tmp_path / "seg-001-final.png"
    final_frame.write_bytes(b"final-frame")
    materializer = SegmentPackageMaterializer(tmp_path)

    path = materializer.materialize(
        parent=parent,
        task_id="PT-TEST",
        segment=_segment(2, "SEG-002", 1001),
        continuity_input_path=str(final_frame),
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    bindings = payload["reference_plan"]["bindings"]
    identity = next(item for item in bindings if item["role"] == "primary_identity")
    helper = next(item for item in bindings if item["role"] == "scene_composition_anchor")

    assert parent == original
    assert identity == original["reference_plan"]["bindings"][0]
    assert helper["path"] == str(final_frame.resolve(strict=False))
    assert helper["segment_continuity"] is True
    assert helper["source_provider_helper_reference_id"] == "HELPER-001"
    assert payload["reference_plan"]["provider_helper"]["status"] == "segment_continuity"


def test_different_continuity_frames_create_immutable_distinct_packages(tmp_path: Path) -> None:
    parent = _parent(tmp_path)
    materializer = SegmentPackageMaterializer(tmp_path)
    first = tmp_path / "continuity-a.png"
    second = tmp_path / "continuity-b.png"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    first_path = materializer.materialize(
        parent=parent,
        task_id="PT-TEST",
        segment=_segment(2, "SEG-002", 1001),
        continuity_input_path=str(first),
    )
    second_path = materializer.materialize(
        parent=parent,
        task_id="PT-TEST",
        segment=_segment(2, "SEG-002", 1001),
        continuity_input_path=str(second),
    )

    assert first_path != second_path
    assert first_path.is_file()
    assert second_path.is_file()
