"""Q3.1.3.5.8a disposable single-span authorization, never ComfyUI traffic."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceCoordinator,
    H3IsolatedAcceptanceError,
)
from vscs.infrastructure.production_execution.minimax_h3_automated_execution import (
    MiniMaxH3AutomatedExecutionPreflight,
)


def _report(*, task_id: str = "TASK-TEST", spans: int = 1):
    return MiniMaxH3AutomatedExecutionPreflight(
        task_id=task_id,
        shot_id="SHT-TEST",
        package_fingerprint="package-fp",
        plan_id="H3-PLAN",
        plan_fingerprint="plan-fp",
        span_job_ids=tuple(f"JOB-{i}" for i in range(spans)),
        prompt_fingerprints=tuple(f"prompt-{i}" for i in range(spans)),
        reference_slot_fingerprints=tuple(f"refs-{i}" for i in range(spans)),
        prompt_validation_fingerprints=tuple(f"validation-{i}" for i in range(spans)),
        workflow_fingerprints=tuple(f"workflow-{i}" for i in range(spans)),
        model_config_fingerprints=tuple(f"model-{i}" for i in range(spans)),
        provider_profile_id="minimax-h3-ref2va-v1",
        provider_profile_fingerprint="policy-fp",
        execution_adapter_id="minimax_h3_automated_execution",
    )


def _coordinator(tmp_path: Path, report=None):
    project = tmp_path / "disposable" / "project"
    output = project / "acceptance-output"
    output.mkdir(parents=True)
    (tmp_path / "disposable" / ".vscs_h3_disposable_acceptance").write_text(
        "Q3.1.3.5.8", encoding="utf-8"
    )
    seen = []
    current = [report or _report()]

    def dry_run(task):
        seen.append(task)
        return current[0]

    service = SimpleNamespace(
        project_directory=project,
        dry_run=dry_run,
        execute=lambda *args, **kwargs: pytest.fail("No live execution allowed in 8a"),
    )
    coordinator = H3IsolatedAcceptanceCoordinator(
        service, acceptance_root=tmp_path / "disposable",
        project_root=project, output_root=output,
    )
    return coordinator, current, seen


def test_prepare_single_span_is_read_only_and_no_submission(tmp_path: Path):
    coordinator, _, seen = _coordinator(tmp_path)
    prepared = coordinator.prepare("TASK-TEST")
    assert prepared.task_id == "TASK-TEST"
    assert prepared.report.span_count == 1
    assert seen == ["TASK-TEST"]
    assert tuple(coordinator.output_root.iterdir()) == ()


def test_reject_multiple_spans(tmp_path: Path):
    coordinator, _, _ = _coordinator(tmp_path, _report(spans=2))
    with pytest.raises(H3IsolatedAcceptanceError, match="exactly one"):
        coordinator.prepare("TASK-TEST")


def test_reject_wrong_task(tmp_path: Path):
    coordinator, _, _ = _coordinator(tmp_path, _report(task_id="OTHER"))
    with pytest.raises(H3IsolatedAcceptanceError, match="selected task"):
        coordinator.prepare("TASK-TEST")


def test_explicit_authorization_is_one_use_and_rechecks_freshness(tmp_path: Path):
    coordinator, _, seen = _coordinator(tmp_path)
    prepared = coordinator.prepare("TASK-TEST")
    token = coordinator.authorize_once(
        prepared, operator_confirmed=True, expected_plan_fingerprint="plan-fp"
    )
    assert coordinator.consume_authorization(token) == prepared
    assert seen == ["TASK-TEST", "TASK-TEST"]
    with pytest.raises(H3IsolatedAcceptanceError, match="consumed"):
        coordinator.consume_authorization(token)


def test_authorization_refuses_stale_plan_and_consumes_capability(tmp_path: Path):
    coordinator, current, _ = _coordinator(tmp_path)
    prepared = coordinator.prepare("TASK-TEST")
    token = coordinator.authorize_once(
        prepared, operator_confirmed=True, expected_plan_fingerprint="plan-fp"
    )
    current[0] = replace(current[0], package_fingerprint="changed")
    with pytest.raises(H3IsolatedAcceptanceError, match="stale"):
        coordinator.consume_authorization(token)
    with pytest.raises(H3IsolatedAcceptanceError, match="consumed"):
        coordinator.consume_authorization(token)


@pytest.mark.parametrize("confirmed,fingerprint", [(False, "plan-fp"), (True, "wrong")])
def test_authorization_requires_operator_and_exact_fingerprint(
    tmp_path: Path, confirmed: bool, fingerprint: str
):
    coordinator, _, _ = _coordinator(tmp_path)
    prepared = coordinator.prepare("TASK-TEST")
    with pytest.raises(H3IsolatedAcceptanceError):
        coordinator.authorize_once(
            prepared, operator_confirmed=confirmed, expected_plan_fingerprint=fingerprint
        )


def test_reject_outside_project_or_other_service_project(tmp_path: Path):
    coordinator, _, _ = _coordinator(tmp_path)
    foreign = tmp_path / "VSCS TSR2"
    foreign.mkdir()
    with pytest.raises(H3IsolatedAcceptanceError, match="child"):
        H3IsolatedAcceptanceCoordinator(
            coordinator.service, acceptance_root=tmp_path / "disposable",
            project_root=foreign, output_root=foreign,
        )
    with pytest.raises(H3IsolatedAcceptanceError, match="not bound"):
        H3IsolatedAcceptanceCoordinator(
            SimpleNamespace(project_directory=foreign),
            acceptance_root=tmp_path / "disposable",
            project_root=coordinator.project_root, output_root=coordinator.output_root,
        )


def test_reject_output_escape(tmp_path: Path):
    coordinator, _, _ = _coordinator(tmp_path)
    with pytest.raises(H3IsolatedAcceptanceError, match="confined"):
        H3IsolatedAcceptanceCoordinator(
            coordinator.service, acceptance_root=tmp_path / "disposable",
            project_root=coordinator.project_root, output_root=tmp_path,
        )
