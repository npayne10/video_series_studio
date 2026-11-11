"""Governed CAP correction queue generation against the real Qwen edit API graph."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps import managed_qwen_correction_job as correction

_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "vscs"
    / "workflows"
    / "image"
    / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
)


def _fixture(tmp_path):
    graph = tmp_path / "managed_api.json"
    graph.write_bytes(_TEMPLATE.read_bytes())
    root = tmp_path / "project"
    root.mkdir()
    source = root / "source.png"
    source.write_bytes(b"test fixture image bytes only")
    asset_id = "STORY-LOC-001"
    contract = SimpleNamespace(
        project_root=root,
        asset_id=asset_id,
        source_path=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        workflow_path=graph,
        workflow_sha256=hashlib.sha256(graph.read_bytes()).hexdigest(),
        evidence_sha256="trusted-contract",
        correction_attempt=2,
        mask_path=None,
        accepted_fields=(("door_count", "one"), ("route", "continuous")),
    )
    plan = SimpleNamespace(
        attempt=2,
        source=SimpleNamespace(
            accepted_fields=contract.accepted_fields,
            asset_id=asset_id,
            image_sha256=contract.source_sha256,
        ),
        request=SimpleNamespace(seed=42, negative_prompt="No extra doors"),
    )
    job_id = "abc123"
    runtime = root / ".vscs" / "runtime" / "comfyui"
    queue = runtime / "queues" / f"cap_correction_{job_id}.json"
    output = runtime / "jobs" / job_id / "output" / f"cap_correction_{job_id}.png"
    return Mock(), plan, contract, graph, queue, output, job_id


def _prepare(fixture):
    service, plan, contract, graph, queue, output, job_id = fixture
    return correction.prepare_managed_qwen_correction(
        service,
        plan,
        contract,
        workflow_path=graph,
        queue_path=queue,
        output_path=output,
        job_id=job_id,
    )


def test_managed_qwen_compiles_offline_candidate_edit_job(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    service, plan, contract, graph, queue, output, _job_id = fixture
    validation = Mock()
    monkeypatch.setattr(correction, "verify_spatial_contract", validation)
    result = _prepare(fixture)
    validation.assert_called_once_with(service, plan, contract)
    job = result.queue["jobs"][0]
    assert job["reference_inputs"] == [str(contract.source_path)]
    assert job["positive_prompt"] == (
        "MANDATORY reviewed door_count: one\nMANDATORY reviewed route: continuous"
    )
    assert job["negative_prompt"] == "No extra doors"
    assert job["asset_category"] == "location"
    assert result.workflow["171"]["inputs"]["queue_file"] == str(queue)
    assert result.workflow["170:169"]["inputs"]["seed"] == 42
    assert not result.execution_authorized
    assert not queue.exists()
    assert not output.exists()
    assert graph.read_text(encoding="utf-8").find("__VSCS_QUEUE_FILE__") != -1


def test_managed_qwen_rejects_mask_that_graph_cannot_condition(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(correction, "verify_spatial_contract", Mock())
    fixture[2].mask_path = tmp_path / "mask.png"
    with pytest.raises(correction.ManagedQwenCorrectionError, match="no validated mask"):
        _prepare(fixture)


def test_managed_qwen_rejects_wrong_output_root(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(correction, "verify_spatial_contract", Mock())
    service, plan, contract, graph, queue, output, job_id = fixture
    with pytest.raises(correction.ManagedQwenCorrectionError, match="not isolated"):
        correction.prepare_managed_qwen_correction(
            service,
            plan,
            contract,
            workflow_path=graph,
            queue_path=queue,
            output_path=tmp_path / output.name,
            job_id=job_id,
        )


def test_managed_qwen_refuses_workflow_drift(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(correction, "verify_spatial_contract", Mock())
    graph = fixture[3]
    data = json.loads(graph.read_text(encoding="utf-8"))
    data["170:169"]["inputs"]["latent_image"] = ["171", 0]
    graph.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RuntimeError, match="latent_image"):
        _prepare(fixture)


def test_managed_qwen_refuses_reused_runtime_output(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    monkeypatch.setattr(correction, "verify_spatial_contract", Mock())
    output = fixture[5]
    output.parent.mkdir(parents=True)
    output.write_bytes(b"already exists")
    with pytest.raises(correction.ManagedQwenCorrectionError, match="already exists"):
        _prepare(fixture)


def test_f541_degraded_final_attempt_refused_before_compilation(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path)
    fixture[1].max_attempts = 2
    fixture[1].effectiveness_warnings = (
        "Previous semantic score declined (-7).",
    )
    verification = Mock()
    monkeypatch.setattr(correction, "verify_spatial_contract", verification)
    with pytest.raises(correction.ManagedQwenCorrectionError, match="final correction"):
        _prepare(fixture)
    verification.assert_not_called()
    assert not fixture[4].exists()
    assert not fixture[5].exists()
