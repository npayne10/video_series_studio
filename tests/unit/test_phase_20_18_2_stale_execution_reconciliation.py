from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from vscs.application.production_execution import GovernedRetryOverrideState
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    DurableExecutionEvent,
    DurableExecutionJob,
    ProviderExecutionState,
)
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend

NOW = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-18-2-STALE-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-18-2-STALE-001",
            revision=1,
            fingerprint="authority-20-18-2-stale",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=NOW,
    )


def _job(task: ProductionTask, attempt: int, state: ProviderExecutionState) -> DurableExecutionJob:
    observed = NOW + timedelta(minutes=attempt)
    queue_id = "PQ-STALE-TEST"
    entry_id = f"PQE-{task.task_id}"
    prompt = f"prompt-{attempt:03d}"
    failure_reason = f"attempt {attempt} failed" if state is ProviderExecutionState.FAILED else None
    return DurableExecutionJob(
        execution_id=f"PEX-{queue_id}-{entry_id}-A{attempt:03d}",
        production_id=task.production_id,
        task_id=task.task_id,
        queue_id=queue_id,
        entry_id=entry_id,
        resource_id="GPU-01",
        worker_id="WORKER-GPU-01",
        lease_id=f"PLEASE-{attempt:03d}",
        attempt_number=attempt,
        authority_fingerprint=task.authority.fingerprint,
        provider_id="LOCAL-COMFYUI-GPU-01",
        state=state,
        created_at=observed,
        updated_at=observed,
        provider_job_id=prompt,
        submitted_at=observed,
        progress=0.0 if state is ProviderExecutionState.FAILED else 0.5,
        failure_reason=failure_reason,
        events=(
            DurableExecutionEvent(
                state=state,
                observed_at=observed,
                progress=0.0 if state is ProviderExecutionState.FAILED else 0.5,
                provider_job_id=prompt,
                failure_reason=failure_reason,
            ),
        ),
    )


def _backend(tmp_path: Path) -> tuple[LocalComfyUIProductionExecutionBackend, ProductionTask]:
    project = tmp_path / "project"
    output = tmp_path / "comfyui-output"
    project.mkdir()
    output.mkdir()
    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=output,
    )
    task = _task()
    backend.tasks.save(task)
    return backend, task


def test_retry_status_reconciles_superseded_nonterminal_attempt_and_unblocks_retry(
    tmp_path: Path,
) -> None:
    backend, task = _backend(tmp_path)
    jobs = (
        _job(task, 1, ProviderExecutionState.FAILED),
        _job(task, 2, ProviderExecutionState.RUNNING),
        _job(task, 3, ProviderExecutionState.FAILED),
        _job(task, 4, ProviderExecutionState.FAILED),
    )
    for job in jobs:
        backend.execution_jobs.repository.save(job)

    status = backend.retry_override_status_for_profile(task.task_id, profile="production")

    assert status.state is GovernedRetryOverrideState.ELIGIBLE
    assert status.attempts_recorded == 4
    repaired = backend.execution_jobs.require(jobs[1].execution_id)
    assert repaired.state is ProviderExecutionState.FAILED
    assert repaired.failure_reason is not None
    assert "later governed execution A004 already exists" in repaired.failure_reason


def test_retry_status_keeps_latest_nonterminal_attempt_blocking(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    backend.execution_jobs.repository.save(_job(task, 1, ProviderExecutionState.FAILED))
    latest = _job(task, 2, ProviderExecutionState.RUNNING)
    backend.execution_jobs.repository.save(latest)

    status = backend.retry_override_status_for_profile(task.task_id, profile="production")

    assert status.state is GovernedRetryOverrideState.BLOCKED
    preserved = backend.execution_jobs.require(latest.execution_id)
    assert preserved.state is ProviderExecutionState.RUNNING
    assert preserved.failure_reason is None


def test_execution_gate_reconciles_superseded_nonterminal_history(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    jobs = (
        _job(task, 1, ProviderExecutionState.FAILED),
        _job(task, 2, ProviderExecutionState.RUNNING),
        _job(task, 3, ProviderExecutionState.FAILED),
        _job(task, 4, ProviderExecutionState.FAILED),
    )
    for job in jobs:
        backend.execution_jobs.repository.save(job)

    assert backend.has_execution_for_profile(task.task_id, profile="production")
    repaired = backend.execution_jobs.require(jobs[1].execution_id)
    assert repaired.state is ProviderExecutionState.FAILED
