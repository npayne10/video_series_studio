"""F5.4.1 spatial edit fidelity inspection: no provider or CAP access."""

import json
from pathlib import Path

import pytest
from PIL import Image

from vscs.application.caps.qwen_spatial_fidelity import (
    QwenSpatialFidelityError,
    inspect_qwen_spatial_fidelity,
)

_WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vscs"
    / "workflows"
    / "image"
    / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
)


def test_real_managed_qwen_workflow_is_not_mask_qualified():
    report = inspect_qwen_spatial_fidelity()
    assert report.sampler_denoise == 1.0
    assert report.source_conditioned
    assert not report.mask_related_node_present
    assert not report.region_limited_edit_validated
    assert report.full_frame_reinterpretation_risk
    assert not report.execution_authorized
    assert not report.final_attempt_spatially_qualified
    assert "No mask/inpaint node" in report.describe()
    assert "No GPU call" in report.describe()


def test_complete_image_difference_is_diagnostic_not_design_authority(tmp_path):
    source = tmp_path / "source.png"
    edited = tmp_path / "edited.png"
    Image.new("RGB", (320, 256), (50, 50, 50)).save(source)
    Image.new("RGB", (320, 256), (60, 50, 50)).save(edited)
    report = inspect_qwen_spatial_fidelity(source_image=source, edited_image=edited)
    assert report.source_sha256 != report.edited_sha256
    assert report.source_dimensions == (320, 256)
    assert report.edited_dimensions == (320, 256)
    assert report.mean_absolute_rgb_delta is not None
    assert report.mean_absolute_rgb_delta > 0
    assert report.changed_pixel_percentage == 0.0
    assert not report.execution_authorized
    assert not report.region_limited_edit_validated


def test_different_image_sizes_block_pixelwise_equivalence(tmp_path):
    source = tmp_path / "source.png"
    edited = tmp_path / "edited.png"
    Image.new("RGB", (320, 256), (10, 20, 30)).save(source)
    Image.new("RGB", (360, 256), (10, 20, 30)).save(edited)
    report = inspect_qwen_spatial_fidelity(source_image=source, edited_image=edited)
    assert report.mean_absolute_rgb_delta is None
    assert report.changed_pixel_percentage is None
    assert any("dimensions differ" in item for item in report.warnings)


def test_missing_partner_image_fails_closed(tmp_path):
    with pytest.raises(QwenSpatialFidelityError, match="together"):
        inspect_qwen_spatial_fidelity(source_image=tmp_path / "source.png")


def test_modified_sampler_denoise_not_treated_as_mask_control(tmp_path):
    graph = json.loads(_WORKFLOW.read_text(encoding="utf-8"))
    graph["170:169"]["inputs"]["denoise"] = 0.5
    changed = tmp_path / "derived_api.json"
    changed.write_text(json.dumps(graph), encoding="utf-8")
    report = inspect_qwen_spatial_fidelity(workflow_path=changed)
    assert report.sampler_denoise == 0.5
    assert not report.region_limited_edit_validated
    assert report.full_frame_reinterpretation_risk


def test_fake_mask_node_not_treated_as_validated_spatial_edit(tmp_path):
    graph = json.loads(_WORKFLOW.read_text(encoding="utf-8"))
    graph["999"] = {
        "class_type": "InpaintModelConditioning",
        "inputs": {"not_connected": True},
    }
    changed = tmp_path / "derived_api.json"
    changed.write_text(json.dumps(graph), encoding="utf-8")
    report = inspect_qwen_spatial_fidelity(workflow_path=changed)
    assert report.mask_related_node_present
    assert not report.region_limited_edit_validated
    assert not report.final_attempt_spatially_qualified
