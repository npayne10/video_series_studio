"""Fail-closed, synthetic tests of one-use multiple-angle qualification."""

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from tests.unit.test_multiple_angle_execution_guard import _prepare

from vscs.application.caps.derived_reference_generation import DerivedReferenceGenerationError
from vscs.application.caps.multiple_angle_execution_guard import stage_offline_qualification
from vscs.application.caps.multiple_angle_live_execution import (
    execute_qualified_multiple_angle,
)
from vscs.application.caps.multiple_angle_runtime_readiness import plan_multiple_angle_runtime
from vscs.application.caps.reference_library import (
    ReferenceLibraryConflictError,
    _qualified_view_review,
)
from vscs.domain.caps import CanonicalReferenceLifecycle, CanonicalReferenceView


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), "blue").save(buffer, format="PNG")
    return buffer.getvalue()


def test_separate_camera_and_geometry_attestations_fail_closed() -> None:
    camera = "VIEWPOINT ACCEPTANCE: PASS — Operator checked perpendicular rear elevation."
    geometry = (
        "CANONICAL GEOMETRY REVIEW: VERIFIED — Compared every rear panel and "
        "mounting feature against approved engineering drawings."
    )
    assert _qualified_view_review(camera, unseen_geometry=False)
    assert not _qualified_view_review(camera, unseen_geometry=True)
    assert not _qualified_view_review(geometry, unseen_geometry=True)
    assert _qualified_view_review(camera + "\n" + geometry, unseen_geometry=True)
    assert not _qualified_view_review(
        camera.replace("PASS", "FAIL") + "\n" + geometry, unseen_geometry=True
    )
    assert not _qualified_view_review(
        camera + "\n" + geometry.replace("VERIFIED", "UNVERIFIED"), unseen_geometry=True
    )


class FakeComfyUI:
    submissions = 0

    def object_info(self):
        return {}

    def healthcheck(self):
        return None

    def submit(self, prompt):
        self.submissions += 1
        return "fake-prompt-id"

    def wait(self, prompt_id, timeout_seconds=3600.0):
        return {
            "status": {"completed": True},
            "outputs": {
                "2": {
                    "images": [
                        {
                            "filename": f"VSCS_QUALIFICATION_{self.qualification_id}_00001_.png",
                            "subfolder": "",
                            "type": "output",
                        }
                    ]
                }
            },
        }

    def fetch_output_image(self, image):
        return _png()


def _models(root: Path) -> Path:
    paths = (
        "diffusion_models/qwen/qwen_image_edit_2511_fp8mixed.safetensors",
        "loras/qwen/qwen-image-edit-2511-multiple-angles-lora.safetensors",
        "loras/qwen/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors",
        "text_encoders/qwen/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        "vae/qwen/qwen_image_vae.safetensors",
    )
    for name in paths:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic model marker")
    return root


def _permit_preflight(monkeypatch):
    monkeypatch.setattr(
        "vscs.application.caps.multiple_angle_live_execution.inspect_provider_compatibility",
        lambda *args: SimpleNamespace(
            missing_node_types=(),
            missing_input_names=(),
            invalid_links=(),
            incompatible_link_types=(),
            unresolved_switch_types=(),
            unresolved_source_bindings=(),
            unavailable_model_selections=(),
        ),
    )


def test_requires_scoped_gpu_consent_before_transport_or_mutation(tmp_path: Path) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    client = FakeComfyUI()
    with pytest.raises(DerivedReferenceGenerationError, match="authorization"):
        execute_qualified_multiple_angle(
            service, plan, staged, client=client, model_root=tmp_path, authorization="yes"
        )
    assert not staged.queue_path.with_suffix(".submission.json").exists()
    assert client.submissions == 0
    context.shutdown()


def test_qualified_output_registers_only_candidate_and_replay_fails(
    tmp_path: Path, monkeypatch
) -> None:
    context, project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    _permit_preflight(monkeypatch)
    client = FakeComfyUI()
    client.qualification_id = plan.qualification_id
    result = execute_qualified_multiple_angle(
        service,
        plan,
        staged,
        client=client,
        model_root=_models(tmp_path / "models"),
        authorization=f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}",
    )
    assert client.submissions == 1
    assert staged.output_path.read_bytes() == _png()
    assert result.status == "candidate_pending_human_qc"
    assert not result.production_approved
    assert (
        service.library.get(result.reference_record_id).lifecycle
        is CanonicalReferenceLifecycle.CANDIDATE
    )
    assert (project / "master.png").read_bytes() == b"approved synthetic MASTER"
    with pytest.raises(DerivedReferenceGenerationError, match="already used"):
        execute_qualified_multiple_angle(
            service,
            plan,
            staged,
            client=client,
            model_root=tmp_path,
            authorization=f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}",
        )
    assert client.submissions == 1
    context.shutdown()


def test_detailed_mode_is_recorded_on_single_candidate(tmp_path: Path, monkeypatch) -> None:
    context, _project, service, _plan = _prepare(tmp_path)
    plan = plan_multiple_angle_runtime(
        service,
        "CAP-PRP-999",
        CanonicalReferenceView.REAR,
        seed=11,
        sampling_mode="detailed",
        qualification_id="a" * 32,
    )
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    _permit_preflight(monkeypatch)
    client = FakeComfyUI()
    client.qualification_id = plan.qualification_id
    result = execute_qualified_multiple_angle(
        service,
        plan,
        staged,
        client=client,
        model_root=_models(tmp_path / "models"),
        authorization=f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}",
    )
    assert client.submissions == 1
    assert (
        json.loads(staged.queue_path.with_suffix(".submission.json").read_text())["sampling_mode"]
        == "detailed"
    )
    assert "Sampling mode: detailed" in service.references.get(result.reference_record_id).notes
    assert not result.production_approved
    context.shutdown()


def test_submission_exception_leaves_immutable_attempt_and_no_auto_retry(
    tmp_path: Path, monkeypatch
) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    _permit_preflight(monkeypatch)
    client = FakeComfyUI()

    def fail(_graph):
        raise RuntimeError("transport uncertain")

    client.submit = fail
    with pytest.raises(RuntimeError, match="uncertain"):
        execute_qualified_multiple_angle(
            service,
            plan,
            staged,
            client=client,
            model_root=_models(tmp_path / "models"),
            authorization=f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}",
        )
    assert staged.queue_path.with_suffix(".submission.json").exists()
    assert not staged.output_path.exists()
    context.shutdown()


def test_untrusted_provider_image_never_registers_a_candidate(tmp_path: Path, monkeypatch) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    _permit_preflight(monkeypatch)
    client = FakeComfyUI()
    client.qualification_id = plan.qualification_id
    client.fetch_output_image = lambda _image: b"not a PNG"
    with pytest.raises(DerivedReferenceGenerationError, match="bounded PNG"):
        execute_qualified_multiple_angle(
            service,
            plan,
            staged,
            client=client,
            model_root=_models(tmp_path / "models"),
            authorization=f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}",
        )
    assert not staged.output_path.exists()
    assert all(
        item.view is not CanonicalReferenceView.FRONT
        for item in service.library.list_for_cap("CAP-PRP-999", include_archived=True)
    )
    assert staged.queue_path.with_suffix(".submission.json").exists()
    context.shutdown()


def test_rear_candidate_requires_documented_human_geometry_review(
    tmp_path: Path, monkeypatch
) -> None:
    context, _project, service, _front_plan = _prepare(tmp_path)
    plan = plan_multiple_angle_runtime(
        service,
        "CAP-PRP-999",
        CanonicalReferenceView.REAR,
        seed=2,
        qualification_id="e" * 32,
    )
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    _permit_preflight(monkeypatch)
    client = FakeComfyUI()
    client.qualification_id = plan.qualification_id
    result = execute_qualified_multiple_angle(
        service,
        plan,
        staged,
        client=client,
        model_root=_models(tmp_path / "models"),
        authorization=f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}",
    )
    with pytest.raises(ReferenceLibraryConflictError, match="viewpoint acceptance"):
        service.library.approve(result.reference_record_id, "test-operator")
    assert (
        service.library.get(result.reference_record_id).lifecycle
        is CanonicalReferenceLifecycle.CANDIDATE
    )
    with pytest.raises(ReferenceLibraryConflictError, match="viewpoint acceptance"):
        service.library.approve(
            result.reference_record_id,
            "test-operator",
            note=(
                "VIEWPOINT ACCEPTANCE: PASS — Synthetic fixture: camera is perpendicular "
                "to requested rear elevation but geometry is still unverified"
            ),
        )
    service.library.approve(
        result.reference_record_id,
        "test-operator",
        note=(
            "VIEWPOINT ACCEPTANCE: PASS — Synthetic fixture: camera is perpendicular "
            "to requested rear elevation\n"
            "CANONICAL GEOMETRY REVIEW: VERIFIED — Synthetic acceptance fixture: reviewed "
            "the required rear surfaces against signed engineering drawings."
        ),
    )
    assert (
        service.library.get(result.reference_record_id).lifecycle
        is CanonicalReferenceLifecycle.APPROVED
    )
    context.shutdown()
