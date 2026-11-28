"""Offline-only qualification of a proposed Qwen multiple-angle ComfyUI graph.

No ComfyUI network requests, workflow execution, model downloads or project writes.
An audit finding is never generation authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MultipleAngleQualification:
    workflow_sha256: str | None
    identified_angle_nodes: tuple[str, ...]
    model_file_present: bool
    multiple_angles_lora_present: bool
    missing_node_types: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def generation_authorized(self) -> bool:
        """The offline audit cannot authorise production or GPU generation."""
        return False


def inspect_multiple_angle_capability(
    *,
    workflow_path: Path | None,
    object_info_path: Path | None,
    model_root: Path | None,
) -> MultipleAngleQualification:
    """Inspect explicitly supplied evidence; absent input is a blocker, not a pass."""
    blockers: list[str] = []
    workflow_sha256: str | None = None
    angle_nodes: tuple[str, ...] = ()
    required_types: set[str] = set()
    workflow: dict[str, Any] | None = None

    if workflow_path is None or not workflow_path.is_file():
        blockers.append("Supply a reviewed, locally exported multiple-angle API workflow JSON")
    else:
        data = workflow_path.read_bytes()
        workflow_sha256 = hashlib.sha256(data).hexdigest()
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict) or not parsed:
            blockers.append("Workflow must be a nonempty ComfyUI API-format JSON object")
        elif not all(
            isinstance(node, dict) and isinstance(node.get("class_type"), str)
            for node in parsed.values()
        ):
            blockers.append("Workflow contains nodes without API class_type declarations")
        else:
            workflow = parsed
            required_types = {node["class_type"] for node in parsed.values()}
            angle_nodes = tuple(
                sorted(
                    node_id
                    for node_id, node in parsed.items()
                    if "camera" in node["class_type"].lower()
                    and "angle" in node["class_type"].lower()
                )
            )
            if not angle_nodes:
                blockers.append("No explicit camera-angle composition node found in the API graph")
            if not any("LoraLoader" in node_type for node_type in required_types):
                blockers.append("No LoRA loader found in the proposed multiple-angle graph")
            if not any("Save" in node_type for node_type in required_types):
                blockers.append("No output saver found in the proposed multiple-angle graph")

    available_types: set[str] = set()
    inventory_available = False
    if object_info_path is None or not object_info_path.is_file():
        blockers.append("Supply a saved read-only ComfyUI /object_info inventory")
    else:
        try:
            object_info = json.loads(object_info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            object_info = None
        if not isinstance(object_info, dict):
            blockers.append("ComfyUI object_info snapshot is not a JSON object")
        else:
            inventory_available = True
            available_types = set(object_info)

    missing = tuple(sorted(required_types - available_types)) if inventory_available else ()
    if missing:
        blockers.append("Workflow requires unavailable ComfyUI node types")

    model_present = False
    lora_present = False
    if model_root is None or not model_root.is_dir():
        blockers.append("Supply the local ComfyUI models directory for read-only inventory")
    else:
        model_present = any(
            path.is_file() for path in model_root.rglob("*qwen_image_edit_2511*.safetensors")
        )
        lora_present = any(
            path.is_file() for path in model_root.rglob("*multiple*angles*lora*.safetensors")
        )
        if not model_present:
            blockers.append("Qwen Image Edit 2511 checkpoint not found in model inventory")
        if not lora_present:
            blockers.append("Multiple-angles LoRA not found in model inventory")

    if workflow is not None:
        # A camera graph and model presence do not establish identity fidelity or VRAM fit.
        blockers.append(
            "GPU fit and canonical identity still require isolated operator qualification"
        )
    return MultipleAngleQualification(
        workflow_sha256=workflow_sha256,
        identified_angle_nodes=angle_nodes,
        model_file_present=model_present,
        multiple_angles_lora_present=lora_present,
        missing_node_types=missing,
        blockers=tuple(blockers),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Qwen multiple-angle qualification")
    parser.add_argument("--workflow", type=Path)
    parser.add_argument("--object-info", type=Path)
    parser.add_argument("--model-root", type=Path)
    args = parser.parse_args()
    report = inspect_multiple_angle_capability(
        workflow_path=args.workflow,
        object_info_path=args.object_info,
        model_root=args.model_root,
    )
    print(
        json.dumps(
            {
                "workflow_sha256": report.workflow_sha256,
                "camera_angle_nodes": report.identified_angle_nodes,
                "model_file_present": report.model_file_present,
                "multiple_angles_lora_present": report.multiple_angles_lora_present,
                "missing_node_types": report.missing_node_types,
                "blockers": report.blockers,
                "generation_authorized": report.generation_authorized,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
