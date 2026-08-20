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

NOW = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-16-2-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-16-2-001",
            revision=1,
            fingerprint="authority-20-16-2",
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
    queue_id = "PQ-PROFILE-TEST"
    entry_id = f"PQE-{task.task_id}"
    prompt = f"prompt-{attempt:03d}"
    reason = f"attempt {attempt} failed"
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
    return backend, task


def test_legacy_attempts_are_production_and_do_not_consume_preview_or_master(
    tmp_path: Path,
) -> None:
    backend, task = _backend(tmp_path)
    for attempt in range(1, 4):
        backend.execution_jobs.repository.save(_failed_job(task, attempt))

    production = backend.retry_override_status_for_profile(task.task_id, profile="production")
    preview = backend.retry_override_status_for_profile(task.task_id, profile="preview")
    master = backend.retry_override_status_for_profile(task.task_id, profile="master")

    assert production.state is GovernedRetryOverrideState.ELIGIBLE
    assert production.attempts_recorded == 3
    assert preview.state is GovernedRetryOverrideState.NOT_REQUIRED
    assert preview.attempts_recorded == 0
    assert preview.effective_maximum_attempts == 3
    assert master.state is GovernedRetryOverrideState.NOT_REQUIRED
    assert master.attempts_recorded == 0
    assert backend.has_execution_for_profile(task.task_id, profile="production")
    assert not backend.has_execution_for_profile(task.task_id, profile="preview")
    assert not backend.has_execution_for_profile(task.task_id, profile="master")


def test_profile_assignments_keep_independent_three_attempt_budgets(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    for attempt in range(1, 7):
        job = _failed_job(task, attempt)
        backend.execution_jobs.repository.save(job)
        if attempt >= 4:
            backend.execution_profiles.assign(job.execution_id, task.task_id, "preview")

    production = backend.retry_override_status_for_profile(task.task_id, profile="production")
    preview = backend.retry_override_status_for_profile(task.task_id, profile="preview")
    master = backend.retry_override_status_for_profile(task.task_id, profile="master")

    assert production.state is GovernedRetryOverrideState.ELIGIBLE
    assert production.attempts_recorded == 3
    assert preview.state is GovernedRetryOverrideState.ELIGIBLE
    assert preview.attempts_recorded == 3
    assert master.state is GovernedRetryOverrideState.NOT_REQUIRED
    assert master.attempts_recorded == 0


def test_retry_override_is_scoped_to_only_one_profile(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    for attempt in range(1, 7):
        job = _failed_job(task, attempt)
        backend.execution_jobs.repository.save(job)
        if attempt >= 4:
            backend.execution_profiles.assign(job.execution_id, task.task_id, "preview")

    preview = backend.authorize_retry_for_profile(
        task.task_id,
        profile="preview",
        authorized_by="operator",
        reason="Allow one more Preview diagnostic render.",
    )
    production = backend.retry_override_status_for_profile(task.task_id, profile="production")

    assert preview.state is GovernedRetryOverrideState.AUTHORIZED
    assert preview.attempts_recorded == 3
    assert preview.effective_maximum_attempts == 4
    assert production.state is GovernedRetryOverrideState.ELIGIBLE
    assert production.effective_maximum_attempts == 3
    assert preview.latest_authorization is not None
    assert (
        backend.retry_profiles.profile_for_authorization(
            preview.latest_authorization.authorization_id
        )
        == "preview"
    )


def test_legacy_retry_override_defaults_to_production_profile(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    for attempt in range(1, 4):
        backend.execution_jobs.repository.save(_failed_job(task, attempt))

    backend.authorize_retry(
        task.task_id,
        authorized_by="operator",
        reason="Legacy production override.",
    )

    production = backend.retry_override_status_for_profile(task.task_id, profile="production")
    preview = backend.retry_override_status_for_profile(task.task_id, profile="preview")

    assert production.state is GovernedRetryOverrideState.AUTHORIZED
    assert production.effective_maximum_attempts == 4
    assert preview.state is GovernedRetryOverrideState.NOT_REQUIRED
    assert preview.effective_maximum_attempts == 3


def test_execution_profile_assignment_survives_restart(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    job = _failed_job(task, 1)
    backend.execution_jobs.repository.save(job)
    backend.execution_profiles.assign(job.execution_id, task.task_id, "master")

    restarted = LocalComfyUIProductionExecutionBackend(
        backend.project_directory,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=tmp_path / "comfyui-output",
    )

    assert restarted.execution_profiles.profile_for_execution(job.execution_id) == "master"
    master = restarted.retry_override_status_for_profile(task.task_id, profile="master")
    production = restarted.retry_override_status_for_profile(task.task_id, profile="production")
    assert master.attempts_recorded == 1
    assert production.attempts_recorded == 0
