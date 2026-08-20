from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    GovernedRetryOverrideState,
    ProductionExecutionError,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEngine,
    ProductionQueueEntry,
    ProductionQueueState,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    DurableExecutionEvent,
    DurableExecutionJob,
    ProviderExecutionState,
)
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend

NOW = datetime(2026, 8, 20, 14, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-16-1-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-16-1-001",
            revision=1,
            fingerprint="authority-20-16-1",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=NOW,
    )


def _failed_job(task: ProductionTask, attempt: int) -> DurableExecutionJob:
    observed = NOW + timedelta(minutes=attempt)
    queue_id = "PQ-20-16-1"
    entry_id = f"PQE-{task.task_id}"
    prompt = f"prompt-a{attempt:03d}"
    reason = f"attempt {attempt} produced no authoritative output"
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
        state=ProviderExecutionState.FAILED,
        created_at=observed,
        updated_at=observed,
        provider_job_id=prompt,
        render_request_id=f"REQ-{attempt:03d}",
        workflow_id="video_production_engine_v7_1_4",
        submitted_at=observed,
        progress=0.0,
        failure_reason=reason,
        events=(
            DurableExecutionEvent(
                state=ProviderExecutionState.FAILED,
                observed_at=observed,
                progress=0.0,
                provider_job_id=prompt,
                failure_reason=reason,
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
    for attempt in range(1, 4):
        backend.execution_jobs.repository.save(_failed_job(task, attempt))
    return backend, task


def _queue(task: ProductionTask) -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-20-16-1",
        production_id=task.production_id,
        schedule_id="PS-20-16-1",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=(
            ProductionQueueEntry(
                entry_id=f"PQE-{task.task_id}",
                task_id=task.task_id,
                resource_id="GPU-01",
                task_type=task.task_type,
                state=ProductionQueueState.READY,
                priority=ProductionTaskPriority.NORMAL,
                maximum_attempts=task.attempt_policy.maximum_attempts,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def test_exhausted_task_requires_human_retry_override(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)

    status = backend.retry_override_status(task.task_id)

    assert status.state is GovernedRetryOverrideState.ELIGIBLE
    assert status.attempts_recorded == 3
    assert status.base_maximum_attempts == 3
    assert status.effective_maximum_attempts == 3
    assert status.next_attempt_number == 4
    assert backend.has_execution(task.task_id)


def test_human_override_grants_exactly_one_durable_additional_attempt(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)

    status = backend.authorize_retry(
        task.task_id,
        authorized_by="Neill Payne",
        reason="ComfyUI completed without producing a usable output file.",
    )

    assert status.state is GovernedRetryOverrideState.AUTHORIZED
    assert status.effective_maximum_attempts == 4
    assert status.next_attempt_number == 4
    assert status.latest_authorization is not None
    assert status.latest_authorization.authorized_attempt_number == 4
    assert status.latest_authorization.authorized_by == "Neill Payne"
    assert not backend.has_execution(task.task_id)
    history = backend._retry_attempt_history(
        task,
        backend.execution_jobs.list_for_task(task.task_id),
    )
    assert len(history) == 3

    retry_store = (
        backend.project_directory
        / ".vscs"
        / "provider_executions"
        / "retry_overrides"
        / "authorizations.json"
    )
    assert retry_store.is_file()
    assert not (
        backend.project_directory / ".vscs" / "provider_executions" / "retry_overrides.json"
    ).exists()

    restarted = LocalComfyUIProductionExecutionBackend(
        backend.project_directory,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=tmp_path / "comfyui-output",
    )
    restored = restarted.retry_override_status(task.task_id)
    assert restored.state is GovernedRetryOverrideState.AUTHORIZED
    assert restored.effective_maximum_attempts == 4


def test_authorized_retry_widens_runtime_queue_for_a004(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    backend.authorize_retry(
        task.task_id,
        authorized_by="operator",
        reason="Authorize A004 after three outputless provider attempts.",
    )
    history = backend._retry_attempt_history(
        task,
        backend.execution_jobs.list_for_task(task.task_id),
    )

    queue = backend._queue_with_attempt_history(_queue(task), task.task_id, history)
    entry = queue.entry_for_task(task.task_id)
    assert entry is not None
    assert entry.maximum_attempts == 4
    assert entry.attempt_count == 3

    queue = ProductionQueueEngine().claim(queue, entry.entry_id, "WORKER-GPU-01", now=NOW)
    queue = ProductionQueueEngine().start(queue, entry.entry_id, now=NOW)
    started = queue.entry(entry.entry_id)
    assert started is not None
    assert started.attempt_count == 4
    assert started.attempts[-1].attempt_number == 4


def test_unused_override_cannot_be_stacked(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    backend.authorize_retry(
        task.task_id,
        authorized_by="operator",
        reason="Authorize one additional diagnostic production attempt.",
    )

    with pytest.raises(ProductionExecutionError, match="authorizes attempt A004"):
        backend.authorize_retry(
            task.task_id,
            authorized_by="operator",
            reason="Attempt to stack another override before A004 exists.",
        )


def test_failed_authorized_attempt_requires_new_human_override(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    backend.authorize_retry(
        task.task_id,
        authorized_by="operator",
        reason="Authorize A004.",
    )
    backend.execution_jobs.repository.save(_failed_job(task, 4))

    status = backend.retry_override_status(task.task_id)

    assert status.state is GovernedRetryOverrideState.ELIGIBLE
    assert status.attempts_recorded == 4
    assert status.effective_maximum_attempts == 4
    assert status.next_attempt_number == 5
    assert backend.has_execution(task.task_id)


def test_legacy_retry_override_store_is_migrated_out_of_execution_job_directory(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    output = tmp_path / "comfyui-output"
    legacy = project / ".vscs" / "provider_executions" / "retry_overrides.json"
    legacy.parent.mkdir(parents=True)
    output.mkdir()
    legacy.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "authorizations": [],
            }
        ),
        encoding="utf-8",
    )

    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=output,
    )

    assert not legacy.exists()
    assert (
        project / ".vscs" / "provider_executions" / "retry_overrides" / "authorizations.json"
    ).is_file()
    assert backend.execution_jobs.list_active() == ()
