"""Validate the checked-in managed Qwen edit graph without submitting jobs."""

import json
from pathlib import Path

import pytest

from vscs.application.caps.managed_qwen_edit_inspection import (
    ManagedQwenEditError,
    inspect_managed_qwen_edit_workflow,
)

_GRAPH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vscs"
    / "workflows"
    / "image"
    / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
)


def test_existing_managed_workflow_is_image_conditioned_but_not_authorized():
    result = inspect_managed_qwen_edit_workflow(_GRAPH)
    assert result.loader_node_id == "171"
    assert result.sampler_node_id == "170:169"
    assert result.output_node_id == "9"
    assert "qwen_image_edit_2511_fp8mixed" in result.model_name
    assert "Lightning-4steps" in result.lora_name
    assert not result.execution_authorized
    assert len(result.blockers) == 4


def test_empty_latent_substitution_rejected(tmp_path):
    graph = json.loads(_GRAPH.read_text(encoding="utf-8"))
    graph["170:169"]["inputs"]["latent_image"] = ["170:156", 1]
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    with pytest.raises(ManagedQwenEditError, match="latent_image"):
        inspect_managed_qwen_edit_workflow(path)


def test_loader_source_disconnect_rejected(tmp_path):
    graph = json.loads(_GRAPH.read_text(encoding="utf-8"))
    graph["170:160"]["inputs"]["image"] = ["171", 1]
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    with pytest.raises(ManagedQwenEditError, match="image"):
        inspect_managed_qwen_edit_workflow(path)


def test_wrong_checkpoint_rejected(tmp_path):
    graph = json.loads(_GRAPH.read_text(encoding="utf-8"))
    graph["170:161"]["inputs"]["unet_name"] = "text_to_image.safetensors"
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    with pytest.raises(ManagedQwenEditError, match="checkpoint"):
        inspect_managed_qwen_edit_workflow(path)


def test_custom_output_disconnected_rejected(tmp_path):
    graph = json.loads(_GRAPH.read_text(encoding="utf-8"))
    graph["9"]["inputs"]["images"] = ["170:156", 0]
    path = tmp_path / "modified.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    with pytest.raises(ManagedQwenEditError, match="images"):
        inspect_managed_qwen_edit_workflow(path)
