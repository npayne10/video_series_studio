"""Q3.1.3.5.8d: live entrypoint stays operator-only and fail-closed.

No test in this file makes a real ComfyUI HTTP request.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_h3_isolated_full_integration_acceptance import _fixture, _provider
from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceError,
)


def test_missing_live_authorization_blocks_before_provider(tmp_path: Path):
    coordinator, _, _, seen, _, evidence = _fixture(tmp_path)
    with pytest.raises(H3IsolatedAcceptanceError, match="authorization"):
        coordinator.execute_single_authorized_run(
            "invalid",
            run_id="RUN-001",
            evidence_root=evidence,
            expected_frames=12,
            expected_fps=24,
        )
    assert seen == ["TASK-TEST"]


def test_live_execution_refuses_non_governed_orchestrator(tmp_path: Path):
    coordinator, prepared, _, seen, _, evidence = _fixture(tmp_path)
    token = coordinator.authorize_once(
        prepared, operator_confirmed=True, expected_plan_fingerprint=prepared.plan_fingerprint
    )
    with pytest.raises(H3IsolatedAcceptanceError, match="governed orchestration"):
        coordinator.execute_single_authorized_run(
            token,
            run_id="RUN-001",
            evidence_root=evidence,
            expected_frames=12,
            expected_fps=24,
        )
    assert seen == ["TASK-TEST", "TASK-TEST"]
    with pytest.raises(H3IsolatedAcceptanceError, match="consumed"):
        coordinator.consume_authorization(token)


def test_integrated_report_persists_provider_provenance_without_approval(tmp_path: Path):
    coordinator, prepared, _, _, output, evidence = _fixture(tmp_path)
    provider_evidence = _provider(prepared)
    _, report_path = coordinator.validate_completed_output(
        prepared,
        output_path=output,
        expected_frames=12,
        expected_fps=24,
        evidence_root=evidence,
        run_id="RUN-001",
        provider_evidence=provider_evidence,
    )
    import json

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["provider_provenance"]["job_id"] == prepared.report.span_job_ids[0]
    assert report["provider_provenance"]["prompt_id"] == "synthetic-prompt-no-network"
    assert report["qc_status"] == "unreviewed"
    assert report["approved"] is False
