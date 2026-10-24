"""Q3.1.3.5.8c: offline integration of readiness, provenance and MP4 evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.test_h3_isolated_live_generation_acceptance import _coordinator
from tests.test_h3_isolated_output_evidence_acceptance import _valid_video
from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceError,
)


def _provider(prepared):
    return {
        "job_id": prepared.report.span_job_ids[0],
        "workflow_fingerprint": prepared.report.workflow_fingerprints[0],
        "model_config_fingerprint": prepared.report.model_config_fingerprints[0],
        "prompt_id": "synthetic-prompt-no-network",
    }


def _fixture(tmp_path: Path):
    coordinator, current, seen = _coordinator(tmp_path)
    prepared = coordinator.prepare("TASK-TEST")
    output = _valid_video(coordinator.output_root)
    evidence = coordinator.project_root / "evidence"
    evidence.mkdir()
    return coordinator, prepared, current, seen, output, evidence


def _finish(coordinator, prepared, output, evidence, provider=None, run_id="RUN-001"):
    return coordinator.validate_completed_output(
        prepared,
        output_path=output,
        expected_frames=12,
        expected_fps=24,
        evidence_root=evidence,
        run_id=run_id,
        provider_evidence=provider if provider is not None else _provider(prepared),
    )


def test_integrated_offline_acceptance_creates_unreviewed_evidence(tmp_path: Path):
    coordinator, prepared, _, seen, output, evidence = _fixture(tmp_path)
    before = output.read_bytes()
    validated, path = _finish(coordinator, prepared, output, evidence)
    report = json.loads(path.read_text(encoding="utf-8"))
    assert validated.sha256 == report["output"]["sha256"]
    assert report["plan_fingerprint"] == prepared.plan_fingerprint
    assert report["qc_status"] == "unreviewed"
    assert report["approved"] is False
    assert output.read_bytes() == before
    assert seen == ["TASK-TEST"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("job_id", "other-job"),
        ("workflow_fingerprint", "other-workflow"),
        ("model_config_fingerprint", "other-model"),
        ("prompt_id", ""),
    ],
)
def test_integrated_provenance_mismatch_blocks_before_evidence(
    tmp_path: Path, key: str, value: str
):
    coordinator, prepared, _, _, output, evidence = _fixture(tmp_path)
    provider = _provider(prepared)
    provider[key] = value
    with pytest.raises(H3IsolatedAcceptanceError, match="provider evidence"):
        _finish(coordinator, prepared, output, evidence, provider=provider)
    assert list(evidence.iterdir()) == []


def test_integrated_output_escape_blocks_without_report(tmp_path: Path):
    coordinator, prepared, _, _, _, evidence = _fixture(tmp_path)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    with pytest.raises(H3IsolatedAcceptanceError, match="escapes"):
        _finish(coordinator, prepared, outside, evidence)
    assert list(evidence.iterdir()) == []


def test_integrated_stale_preparation_blocks_without_report(tmp_path: Path):
    coordinator, prepared, _, _, output, evidence = _fixture(tmp_path)
    wrong = replace(prepared, output_root=tmp_path)
    with pytest.raises(H3IsolatedAcceptanceError, match="preparation"):
        _finish(coordinator, wrong, output, evidence)
    assert list(evidence.iterdir()) == []


def test_integrated_duplicate_run_fails_closed(tmp_path: Path):
    coordinator, prepared, _, _, output, evidence = _fixture(tmp_path)
    _, path = _finish(coordinator, prepared, output, evidence)
    existing = path.read_bytes()
    with pytest.raises(H3IsolatedAcceptanceError, match="already exists"):
        _finish(coordinator, prepared, output, evidence)
    assert path.read_bytes() == existing


def test_integrated_wrong_frames_blocks(tmp_path: Path):
    coordinator, prepared, _, _, output, evidence = _fixture(tmp_path)
    with pytest.raises(H3IsolatedAcceptanceError, match="frame count"):
        coordinator.validate_completed_output(
            prepared,
            output_path=output,
            expected_frames=13,
            expected_fps=24,
            evidence_root=evidence,
            run_id="RUN-001",
            provider_evidence=_provider(prepared),
        )
    assert list(evidence.iterdir()) == []
