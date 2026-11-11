"""F5.4.1B: reviewed-mask, one-shot isolated GPU acceptance guards."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import qwen_mask_gpu_qualification as live
from vscs.application.caps.qwen_mask_aware_qualification import (
    MaskAwareQualificationError,
    prepare_mask_aware_bundle,
)


def _bundle(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "candidate4.png"
    Image.new("RGB", (320, 256), (90, 95, 100)).save(source)
    bundle = tmp_path / "separate" / "run_001"
    bundle.parent.mkdir()
    prepare_mask_aware_bundle(
        project_root=project,
        source_png=source,
        bundle_directory=bundle,
        bounds=(100, 50, 140, 100),
    )
    return project, source, bundle


def _schema():
    def spec(*fields):
        return {"input": {"required": {name: ["placeholder"] for name in fields}}}

    result = {
        "LoadImageMask": spec("image", "channel"),
        "SetLatentNoiseMask": spec("samples", "mask"),
        "ImageCompositeMasked": spec(
            "destination", "source", "x", "y", "mask", "resize_source"
        ),
    }
    result["LoadImageMask"]["input"]["required"]["channel"] = [["red", "alpha"]]
    return result


def test_no_gpu_consent_or_mask_review_does_not_reserve(tmp_path):
    project, _source, bundle = _bundle(tmp_path)
    provider = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    for gpu, reviewed in ((False, True), (True, False)):
        with pytest.raises(MaskAwareQualificationError, match="consent"):
            live.execute_isolated_mask_qualification(
                bundle_directory=bundle,
                project_root=project,
                operator_confirmed=gpu,
                mask_reviewed=reviewed,
                client=provider,
            )
    provider.healthcheck.assert_not_called()
    assert not (bundle / "execution_reserved.json").exists()


def test_missing_image_composite_node_fails_before_upload_or_gpu(tmp_path):
    project, _source, bundle = _bundle(tmp_path)
    objects = _schema()
    objects.pop("ImageCompositeMasked")
    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=objects),
        submit=Mock(),
    )
    upload = Mock()
    with pytest.raises(MaskAwareQualificationError, match="ImageCompositeMasked"):
        live.execute_isolated_mask_qualification(
            bundle_directory=bundle, project_root=project,
            operator_confirmed=True, mask_reviewed=True,
            client=provider, upload_mask=upload,
        )
    upload.assert_not_called()
    provider.submit.assert_not_called()
    assert not (bundle / "execution_reserved.json").exists()


def test_tampered_mask_refused_before_provider(tmp_path):
    project, _source, bundle = _bundle(tmp_path)
    (bundle / "mask.png").write_bytes(b"tampered")
    provider = SimpleNamespace(healthcheck=Mock(), submit=Mock())
    with pytest.raises(MaskAwareQualificationError, match="changed"):
        live.execute_isolated_mask_qualification(
            bundle_directory=bundle, project_root=project,
            operator_confirmed=True, mask_reviewed=True, client=provider,
        )
    provider.healthcheck.assert_not_called()
    assert not (bundle / "execution_reserved.json").exists()


def test_one_shot_success_keeps_original_project_unchanged(tmp_path, monkeypatch):
    project, source, bundle = _bundle(tmp_path)
    monkeypatch.setattr(live, "validate_managed_qwen_model_choices", Mock())

    class Provider:
        def __init__(self):
            self.healthcheck = Mock()
            self.object_info = Mock(return_value=_schema())
            self.validate_nodes = Mock()
            self.submit = Mock(return_value="masked-qwen-smoke")

        def wait(self, prompt_id, timeout_seconds):
            assert prompt_id == "masked-qwen-smoke"
            with Image.open(source) as original:
                edited = original.copy()
            edited.putpixel((120, 60), (150, 160, 170))
            edited.save(bundle / "masked_qwen_output.png")
            return {"status": {"completed": True}}

    provider = Provider()
    upload = Mock(side_effect=lambda _endpoint, _path, name: name)
    result = live.execute_isolated_mask_qualification(
        bundle_directory=bundle, project_root=project,
        operator_confirmed=True, mask_reviewed=True,
        client=provider, upload_mask=upload,
    )
    assert result["status"] == "SPATIAL_PIXEL_PRESERVATION_VERIFIED"
    assert result["outside_mask_pixels_identical"] is True
    assert result["candidate_registered"] is False
    assert result["correction_attempt_consumed"] is False
    assert (bundle / "execution_reserved.json").exists()
    assert (bundle / "qualification_result.json").exists()
    assert json.loads((bundle / "runtime_graph.json").read_text())[
        "F541B_MASK"
    ]["inputs"]["image"].startswith("vscs_f541b_")
    assert sorted(item.name for item in project.iterdir()) == [source.name]
    provider.submit.assert_called_once()
    upload.assert_called_once()


def test_submission_failure_reserves_once_and_prevents_retry(tmp_path, monkeypatch):
    project, _source, bundle = _bundle(tmp_path)
    monkeypatch.setattr(live, "validate_managed_qwen_model_choices", Mock())
    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=_schema()),
        validate_nodes=Mock(),
        submit=Mock(side_effect=RuntimeError("unknown GPU submission")),
    )
    upload = Mock(side_effect=lambda _endpoint, _path, name: name)
    with pytest.raises(RuntimeError, match="unknown GPU"):
        live.execute_isolated_mask_qualification(
            bundle_directory=bundle, project_root=project,
            operator_confirmed=True, mask_reviewed=True,
            client=provider, upload_mask=upload,
        )
    assert (bundle / "execution_reserved.json").exists()
    with pytest.raises(MaskAwareQualificationError, match="cannot be retried"):
        live.execute_isolated_mask_qualification(
            bundle_directory=bundle, project_root=project,
            operator_confirmed=True, mask_reviewed=True,
            client=provider, upload_mask=upload,
        )
    provider.submit.assert_called_once()


def test_upload_name_mismatch_blocks_gpu_after_reservation(tmp_path, monkeypatch):
    project, _source, bundle = _bundle(tmp_path)
    monkeypatch.setattr(live, "validate_managed_qwen_model_choices", Mock())
    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=_schema()),
        submit=Mock(),
    )
    with pytest.raises(MaskAwareQualificationError, match="identity"):
        live.execute_isolated_mask_qualification(
            bundle_directory=bundle, project_root=project,
            operator_confirmed=True, mask_reviewed=True,
            client=provider, upload_mask=Mock(return_value="other_mask.png"),
        )
    provider.submit.assert_not_called()
    assert (bundle / "execution_reserved.json").exists()


def test_prepared_graph_must_match_original_offline_evidence(tmp_path):
    project, _source, bundle = _bundle(tmp_path)
    target = bundle / "experimental_masked_api.json"
    graph = json.loads(target.read_text())
    graph["170:169"]["inputs"]["latent_image"] = ["170:156", 0]
    target.write_text(json.dumps(graph))
    provider = SimpleNamespace(healthcheck=Mock())
    with pytest.raises(MaskAwareQualificationError, match="changed"):
        live.execute_isolated_mask_qualification(
            bundle_directory=bundle, project_root=project,
            operator_confirmed=True, mask_reviewed=True,
            client=provider,
        )
    provider.healthcheck.assert_not_called()


def test_read_only_node_inventory_does_not_upload_or_reserve(tmp_path, monkeypatch):
    project, _source, bundle = _bundle(tmp_path)
    monkeypatch.setattr(live, "validate_managed_qwen_model_choices", Mock())
    provider = SimpleNamespace(
        healthcheck=Mock(),
        object_info=Mock(return_value=_schema()),
        validate_nodes=Mock(),
        submit=Mock(),
    )
    result = live.inspect_isolated_mask_nodes(
        bundle_directory=bundle, project_root=project, client=provider,
    )
    assert result["status"] == "MASKED_NODES_AND_MODELS_READY_NO_GPU_INFERENCE"
    assert result["mask_uploaded"] is False
    assert result["gpu_submitted"] is False
    assert result["execution_authorized"] is False
    assert not (bundle / "execution_reserved.json").exists()
    provider.submit.assert_not_called()
    provider.validate_nodes.assert_called_once()


def test_read_only_node_inventory_refuses_existing_execution(tmp_path):
    project, _source, bundle = _bundle(tmp_path)
    (bundle / "execution_reserved.json").write_text("{}")
    provider = SimpleNamespace(healthcheck=Mock())
    with pytest.raises(MaskAwareQualificationError, match="no longer read-only"):
        live.inspect_isolated_mask_nodes(
            bundle_directory=bundle, project_root=project, client=provider,
        )
    provider.healthcheck.assert_not_called()
