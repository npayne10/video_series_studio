"""Mocked one-shot managed Qwen CAP edit: no real ComfyUI or GPU requests."""

import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import managed_qwen_correction_job as compiler
from vscs.application.caps import managed_qwen_live_correction as live

_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vscs"
    / "workflows"
    / "image"
    / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
)


def _fixture(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    workflow = tmp_path / "qwen_edit_api.json"
    workflow.write_bytes(_TEMPLATE.read_bytes())
    image = root / "candidate.png"
    image.write_bytes(b"source evidence")
    accepted = (("entrances", "exactly one"),)
    contract = SimpleNamespace(
        project_root=root,
        asset_id="STORY-LOC-001",
        source_path=image,
        source_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        workflow_path=workflow,
        workflow_sha256=hashlib.sha256(workflow.read_bytes()).hexdigest(),
        evidence_sha256="contract-hash",
        correction_attempt=2,
        mask_path=None,
        accepted_fields=accepted,
    )
    plan = SimpleNamespace(
        attempt=2,
        source=SimpleNamespace(
            asset_id=contract.asset_id,
            accepted_fields=accepted,
            image_sha256=contract.source_sha256,
        ),
        request=SimpleNamespace(seed=7, negative_prompt="no extra equipment"),
    )
    service = Mock()
    return service, plan, contract


def _png():
    output = io.BytesIO()
    Image.new("RGB", (256, 256), "gray").save(output, format="PNG")
    return output.getvalue()


def test_managed_qwen_live_submits_once_after_preflight_and_reservation(tmp_path, monkeypatch):
    service, plan, contract = _fixture(tmp_path)
    validation = Mock()
    reservation = Mock()
    monkeypatch.setattr(live, "verify_spatial_contract", validation)
    monkeypatch.setattr(compiler, "verify_spatial_contract", Mock())
    monkeypatch.setattr(live, "reserve_guided_edit_attempt", reservation)

    class FakeClient:
        def __init__(self):
            self.submit = Mock(return_value="prompt-id")
            self.healthcheck = Mock()
            self.validate_nodes = Mock()

        def wait(self, prompt_id, timeout_seconds):
            assert prompt_id == "prompt-id"
            assert timeout_seconds == 3600.0
            runtime = contract.project_root / ".vscs" / "runtime" / "comfyui"
            files = list((runtime / "jobs").glob("*/output/*.png"))
            assert not files
            output_roots = list((runtime / "jobs").glob("*/output"))
            assert len(output_roots) == 1
            job_id = output_roots[0].parent.name
            (output_roots[0] / f"cap_correction_{job_id}.png").write_bytes(_png())
            return {"status": {"completed": True}}

    client = FakeClient()
    result = live.render_one_managed_qwen_correction(
        service, plan, contract, operator_confirmed=True, client=client
    )
    client.healthcheck.assert_called_once()
    client.validate_nodes.assert_called_once()
    client.submit.assert_called_once()
    reservation.assert_called_once_with(contract)
    assert validation.call_count >= 3
    assert result.prompt_id == "prompt-id"
    assert result.output_node_id == "9"
    assert result.width == 256
    assert result.height == 256
    assert result.image_sha256 == hashlib.sha256(_png()).hexdigest()
    service.generator.persist_candidate.assert_not_called()


def test_managed_qwen_live_never_submits_without_explicit_consent(tmp_path):
    service, plan, contract = _fixture(tmp_path)
    client = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(live.GuidedEditExecutionError, match="operator approval"):
        live.render_one_managed_qwen_correction(
            service, plan, contract, operator_confirmed=False, client=client
        )
    client.submit.assert_not_called()
    client.healthcheck.assert_not_called()


def test_managed_qwen_live_refuses_mask_without_submission(tmp_path, monkeypatch):
    service, plan, contract = _fixture(tmp_path)
    contract.mask_path = tmp_path / "mask.png"
    monkeypatch.setattr(live, "verify_spatial_contract", Mock())
    client = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(live.GuidedEditExecutionError, match="Masked"):
        live.render_one_managed_qwen_correction(
            service, plan, contract, operator_confirmed=True, client=client
        )
    client.submit.assert_not_called()


def test_managed_qwen_live_preserves_unknown_attempt_after_submit_error(tmp_path, monkeypatch):
    service, plan, contract = _fixture(tmp_path)
    monkeypatch.setattr(live, "verify_spatial_contract", Mock())
    monkeypatch.setattr(compiler, "verify_spatial_contract", Mock())
    reserve = Mock()
    monkeypatch.setattr(live, "reserve_guided_edit_attempt", reserve)
    client = SimpleNamespace(
        submit=Mock(side_effect=RuntimeError("connection closed after POST")),
        healthcheck=Mock(),
        validate_nodes=Mock(),
    )
    with pytest.raises(RuntimeError, match="connection closed"):
        live.render_one_managed_qwen_correction(
            service, plan, contract, operator_confirmed=True, client=client
        )
    reserve.assert_called_once_with(contract)
    client.submit.assert_called_once()
