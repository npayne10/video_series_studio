from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vscs.application.production_execution import GovernedRetryOverrideState
from vscs.application.provider_execution import ProviderExecutionState
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend

from .test_phase_20_16_2_profile_scoped_execution_attempts import (
    _backend,
    _failed_job,
)


def _running_job(task, attempt: int):  # type: ignore[no-untyped-def]
    failed = _failed_job(task, attempt)
    running_event = replace(
        failed.events[0],
        state=ProviderExecutionState.RUNNING,
        failure_reason=None,
    )
    return replace(
        failed,
        state=ProviderExecutionState.RUNNING,
        failure_reason=None,
        progress=0.5,
        events=(running_event,),
    )


def test_refresh_reconciliation_fails_superseded_nonterminal_attempt_and_unblocks_retry(
    tmp_path: Path,
) -> None:
    backend, task = _backend(tmp_path)
    assert isinstance(backend, LocalComfyUIProductionExecutionBackend)

    jobs = (
        _failed_job(task, 1),
        _running_job(task, 2),
        _failed_job(task, 3),
        _failed_job(task, 4),
    )
    for job in jobs:
        backend.execution_jobs.repository.save(job)

    before = backend.retry_override_status_for_profile(task.task_id, profile="production")
    assert before.state is GovernedRetryOverrideState.BLOCKED
    assert before.attempts_recorded == 4

    result = backend.reconcile_for_profile(task.task_id, profile="production")

    assert result.state.value == "failed"
    repaired = backend.execution_jobs.require(jobs[1].execution_id)
    assert repaired.state is ProviderExecutionState.FAILED
    assert repaired.failure_reason is not None
    assert "later governed execution A004 already exists" in repaired.failure_reason

    after = backend.retry_override_status_for_profile(task.task_id, profile="production")
    assert after.state is GovernedRetryOverrideState.ELIGIBLE
    assert after.attempts_recorded == 4


def test_stale_reconciliation_never_changes_latest_nonterminal_attempt(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    latest = _running_job(task, 2)
    backend.execution_jobs.repository.save(_failed_job(task, 1))
    backend.execution_jobs.repository.save(latest)

    backend._fail_superseded_nonterminal_jobs(task.task_id)

    preserved = backend.execution_jobs.require(latest.execution_id)
    assert preserved.state is ProviderExecutionState.RUNNING
    assert preserved.failure_reason is None
