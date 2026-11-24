"""Stage B.2 offline-only multiple-angle qualification contract."""

import json
from pathlib import Path

from vscs.application.caps.qwen_multi_angle_qualification import (
    inspect_multiple_angle_capability,
)


def test_missing_evidence_blocks_generation(tmp_path: Path) -> None:
    report = inspect_multiple_angle_capability(
        workflow_path=None, object_info_path=None, model_root=tmp_path
    )
    assert not report.generation_authorized
    assert not report.multiple_angles_lora_present
    assert any("workflow" in reason for reason in report.blockers)
    assert any("LoRA" in reason for reason in report.blockers)


def test_offline_audit_identifies_nodes_models_and_remaining_qualification(tmp_path: Path) -> None:
    workflow = tmp_path / "angles.json"
    workflow.write_text(
        json.dumps(
            {
                "1": {"class_type": "ComposeCameraAnglePrompt", "inputs": {}},
                "2": {"class_type": "LoraLoaderModelOnly", "inputs": {}},
                "3": {"class_type": "SaveImage", "inputs": {}},
            }
        ),
        encoding="utf-8",
    )
    object_info = tmp_path / "object_info.json"
    object_info.write_text(
        json.dumps({"ComposeCameraAnglePrompt": {}, "LoraLoaderModelOnly": {}, "SaveImage": {}}),
        encoding="utf-8",
    )
    model_root = tmp_path / "models"
    model_root.mkdir()
    (model_root / "qwen_image_edit_2511_fp8mixed.safetensors").touch()
    (model_root / "qwen-image-edit-2511-multiple-angles-lora.safetensors").touch()

    report = inspect_multiple_angle_capability(
        workflow_path=workflow, object_info_path=object_info, model_root=model_root
    )
    assert report.workflow_sha256 is not None
    assert report.identified_angle_nodes == ("1",)
    assert report.model_file_present and report.multiple_angles_lora_present
    assert report.missing_node_types == ()
    assert not report.generation_authorized
    assert any("GPU fit" in reason for reason in report.blockers)


def test_missing_camera_node_and_unavailable_node_fail_closed(tmp_path: Path) -> None:
    workflow = tmp_path / "inadequate.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {}}}),
        encoding="utf-8",
    )
    inventory = tmp_path / "nodes.json"
    inventory.write_text("{}", encoding="utf-8")
    report = inspect_multiple_angle_capability(
        workflow_path=workflow, object_info_path=inventory, model_root=tmp_path
    )
    assert not report.generation_authorized
    assert any("camera-angle" in reason for reason in report.blockers)
    assert report.missing_node_types == ("TextEncodeQwenImageEditPlus",)
