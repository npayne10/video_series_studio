"""B.5.26F worker-only Qwen execution: no CAP database calls."""

import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import managed_qwen_worker_execution as worker


def _fixture(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    source = root / "source.png"
    source.write_bytes(b"source evidence")
    report = root / "review.json"
    report.write_bytes(b"review evidence")
    workflow = root / "qwen_api.json"
    workflow.write_bytes(b"workflow evidence")
    job_id = "job123"
    runtime = root / ".vscs" / "runtime" / "comfyui"
    output = runtime / "jobs" / job_id / "output" / f"cap_correction_{job_id}.png"
    queue = runtime / "queues" / f"cap_correction_{job_id}.json"
    contract = SimpleNamespace(
        project_root=root,
        source_path=source,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        quality_report_path=report,
        quality_report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
        workflow_path=workflow,
        workflow_sha256=hashlib.sha256(workflow.read_bytes()).hexdigest(),
        evidence_sha256="F3-contract",
        original_reference_id=1,
        correction_attempt=2,
        mask_path=None,
        verify_seal=Mock(),
    )
    job = SimpleNamespace(
        contract_sha256=contract.evidence_sha256,
        workflow_sha256=contract.workflow_sha256,
        source_sha256=contract.source_sha256,
        output_path=output,
        workflow={"171": {"class_type": "XCICQwenReferenceJobLoader", "inputs": {
            "queue_file": str(queue),
            "job_index": 0,
        }}},
        queue={"jobs": [{"reference_inputs": [str(source)], "positive_prompt": "reviewed CAP"}]},
    )
    return contract, job, queue, output


def _png():
    image = io.BytesIO()
    Image.new("RGB", (256, 256), "gray").save(image, format="PNG")
    return image.getvalue()


def test_worker_one_submission_no_cap_db(tmp_path, monkeypatch):
    contract, job, queue, output = _fixture(tmp_path)
    reserve = Mock()
    monkeypatch.setattr(worker, "reserve_guided_edit_attempt", reserve)

    class Provider:
        def __init__(self):
            self.healthcheck = Mock()
            self.validate_nodes = Mock()
            self.submit = Mock(return_value="prompt-one")

        def wait(self, prompt_id, timeout_seconds):
            assert prompt_id == "prompt-one"
            assert timeout_seconds == 3600.0
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(_png())
            return {"status": {"completed": True}}

    provider = Provider()
    result = worker.execute_prepared_managed_qwen_edit(
        contract, job, operator_confirmed=True, client=provider
    )
    reserve.assert_called_once_with(contract)
    provider.submit.assert_called_once_with(job.workflow)
    assert queue.is_file()
    assert result.content == _png()
    assert result.prompt_id == "prompt-one"
    assert result.contract_sha256 == contract.evidence_sha256
    contract.verify_seal.assert_called()


def test_worker_rejects_no_consent_before_any_io(tmp_path):
    contract, job, queue, output = _fixture(tmp_path)
    provider = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    with pytest.raises(worker.GuidedEditExecutionError, match="confirmation"):
        worker.execute_prepared_managed_qwen_edit(
            contract, job, operator_confirmed=False, client=provider
        )
    provider.submit.assert_not_called()
    provider.healthcheck.assert_not_called()


def test_worker_refuses_modified_source_before_submission(tmp_path, monkeypatch):
    contract, job, queue, output = _fixture(tmp_path)
    contract.source_path.write_bytes(b"changed")
    client = SimpleNamespace(submit=Mock(), healthcheck=Mock())
    reserve = Mock()
    monkeypatch.setattr(worker, "reserve_guided_edit_attempt", reserve)
    with pytest.raises(worker.GuidedEditExecutionError, match="evidence changed"):
        worker.execute_prepared_managed_qwen_edit(
            contract, job, operator_confirmed=True, client=client
        )
    reserve.assert_not_called()
    client.submit.assert_not_called()


def test_worker_unknown_post_outcome_keeps_reservation(tmp_path, monkeypatch):
    contract, job, queue, output = _fixture(tmp_path)
    reserve = Mock()
    monkeypatch.setattr(worker, "reserve_guided_edit_attempt", reserve)
    client = SimpleNamespace(
        submit=Mock(side_effect=RuntimeError("POST result unknown")),
        healthcheck=Mock(),
        validate_nodes=Mock(),
    )
    with pytest.raises(RuntimeError, match="unknown"):
        worker.execute_prepared_managed_qwen_edit(
            contract, job, operator_confirmed=True, client=client
        )
    reserve.assert_called_once_with(contract)
    client.submit.assert_called_once()
    assert queue.is_file()
