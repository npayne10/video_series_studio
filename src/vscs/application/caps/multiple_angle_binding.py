"""Stage B.2C: source-authorised, non-executable multiple-angle graph compilation.

The result is inspection evidence, not a runnable ComfyUI submission. In
particular, queue and output placeholders intentionally remain unresolved.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, cast

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
)
from vscs.domain.caps import CanonicalReferenceView


class MultipleAngleBindingError(RuntimeError):
    """A draft multiple-angle binding failed before any provider interaction."""


@dataclass(frozen=True)
class MultipleAnglePreflight:
    asset_id: str
    view: CanonicalReferenceView
    master_sha256: str
    source_master_reference_id: str
    template_sha256: str
    camera_horizontal_degrees: int
    camera_vertical_degrees: int
    queue_payload: dict[str, Any]
    compiled_graph: dict[str, Any]
    missing_node_types: tuple[str, ...]
    missing_model_files: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def generation_authorized(self) -> bool:
        return False


class MultipleAngleOfflineCompiler:
    """Bind a reviewed camera template to locked MASTER provenance in memory."""

    TEMPLATE_NAME = "VSCS_Qwen_Multiple_Angles_Qualification_API_v1.json"
    EXPECTED_TEMPLATE_SHA256 = "fdf251d81eaa3eec0a5f997e3514fd8ba339924495ef074ce3b5b4a812b56942"
    SOURCE = "1"
    CAMERA = "221"
    MODEL = "219:161"
    MULTI_ANGLE_LORA = "219:220"
    LIGHTNING_LORA = "219:153"
    POSITIVE = "219:151"
    SCALE = "219:160"
    OUTPUT = "2"

    # Provisional camera-frame convention: requires operator qualification.
    CAMERA_AZIMUTH: ClassVar[dict[CanonicalReferenceView, int]] = {
        CanonicalReferenceView.FRONT: 0,
        CanonicalReferenceView.RIGHT: 90,
        CanonicalReferenceView.REAR: 180,
        CanonicalReferenceView.LEFT: 270,
    }

    def __init__(
        self,
        derived_service: DerivedReferenceGenerationService,
        *,
        template_path: Path | None = None,
    ) -> None:
        self.derived_service = derived_service
        self.template_path = template_path or (
            Path(__file__).resolve().parents[2] / "workflows" / "image" / self.TEMPLATE_NAME
        )

    def compile(
        self,
        asset_id: str,
        view: CanonicalReferenceView,
        *,
        seed: int,
        object_info: dict[str, Any] | None = None,
        model_root: Path | None = None,
    ) -> MultipleAnglePreflight:
        if view not in self.CAMERA_AZIMUTH:
            raise MultipleAngleBindingError(
                "Only Front, Rear, Left and Right are qualified for audit"
            )
        if seed < 0:
            raise MultipleAngleBindingError("Seed must be nonnegative")

        _project, _entries, master, _master_record, master_path = (
            self.derived_service._resolve_locked_master(asset_id)
        )
        cap = self.derived_service.references.caps.get(asset_id)
        isolated_description, _excluded_description = self.derived_service._isolated_description(
            cap.canonical_description
        )
        isolated_visual, _excluded_visual = self.derived_service._isolated_description(
            cap.visual_identity
        )
        master_hash = hashlib.sha256(master_path.read_bytes()).hexdigest()
        template_bytes = self.template_path.read_bytes()
        # Git may check out text files as CRLF on Windows. Validate the
        # reviewed LF-normalized content without weakening content integrity.
        normalized_template_bytes = template_bytes.replace(b"\r\n", b"\n")
        template_hash = hashlib.sha256(normalized_template_bytes).hexdigest()
        if (
            self.template_path.name == self.TEMPLATE_NAME
            and template_hash != self.EXPECTED_TEMPLATE_SHA256
        ):
            raise MultipleAngleBindingError("Reviewed multiple-angle template hash changed")
        try:
            template = json.loads(template_bytes)
        except json.JSONDecodeError as exc:
            raise MultipleAngleBindingError("Multiple-angle template is not valid JSON") from exc
        if not isinstance(template, dict):
            raise MultipleAngleBindingError("Multiple-angle template must be an API graph")
        self._validate_template(template)

        graph = deepcopy(template)
        angle = self.CAMERA_AZIMUTH[view]
        graph[self.CAMERA]["inputs"].update(horizontal_angle=angle, vertical_angle=0, zoom=5)
        graph[self.SOURCE] = {
            "class_type": "XCICQwenReferenceJobLoader",
            "inputs": {
                "queue_file": "__VSCS_UNQUALIFIED_QUEUE_FILE__",
                "job_index": 0,
                "quality_mode": "standard",
            },
        }
        # Both the camera guidance and image conditioning now refer to the
        # locked MASTER through the same source image output (port 0).
        graph[self.CAMERA]["inputs"]["image"] = [self.SOURCE, 0]
        graph[self.SCALE]["inputs"]["image"] = [self.SOURCE, 0]
        graph["219:169"]["inputs"]["seed"] = seed
        graph[self.OUTPUT]["inputs"]["filename_prefix"] = "__VSCS_UNQUALIFIED_OUTPUT__"

        queue_payload: dict[str, Any] = {
            "jobs": [
                {
                    "asset_id": asset_id.upper(),
                    "asset_category": "prop" if "-PRP-" in asset_id.upper() else "asset",
                    "reference_inputs": [str(master_path)],
                    "positive_prompt": self.derived_service._prompt(
                        isolated_description, isolated_visual, view
                    ),
                    "negative_prompt": self.derived_service._negative_prompt(),
                    "view": view.value,
                    "seed": seed,
                    "generation": {"enable_turbo_mode": True},
                    "generation_policy": {"force_standard_mode": True},
                    "output": {
                        "candidate_directory": "__VSCS_UNQUALIFIED_OUTPUT_DIRECTORY__",
                        "candidate_filename": "__VSCS_UNQUALIFIED_OUTPUT_FILENAME__",
                    },
                }
            ]
        }
        required = {node["class_type"] for node in graph.values()}
        missing = tuple(sorted(required - set(object_info))) if object_info is not None else ()
        blockers = [
            "Camera azimuth semantics and asset identity require operator qualification",
            "MASTER source queue/output staging and reconciliation are not implemented",
            "16 GiB GPU fit and provider execution remain unqualified",
        ]
        if object_info is None:
            blockers.append("ComfyUI object_info inventory was not supplied")
        if missing:
            blockers.append("Required ComfyUI node types are unavailable")
        missing_models: tuple[str, ...] = ()
        if model_root is None:
            blockers.append("Installed model inventory was not supplied")
        elif not model_root.is_dir():
            blockers.append("ComfyUI model directory does not exist")
        else:
            relative_models = (
                Path("diffusion_models/qwen/qwen_image_edit_2511_fp8mixed.safetensors"),
                Path("loras/qwen/qwen-image-edit-2511-multiple-angles-lora.safetensors"),
                Path("loras/qwen/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"),
                Path("text_encoders/qwen/qwen_2.5_vl_7b_fp8_scaled.safetensors"),
                Path("vae/qwen/qwen_image_vae.safetensors"),
            )
            missing_models = tuple(
                str(relative)
                for relative in relative_models
                if not (model_root / relative).is_file()
                or (model_root / relative).stat().st_size == 0
            )
            if missing_models:
                blockers.append("Required model files are missing or empty")
        return MultipleAnglePreflight(
            asset_id=asset_id.upper(),
            view=view,
            master_sha256=master_hash,
            source_master_reference_id=master.reference_id,
            template_sha256=template_hash,
            camera_horizontal_degrees=angle,
            camera_vertical_degrees=0,
            queue_payload=queue_payload,
            compiled_graph=graph,
            missing_node_types=missing,
            missing_model_files=missing_models,
            blockers=tuple(blockers),
        )

    def _validate_template(self, template: dict[str, Any]) -> None:
        expected = {
            self.SOURCE: "LoadImage",
            self.CAMERA: "CameraAngle",
            self.MODEL: "UNETLoader",
            self.MULTI_ANGLE_LORA: "LoraLoaderModelOnly",
            self.LIGHTNING_LORA: "LoraLoaderModelOnly",
            self.POSITIVE: "TextEncodeQwenImageEditPlus",
            self.SCALE: "FluxKontextImageScale",
            self.OUTPUT: "SaveImage",
            "219:169": "KSampler",
        }
        for node_id, class_type in expected.items():
            node = template.get(node_id)
            if not isinstance(node, dict) or node.get("class_type") != class_type:
                raise MultipleAngleBindingError(f"Unexpected node {node_id}: expected {class_type}")
            if not isinstance(node.get("inputs"), dict):
                raise MultipleAngleBindingError(f"Node {node_id} has no inputs")

        def inputs(node_id: str) -> dict[str, Any]:
            return cast(dict[str, Any], template[node_id]["inputs"])

        if inputs(self.SOURCE).get("image") != "__VSCS_PENDING_MASTER_BINDING__":
            raise MultipleAngleBindingError("Template source marker was modified")
        if inputs(self.POSITIVE).get("prompt") != [self.CAMERA, 1]:
            raise MultipleAngleBindingError(
                "Camera prompt does not reach Qwen positive conditioning"
            )
        if inputs(self.CAMERA).get("image") != [self.SOURCE, 0]:
            raise MultipleAngleBindingError("Camera preview is not linked to the source")
        if inputs(self.SCALE).get("image") != [self.SOURCE, 0]:
            raise MultipleAngleBindingError("Qwen image conditioning lost the source")
        if inputs(self.MULTI_ANGLE_LORA).get("model") != [self.MODEL, 0]:
            raise MultipleAngleBindingError("Multiple-angle LoRA not linked to the checkpoint")
        if not str(inputs(self.MODEL).get("unet_name", "")).endswith(
            "qwen_image_edit_2511_fp8mixed.safetensors"
        ):
            raise MultipleAngleBindingError("Reviewed FP8 checkpoint selection changed")
        if "multiple-angles-lora" not in str(inputs(self.MULTI_ANGLE_LORA).get("lora_name", "")):
            raise MultipleAngleBindingError("Dedicated camera-angle LoRA is not selected")
        if "Qwen-Image-Edit-2511-Lightning-4steps" not in str(
            inputs(self.LIGHTNING_LORA).get("lora_name", "")
        ):
            raise MultipleAngleBindingError("Reviewed Lightning LoRA selection changed")
