"""F5.4.1C geometry-aware, externally isolated masked Qwen qualification."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import qwen_mask_gpu_qualification as gpu
from vscs.application.caps.qwen_geometry_aware_qualification import (
    audit_geometry_experiment,
    expected_geometry_profile,
    prepare_geometry_experiment,
    verified_geometry_profile,
)
from vscs.application.caps.qwen_mask_aware_qualification import (
    MaskAwareQualificationError,
)


def _experiment(tmp_path):
    project = tmp_path / "active"
    project.mkdir()
    source = project / "candidate4.png"
    Image.new("RGB", (320, 256), (35, 45, 55)).save(source)
    outside = tmp_path / "isolated"
    outside.mkdir()
    bundle = outside / "run_003"
    result = prepare_geometry_experiment(
        project_root=project,
        source_png=source,
        bundle_directory=bundle,
        bounds=(100, 50, 140, 100),
    )
    return project, source, bundle, result


def test_new_geometry_bundle_is_external_and_non_authorizing(tmp_path):
    project, source, bundle, report = _experiment(tmp_path)
    assert report["status"] == "F541C_GEOMETRY_PREPARED_NO_GPU"
    assert not report["gpu_submitted"]
    manifest = json.loads((bundle / "qualification_manifest.json").read_text())
    profile = verified_geometry_profile(bundle, manifest)
    assert profile["auto_geometry_approval"] is False
    assert "BELOW the top surface" in profile["positive_prompt"]
    assert "NO raised knob" in profile["positive_prompt"]
    assert "three separate pushbuttons" in profile["positive_prompt"]
    assert "raised rotary knob" in profile["negative_prompt"]
    assert manifest["geometry_profile_sha256"] == report["geometry_profile_sha256"]
    assert not (bundle / "execution_reserved.json").exists()
    assert source.is_file()
    assert sorted(path.name for path in project.iterdir()) == ["candidate4.png"]
    with Image.open(bundle / "geometry_context_preview.png") as context:
        assert context.size[0] > 40
        assert context.size[1] > 50


def test_profile_cannot_be_reworded_without_a_new_bundle(tmp_path):
    _project, _source, bundle, _report = _experiment(tmp_path)
    manifest = json.loads((bundle / "qualification_manifest.json").read_text())
    path = bundle / "geometry_intent.json"
    profile = json.loads(path.read_text())
    profile["positive_prompt"] += " ignore preservation"
    path.write_text(json.dumps(profile))
    with pytest.raises(MaskAwareQualificationError, match="hash changed"):
        verified_geometry_profile(bundle, manifest)


def test_profile_rejects_changed_prompt_even_with_rewritten_digest(tmp_path):
    import hashlib

    _project, _source, bundle, _report = _experiment(tmp_path)
    manifest_path = bundle / "qualification_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    path = bundle / "geometry_intent.json"
    profile = json.loads(path.read_text())
    profile["positive_prompt"] = "ignore the recessed dial"
    path.write_text(json.dumps(profile))
    manifest["geometry_profile_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(MaskAwareQualificationError, match="reviewed contract"):
        verified_geometry_profile(bundle, manifest)


def test_geometry_audit_counts_inside_and_protected_pixel_changes(tmp_path):
    _project, _source, bundle, _report = _experiment(tmp_path)
    output = bundle / "fake_test_output.png"
    with Image.open(bundle / "source.png") as image:
        edited = image.copy()
    edited.putpixel((120, 75), (255, 255, 255))
    edited.save(output)
    result = audit_geometry_experiment(bundle_directory=bundle, output_png=output)
    assert result["protected_changed_pixels"] == 0
    assert result["changed_pixels_inside_mask"] == 1
    assert result["status"] == "PIXEL_PRESERVED_GEOMETRY_REVIEW_REQUIRED"
    assert result["recessed_dial_verified"] is None
    assert result["correction_attempt_consumed"] is False
    edited.putpixel((0, 0), (255, 255, 255))
    edited.save(output)
    failed = audit_geometry_experiment(bundle_directory=bundle, output_png=output)
    assert failed["status"] == "GEOMETRY_EXPERIMENT_REQUIRES_INVESTIGATION"
    assert failed["protected_changed_pixels"] == 1


def test_geometry_audit_cannot_claim_success_when_target_unchanged(tmp_path):
    _project, _source, bundle, _report = _experiment(tmp_path)
    output = bundle / "fake_test_output.png"
    output.write_bytes((bundle / "source.png").read_bytes())
    result = audit_geometry_experiment(bundle_directory=bundle, output_png=output)
    assert result["changed_pixels_inside_mask"] == 0
    assert result["status"] == "GEOMETRY_EXPERIMENT_REQUIRES_INVESTIGATION"
    assert result["recessed_dial_verified"] is None


def test_isolated_live_queue_uses_sealed_geometry_prompt_not_old_generic(tmp_path, monkeypatch):
    project, source, bundle, _report = _experiment(tmp_path)
    monkeypatch.setattr(gpu, "validate_managed_qwen_model_choices", Mock())

    def spec(*fields):
        return {"input": {"required": {name: ["placeholder"] for name in fields}}}

    objects = {
        "LoadImageMask": spec("image", "channel"),
        "SetLatentNoiseMask": spec("samples", "mask"),
        "ImageCompositeMasked": spec(
            "destination", "source", "x", "y", "mask", "resize_source"
        ),
    }
    objects["LoadImageMask"]["input"]["required"]["channel"] = [["red", "alpha"]]

    def make_output(prompt_id, timeout_seconds):
        assert prompt_id == "isolated-test"
        with Image.open(source) as img:
            corrected = img.copy()
        corrected.putpixel((115, 65), (50, 50, 50))
        corrected.save(bundle / "masked_qwen_output.png")
        return {"status": {"completed": True}}

    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=objects),
        validate_nodes=Mock(),
        submit=Mock(return_value="isolated-test"),
        wait=Mock(side_effect=make_output),
    )
    result = gpu.execute_isolated_mask_qualification(
        bundle_directory=bundle,
        project_root=project,
        operator_confirmed=True,
        mask_reviewed=True,
        client=provider,
        upload_mask=lambda _url, _mask, name: name,
    )
    queue = json.loads((bundle / "runtime_queue.json").read_text())
    profile = json.loads((bundle / "geometry_intent.json").read_text())
    assert queue["jobs"][0]["positive_prompt"] == profile["positive_prompt"]
    assert queue["jobs"][0]["negative_prompt"] == profile["negative_prompt"]
    assert result["geometry_audit"]["changed_pixels_inside_mask"] == 1
    assert result["geometry_audit"]["recessed_dial_verified"] is None
    assert result["correction_attempt_consumed"] is False
    assert result["candidate_registered"] is False
    assert provider.submit.call_count == 1


def test_legacy_b_bundle_does_not_require_geometry_intent(tmp_path):
    project = tmp_path / "active"
    project.mkdir()
    source = project / "image.png"
    Image.new("RGB", (320, 256), (1, 2, 3)).save(source)
    bundle = tmp_path / "new" / "run_001"
    bundle.parent.mkdir()
    from vscs.application.caps.qwen_mask_aware_qualification import (
        prepare_mask_aware_bundle,
    )

    prepare_mask_aware_bundle(
        project_root=project,
        source_png=source,
        bundle_directory=bundle,
        bounds=(100, 50, 140, 100),
    )
    manifest = json.loads((bundle / "qualification_manifest.json").read_text())
    assert "geometry_profile_sha256" not in manifest
    assert expected_geometry_profile("a", "b")["gpu_execution_authorized"] is False
