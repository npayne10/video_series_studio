"""B.5.26F F4 — provider preflight fails closed without GPU work."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps import guided_edit_provider_preflight as preflight


def _setup(tmp_path: Path, *, connected: bool = True, mask: bool = False):
    models = tmp_path / "comfyui" / "models" / "diffusion_models" / "qwen"
    models.mkdir(parents=True)
    model = models / "qwen_image_edit_2511_fp8mixed.safetensors"
    model.write_bytes(b"fixture only; never load")
    workflow = tmp_path / "edit_api.json"
    graph = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": "source.png"},
        },
        "2": {
            "class_type": "TextEncodeQwenImageEdit",
            "inputs": {"image": ["1", 0], "text": "reviewed CAP only"},
        },
        "3": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "qwen\\\\qwen_image_edit_2511_fp8mixed.safetensors"},
        },
        "4": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["3", 0],
                "positive": ["2", 0],
                "latent_image": ["1", 0] if connected else ["7", 0],
            },
        },
        "5": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0]}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["5", 0]}},
    }
    if not connected:
        graph["2"]["inputs"]["image"] = ["7", 0]
        graph["7"] = {"class_type": "Other", "inputs": {}}
    if mask:
        graph["8"] = {"class_type": "InpaintModelConditioning", "inputs": {"mask": "m.png"}}
    workflow.write_text(json.dumps(graph), encoding="utf-8")
    contract = SimpleNamespace(
        workflow_path=workflow,
        evidence_sha256=hashlib.sha256(workflow.read_bytes()).hexdigest(),
        mask_path=tmp_path / "m.png" if mask else None,
        model_identifier="qwen_image_edit_2511_fp8mixed",
    )
    service = Mock()
    plan = Mock()
    return service, plan, contract, model, models.parent.parent, graph


def test_f4_linked_source_and_checkpoint_still_refuse_execution(tmp_path, monkeypatch):
    service, plan, contract, model, root, _graph = _setup(tmp_path)
    validation = Mock()
    monkeypatch.setattr(preflight, "verify_spatial_contract", validation)
    result = preflight.inspect_guided_edit_graph(
        service,
        plan,
        contract,
        model_file=model,
        trusted_model_directory=root,
    )
    validation.assert_called_once_with(service, plan, contract)
    assert result.source_loader_ids == ("1",)
    assert result.sampler_ids == ("4",)
    assert not result.execution_authorized
    assert not result.graph_validated
    assert any("operator execution consent" in error for error in result.blockers)
    assert result.checkpoint_bytes == model.stat().st_size


def test_f4_rejects_disconnected_source(tmp_path, monkeypatch):
    service, plan, contract, model, root, _graph = _setup(tmp_path, connected=False)
    monkeypatch.setattr(preflight, "verify_spatial_contract", Mock())
    result = preflight.inspect_guided_edit_graph(
        service, plan, contract, model_file=model, trusted_model_directory=root
    )
    assert any("not upstream" in error for error in result.blockers)


def test_f4_rejects_text_to_image_empty_latent(tmp_path, monkeypatch):
    service, plan, contract, model, root, graph = _setup(tmp_path)
    graph["7"] = {"class_type": "EmptySD3LatentImage", "inputs": {}}
    contract.workflow_path.write_text(json.dumps(graph), encoding="utf-8")
    monkeypatch.setattr(preflight, "verify_spatial_contract", Mock())
    result = preflight.inspect_guided_edit_graph(
        service, plan, contract, model_file=model, trusted_model_directory=root
    )
    assert any("empty-latent" in error for error in result.blockers)


def test_f4_missing_mask_conditioning_is_blocked(tmp_path, monkeypatch):
    service, plan, contract, model, root, _graph = _setup(tmp_path)
    contract.mask_path = tmp_path / "m.png"
    monkeypatch.setattr(preflight, "verify_spatial_contract", Mock())
    result = preflight.inspect_guided_edit_graph(
        service, plan, contract, model_file=model, trusted_model_directory=root
    )
    assert any("mask/inpainting" in error for error in result.blockers)


def test_f4_mismatched_workflow_checkpoint_fails_closed(tmp_path, monkeypatch):
    service, plan, contract, model, root, graph = _setup(tmp_path)
    graph["3"]["inputs"]["unet_name"] = "qwen\\\\other-model.safetensors"
    contract.workflow_path.write_text(json.dumps(graph), encoding="utf-8")
    monkeypatch.setattr(preflight, "verify_spatial_contract", Mock())
    result = preflight.inspect_guided_edit_graph(
        service, plan, contract, model_file=model, trusted_model_directory=root
    )
    assert any("not selected" in error for error in result.blockers)


def test_f4_refuses_checkpoint_outside_comfyui_models(tmp_path, monkeypatch):
    service, plan, contract, model, root, _graph = _setup(tmp_path)
    external = tmp_path / model.name
    external.write_bytes(b"untrusted")
    monkeypatch.setattr(preflight, "verify_spatial_contract", Mock())
    with pytest.raises(preflight.GuidedEditPreflightError, match="escapes"):
        preflight.inspect_guided_edit_graph(
            service, plan, contract, model_file=external, trusted_model_directory=root
        )


def test_f4_revalidates_f3_before_inspection(tmp_path, monkeypatch):
    service, plan, contract, model, root, _graph = _setup(tmp_path)
    from vscs.application.caps.spatial_correction_contract import (
        SpatialCorrectionContractError,
    )

    monkeypatch.setattr(
        preflight,
        "verify_spatial_contract",
        Mock(side_effect=SpatialCorrectionContractError("source changed")),
    )
    with pytest.raises(preflight.GuidedEditPreflightError, match="source changed"):
        preflight.inspect_guided_edit_graph(
            service, plan, contract, model_file=model, trusted_model_directory=root
        )
