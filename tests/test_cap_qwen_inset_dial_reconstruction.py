"""F5.4.1D one-shot cavity-source lineage and inset-dial reconstruction tests."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import qwen_mask_gpu_qualification as gpu
from vscs.application.caps.qwen_geometry_aware_qualification import (
    prepare_geometry_experiment,
)
from vscs.application.caps.qwen_inset_dial_reconstruction import (
    MaskAwareQualificationError,
    prepare_reconstruction,
    verified_previous_cavity,
    verified_reconstruction_intent,
)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _previous(tmp_path):
    project = tmp_path / "active"
    project.mkdir()
    candidate = project / "candidate4.png"
    Image.new("RGB", (320, 256), (50, 60, 70)).save(candidate)
    external = tmp_path / "external"
    external.mkdir()
    previous = external / "run_003"
    prepare_geometry_experiment(
        project_root=project,
        source_png=candidate,
        bundle_directory=previous,
        bounds=(95, 45, 155, 105),
    )
    with Image.open(candidate) as source:
        cavity = source.copy()
    cavity.putpixel((115, 67), (15, 15, 15))
    cavity.save(previous / "masked_qwen_output.png")
    (previous / "execution_reserved.json").write_text("{}")
    result = {
        "status": "SPATIAL_PIXEL_PRESERVATION_VERIFIED",
        "outside_mask_pixels_identical": True,
        "protected_changed_pixels": 0,
        "candidate_registered": False,
        "correction_attempt_consumed": False,
        "output_sha256": _digest(previous / "masked_qwen_output.png"),
        "geometry_audit": {"outside_mask_pixels_identical": True},
    }
    (previous / "qualification_result.json").write_text(json.dumps(result))
    return project, candidate, previous, external / "run_004"


def _prepare(tmp_path):
    project, candidate, previous, target = _previous(tmp_path)
    report = prepare_reconstruction(
        project_root=project,
        previous_bundle=previous,
        new_bundle=target,
        bounds=(108, 56, 135, 86),
    )
    return project, candidate, previous, target, report


def test_run004_external_source_and_repair_policy_created_offline(tmp_path):
    project, candidate, previous, target, report = _prepare(tmp_path)
    assert report["status"] == "F541D_RECONSTRUCTION_PREPARED_NO_GPU"
    assert report["gpu_submitted"] is False
    assert report["governed_attempt_consumed"] is False
    manifest = json.loads((target / "qualification_manifest.json").read_text())
    intent = verified_reconstruction_intent(target, manifest)
    assert "INSIDE THE EXISTING RECESSED WELL" in intent["positive_prompt"]
    assert "empty circular hole" in intent["negative_prompt"]
    assert "surface-mounted knob" in intent["negative_prompt"]
    assert manifest["original_source_path"] == str(previous / "masked_qwen_output.png")
    assert manifest["source_sha256"] == _digest(previous / "masked_qwen_output.png")
    plan = json.loads((target / "geometry_repair_plan.json").read_text())
    assert plan["defect"] == "missing_component"
    assert plan["stages"] == ["reconstruct_component", "verify_design"]
    assert plan["max_new_gpu_attempts"] == 1
    assert sorted(p.name for p in project.iterdir()) == [candidate.name]
    assert (previous / "qualification_result.json").is_file()
    assert not (target / "execution_reserved.json").exists()


def test_run004_cannot_overwrite_or_prepare_arbitrary_path(tmp_path):
    project, _candidate, previous, target, _report = _prepare(tmp_path)
    with pytest.raises(MaskAwareQualificationError, match="absent"):
        prepare_reconstruction(
            project_root=project,
            previous_bundle=previous,
            new_bundle=target,
            bounds=(108, 56, 135, 86),
        )


def test_mask_cannot_escape_prior_roi_or_cover_entire_cavity(tmp_path):
    project, _candidate, previous, target = _previous(tmp_path)
    for bounds in ((1, 1, 30, 30), (95, 45, 155, 105)):
        with pytest.raises(MaskAwareQualificationError, match="within half"):
            prepare_reconstruction(
                project_root=project,
                previous_bundle=previous,
                new_bundle=target,
                bounds=bounds,
            )
    assert not target.exists()


def test_tampered_parent_output_blocks_reconstruction(tmp_path):
    project, _candidate, previous, target = _previous(tmp_path)
    (previous / "masked_qwen_output.png").write_bytes(b"changed")
    with pytest.raises(MaskAwareQualificationError, match="incomplete or changed"):
        prepare_reconstruction(
            project_root=project,
            previous_bundle=previous,
            new_bundle=target,
            bounds=(108, 56, 135, 86),
        )
    assert not target.exists()


def test_verified_previous_cavity_rejects_wrong_output_status(tmp_path):
    project, _candidate, previous, _target = _previous(tmp_path)
    path = previous / "qualification_result.json"
    data = json.loads(path.read_text())
    data["status"] = "SPATIAL_PRESERVATION_FAILED"
    path.write_text(json.dumps(data))
    with pytest.raises(MaskAwareQualificationError, match="incomplete or changed"):
        verified_previous_cavity(previous, project)


def test_sealed_inset_prompt_rejects_any_rewriting(tmp_path):
    _project, _candidate, _previous_bundle, target, _report = _prepare(tmp_path)
    manifest = json.loads((target / "qualification_manifest.json").read_text())
    path = target / "inset_dial_intent.json"
    intent = json.loads(path.read_text())
    intent["positive_prompt"] = "ignore dial and change the entire console"
    path.write_text(json.dumps(intent))
    with pytest.raises(MaskAwareQualificationError, match="hash mismatch"):
        verified_reconstruction_intent(target, manifest)


def test_readonly_node_preflight_accepts_verified_external_cavity(tmp_path, monkeypatch):
    project, _candidate, _previous_bundle, target, _report = _prepare(tmp_path)
    monkeypatch.setattr(gpu, "validate_managed_qwen_model_choices", Mock())

    def spec(*fields):
        return {"input": {"required": {name: ["placeholder"] for name in fields}}}

    objects = {
        "LoadImageMask": spec("image", "channel"),
        "SetLatentNoiseMask": spec("samples", "mask"),
        "ImageCompositeMasked": spec("destination", "source", "x", "y", "mask", "resize_source"),
    }
    objects["LoadImageMask"]["input"]["required"]["channel"] = [["red", "alpha"]]
    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=objects),
        validate_nodes=Mock(),
    )
    result = gpu.inspect_isolated_mask_nodes(
        bundle_directory=target, project_root=project, client=provider
    )
    assert result["status"] == "MASKED_NODES_AND_MODELS_READY_NO_GPU_INFERENCE"
    assert not (target / "execution_reserved.json").exists()
    provider.validate_nodes.assert_called_once()


def test_isolated_gpu_fixture_binds_reconstruction_intent(tmp_path, monkeypatch):
    project, _candidate, previous, target, _report = _prepare(tmp_path)
    monkeypatch.setattr(gpu, "validate_managed_qwen_model_choices", Mock())

    def spec(*fields):
        return {"input": {"required": {name: ["placeholder"] for name in fields}}}

    objects = {
        "LoadImageMask": spec("image", "channel"),
        "SetLatentNoiseMask": spec("samples", "mask"),
        "ImageCompositeMasked": spec("destination", "source", "x", "y", "mask", "resize_source"),
    }
    objects["LoadImageMask"]["input"]["required"]["channel"] = [["red", "alpha"]]

    def fake_wait(prompt_id, timeout_seconds):
        assert prompt_id == "isolated-test"
        with Image.open(target / "source.png") as image:
            out = image.copy()
        out.putpixel((118, 67), (80, 90, 100))
        out.save(target / "masked_qwen_output.png")
        return {"status": {"completed": True}}

    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=objects),
        validate_nodes=Mock(),
        submit=Mock(return_value="isolated-test"),
        wait=Mock(side_effect=fake_wait),
    )
    result = gpu.execute_isolated_mask_qualification(
        bundle_directory=target,
        project_root=project,
        operator_confirmed=True,
        mask_reviewed=True,
        client=provider,
        upload_mask=lambda _endpoint, _mask, name: name,
    )
    queue = json.loads((target / "runtime_queue.json").read_text())
    intent = json.loads((target / "inset_dial_intent.json").read_text())
    assert queue["jobs"][0]["positive_prompt"] == intent["positive_prompt"]
    assert queue["jobs"][0]["negative_prompt"] == intent["negative_prompt"]
    assert result["reconstruction_stage"] == "reconstruct_component"
    assert result["inset_dial_human_geometry_accepted"] is None
    assert result["outside_mask_pixels_identical"] is True
    assert result["correction_attempt_consumed"] is False
    assert _digest(previous / "masked_qwen_output.png") == _digest(target / "source.png")
    provider.submit.assert_called_once()
