"""F4B1 offline binding and staging: never submits a ComfyUI prompt."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import guided_edit_workflow_binding as binding


def _fixture(tmp_path, *, masked=False):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "source.png"
    Image.new("RGB", (16, 12), "gray").save(source)
    mask = project / "mask.png"
    if masked:
        Image.new("L", (16, 12), 255).save(mask)
    workflow = project / "qwen_edit.json"
    graph = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "placeholder.png"}},
        "2": {
            "class_type": "TextEncodeQwenImageEdit",
            "inputs": {"text": "previous untrusted prompt", "image": ["1", 0]},
        },
        "3": {"class_type": "KSampler", "inputs": {"positive": ["2", 0]}},
    }
    if masked:
        graph["4"] = {
            "class_type": "LoadImageMask",
            "inputs": {"image": "mask_placeholder.png"},
        }
    workflow.write_text(json.dumps(graph), encoding="utf-8")
    contract = SimpleNamespace(
        source_path=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        mask_path=mask if masked else None,
        mask_sha256=hashlib.sha256(mask.read_bytes()).hexdigest() if masked else None,
        workflow_path=workflow,
        workflow_sha256=hashlib.sha256(workflow.read_bytes()).hexdigest(),
        evidence_sha256="sealed-f3",
        accepted_fields=(("layout", "ONE door"), ("route", "continuous amber floor line")),
        verify_seal=Mock(),
    )
    mapping = binding.GuidedEditNodeMap(
        source_node_id="1",
        source_input="image",
        prompt_node_id="2",
        prompt_input="text",
        mask_node_id="4" if masked else None,
        mask_input="image" if masked else None,
    )
    comfy = tmp_path / "comfy"
    (comfy / "input").mkdir(parents=True)
    return Mock(), Mock(), contract, mapping, comfy


def _bind(service, plan, contract, mapping):
    return binding.bind_guided_edit_workflow(
        service, plan, contract, mapping,
        source_filename="staged.png",
        mask_filename="mask.png" if contract.mask_path is not None else None,
    )


def test_f4b_binds_governed_constraints_to_copy_without_writing_source(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    validation = Mock()
    monkeypatch.setattr(binding, "verify_spatial_contract", validation)
    result = _bind(service, plan, contract, mapping)
    assert result.prompt["1"]["inputs"]["image"] == "staged.png"
    assert result.prompt["2"]["inputs"]["text"] == (
        "layout: ONE door\nroute: continuous amber floor line"
    )
    assert not result.execution_authorized
    assert "previous untrusted prompt" in contract.workflow_path.read_text(encoding="utf-8")
    validation.assert_called_once_with(service, plan, contract)


def test_f4b_offline_mask_binding_requires_explicit_mapping(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path, masked=True)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    result = _bind(service, plan, contract, mapping)
    assert result.prompt["4"]["inputs"]["image"] == "mask.png"
    mapping = binding.GuidedEditNodeMap("1", "image", "2", "text")
    with pytest.raises(binding.GuidedEditBindingError, match="Mask"):
        _bind(service, plan, contract, mapping)


@pytest.mark.parametrize("filename", ["../evil.png", "bad/other.png", "http:x.png", "bad.png.bak"])
def test_f4b_rejects_untrusted_staging_filenames(tmp_path, monkeypatch, filename):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    with pytest.raises(binding.GuidedEditBindingError, match="unsafe"):
        binding.bind_guided_edit_workflow(
            service, plan, contract, mapping,
            source_filename=filename,
            mask_filename=None,
        )


def test_f4b_rejects_stale_workflow(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    contract.workflow_path.write_text("{}", encoding="utf-8")
    with pytest.raises(binding.GuidedEditBindingError, match="changed"):
        _bind(service, plan, contract, mapping)


def test_f4b_rejects_wrong_node_mapping(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    wrong = binding.GuidedEditNodeMap("3", "positive", "2", "text")
    with pytest.raises(binding.GuidedEditBindingError, match="mapping"):
        _bind(service, plan, contract, wrong)


def test_f4b_stages_and_cleans_immutable_source_without_mutating_it(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path, masked=True)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    staged = binding.stage_guided_edit_inputs(
        service, plan, contract,
        comfyui_input_directory=comfy / "input",
        trusted_comfyui_directory=comfy,
    )
    assert staged.source_path.is_file()
    assert staged.mask_path is not None and staged.mask_path.is_file()
    assert staged.source_path.read_bytes() == contract.source_path.read_bytes()
    assert staged.mask_path.read_bytes() == contract.mask_path.read_bytes()
    staged.cleanup()
    assert not staged.source_path.exists()
    assert not staged.mask_path.exists()
    assert contract.source_path.exists()


def test_f4b_rejects_wrong_staging_directory(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(binding.GuidedEditBindingError, match="differs"):
        binding.stage_guided_edit_inputs(
            service, plan, contract,
            comfyui_input_directory=other,
            trusted_comfyui_directory=comfy,
        )


def test_f4b_rejects_tampered_source_before_any_write(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    Image.new("RGB", (16, 12), "black").save(contract.source_path)
    with pytest.raises(binding.GuidedEditBindingError, match="changed"):
        binding.stage_guided_edit_inputs(
            service, plan, contract,
            comfyui_input_directory=comfy / "input",
            trusted_comfyui_directory=comfy,
        )
    assert not list((comfy / "input").iterdir())


def test_f4b_cleanup_keeps_modified_staging_file(tmp_path, monkeypatch):
    service, plan, contract, mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    staged = binding.stage_guided_edit_inputs(
        service, plan, contract,
        comfyui_input_directory=comfy / "input",
        trusted_comfyui_directory=comfy,
    )
    staged.source_path.write_bytes(b"changed")
    staged.cleanup()
    assert staged.source_path.exists()

def test_f4b_refuses_symlink_comfyui_input_root(tmp_path, monkeypatch):
    service, plan, contract, _mapping, comfy = _fixture(tmp_path)
    monkeypatch.setattr(binding, "verify_spatial_contract", Mock())
    target = tmp_path / "outside"
    target.mkdir()
    (comfy / "input").rmdir()
    try:
        (comfy / "input").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Directory symlinks are not available on this platform")
    with pytest.raises(binding.GuidedEditBindingError, match="symlink"):
        binding.stage_guided_edit_inputs(
            service, plan, contract,
            comfyui_input_directory=comfy / "input",
            trusted_comfyui_directory=comfy,
        )
    assert not list(target.iterdir())
