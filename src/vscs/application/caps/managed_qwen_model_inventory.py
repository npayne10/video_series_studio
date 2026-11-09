"""Read-only ComfyUI model selection preflight for managed Qwen Image Edit."""

from __future__ import annotations

from pathlib import PureWindowsPath
from typing import Any

from vscs.application.caps.guided_edit_live_transport import GuidedEditExecutionError

_MODEL_FIELDS = (
    ("UNETLoader", "unet_name"),
    ("LoraLoaderModelOnly", "lora_name"),
    ("CLIPLoader", "clip_name"),
    ("VAELoader", "vae_name"),
)


def validate_managed_qwen_model_choices(
    graph: dict[str, Any],
    object_info: dict[str, Any],
) -> None:
    """Require exact selected checkpoint/LoRA/encoder/VAE in node inventory.

    Unlike class-only checking, this verifies that ComfyUI advertises each
    named model file. It does NOT load models, prove VRAM fit or grant consent.
    """
    for class_type, field in _MODEL_FIELDS:
        selected = [
            node["inputs"].get(field)
            for node in graph.values()
            if isinstance(node, dict) and node.get("class_type") == class_type
        ]
        if len(selected) != 1 or not isinstance(selected[0], str):
            raise GuidedEditExecutionError(f"Qwen graph has invalid {class_type} selection")
        spec = object_info.get(class_type)
        if not isinstance(spec, dict):
            raise GuidedEditExecutionError(f"Missing ComfyUI inventory for {class_type}")
        inputs = spec.get("input")
        if not isinstance(inputs, dict):
            raise GuidedEditExecutionError(f"Missing ComfyUI schema for {class_type}")
        required = inputs.get("required")
        if not isinstance(required, dict):
            raise GuidedEditExecutionError(f"Missing ComfyUI choices for {class_type}")
        definition = required.get(field)
        if (
            not isinstance(definition, list)
            or not definition
            or not isinstance(definition[0], list)
            or not all(isinstance(choice, str) for choice in definition[0])
        ):
            raise GuidedEditExecutionError(f"Missing model choices for {class_type}")
        normalized = {PureWindowsPath(value).as_posix().casefold() for value in definition[0]}
        chosen = PureWindowsPath(selected[0]).as_posix().casefold()
        if chosen not in normalized:
            raise GuidedEditExecutionError(
                f"ComfyUI does not advertise selected {class_type} {field}: {selected[0]}"
            )
