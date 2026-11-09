"""Read-only Qwen model inventory acceptance against actual managed graph."""

import json
from pathlib import Path

import pytest

from vscs.application.caps.guided_edit_live_transport import GuidedEditExecutionError
from vscs.application.caps.managed_qwen_model_inventory import (
    validate_managed_qwen_model_choices,
)

_GRAPH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vscs"
    / "workflows"
    / "image"
    / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
)


def _fixture():
    graph = json.loads(_GRAPH.read_text(encoding="utf-8"))
    inventory = {}
    for node in graph.values():
        kind = node["class_type"]
        for name in ("unet_name", "lora_name", "clip_name", "vae_name"):
            if name in node["inputs"]:
                inventory[kind] = {"input": {"required": {name: [[node["inputs"][name]]]}}}
    return graph, inventory


def test_actual_managed_qwen_model_selections_present():
    graph, inventory = _fixture()
    validate_managed_qwen_model_choices(graph, inventory)


def test_missing_checkpoint_choice_fails_closed():
    graph, inventory = _fixture()
    inventory["UNETLoader"]["input"]["required"]["unet_name"][0] = [
        "qwen\\qwen_image_2512_text_to_image.safetensors"
    ]
    with pytest.raises(GuidedEditExecutionError, match="does not advertise"):
        validate_managed_qwen_model_choices(graph, inventory)


def test_missing_lora_inventory_fails_closed():
    graph, inventory = _fixture()
    del inventory["LoraLoaderModelOnly"]
    with pytest.raises(GuidedEditExecutionError, match="Missing ComfyUI inventory"):
        validate_managed_qwen_model_choices(graph, inventory)


def test_invalid_clip_choice_schema_fails_closed():
    graph, inventory = _fixture()
    inventory["CLIPLoader"]["input"]["required"]["clip_name"] = "unverified"
    with pytest.raises(GuidedEditExecutionError, match="Missing model choices"):
        validate_managed_qwen_model_choices(graph, inventory)
