from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import vscs.infrastructure.production_execution.compiled_backend as compiled_module
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionExecutionLease,
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleSnapshot,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
    production_schedule_fingerprint,
)
from vscs.application.provider_execution import (
    DurableExecutionEvent,
    DurableExecutionJob,
    ProviderExecutionHandle,
    ProviderExecutionState,
)
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend
from vscs.infrastructure.production_execution.restart_recovery import (
    ComfyUIRecoveryObservation,
    ComfyUIRecoveryPresence,
)

NOW = datetime(2026, 8, 20, 13, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-16-RETRY-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-16-RETRY-001",
            revision=1,
            fingerprint="authority-20-16-retry",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=NOW,
    )


def _persist_schedule(
    backend: LocalComfyUIProductionExecutionBackend,
    task: ProductionTask,
) -> None:
    schedule = ProductionSchedule(
        production_id=task.production_id,
        assignments=(
            ProductionScheduleAssignment(
                task_id=task.task_id,
                resource_id="GPU-01",
                priority=task.priority,
                required_capabilities=tuple(task.capabilities),
            ),
        ),
        deferrals=(),
    )
    fingerprint = production_schedule_fingerprint(schedule)
    snapshot = ProductionScheduleSnapshot(
        schedule_id="PS-20-16-RETRY",
        production_id=task.production_id,
        revision=1,
        fingerprint=fingerprint,
        schedule=schedule,
        created_at=NOW,
    )
    backend.schedules.save_snapshot(snapshot)
    backend.schedules.append_review(
        ProductionScheduleReviewRecord(
            schedule_id=snapshot.schedule_id,
            production_id=snapshot.production_id,
            revision=snapshot.revision,
            fingerprint=snapshot.fingerprint,
            decision=ProductionScheduleReviewDecision.APPROVED,
            reviewed_by="human-reviewer",
            notes="Approved for retry semantics",
            reviewed_at=NOW,
        )
    )


def _durable_job(
    task: ProductionTask,
    state: ProviderExecutionState = ProviderExecutionState.QUEUED,
) -> DurableExecutionJob:
    queue_id = "PQ-PS-20-16-RETRY-R000001"
    entry_id = f"PQE-{task.task_id}"
    failure = "provider produced no output" if state is ProviderExecutionState.FAILED else None
    progress = 1.0 if state is ProviderExecutionState.COMPLETED else 0.0
    return DurableExecutionJob(
        execution_id=f"PEX-{queue_id}-{entry_id}-A001",
        production_id=task.production_id,
        task_id=task.task_id,
        queue_id=queue_id,
        entry_id=entry_id,
        resource_id="GPU-01",
        worker_id="WORKER-GPU-01",
        lease_id=f"PLEASE-{queue_id}-{entry_id}-WORKER-GPU-01",
        attempt_number=1,
        authority_fingerprint=task.authority.fingerprint,
        provider_id="LOCAL-COMFYUI-GPU-01",
        state=state,
        created_at=NOW,
        updated_at=NOW,
        provider_job_id="prompt-missing-output",
        render_request_id=f"REQ-{task.task_id}",
        workflow_id="video_production_engine_v7_1_4",
        submitted_at=NOW,
        progress=progress,
        failure_reason=failure,
        provider_metadata=(
            ("render_job_id", "COMFY-MISSING-OUTPUT"),
            ("request_id", f"REQ-{task.task_id}"),
        ),
        events=(
            DurableExecutionEvent(
                state=state,
                observed_at=NOW,
                progress=progress,
                provider_job_id="prompt-missing-output",
                failure_reason=failure,
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
    _persist_schedule(backend, task)
    return backend, task


class _NotFoundProbe:
    def observe(self, prompt_id: str) -> ComfyUIRecoveryObservation:
        return ComfyUIRecoveryObservation(
            ComfyUIRecoveryPresence.NOT_FOUND,
            prompt_id,
            "ComfyUI history and queue no longer contain the durable prompt identity.",
        )

    def completed_outputs(self, prompt_id: str):
        return ()


def test_missing_prompt_without_output_is_failed_and_retryable(monkeypatch, tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    backend.execution_jobs.repository.save(_durable_job(task))
    monkeypatch.setattr(
        compiled_module,
        "ComfyUIRestartRecoveryProbe",
        lambda _endpoint: _NotFoundProbe(),
    )

    result = backend.reconcile(task.task_id)

    assert result.state.value == "failed"
    latest = backend.execution_jobs.list_for_task(task.task_id)[-1]
    assert latest.state is ProviderExecutionState.FAILED
    assert "no production output" in (latest.failure_reason or "").casefold()
    assert not backend.has_execution(task.task_id)


def test_provider_completed_without_generated_media_is_retryable(tmp_path: Path) -> None:
    backend, task = _backend(tmp_path)
    backend.execution_jobs.repository.save(_durable_job(task, ProviderExecutionState.COMPLETED))

    assert not backend.has_execution(task.task_id)
    snapshot = backend.telemetry(task.task_id)
    assert snapshot.state.value == "failed"
    assert "without recoverable production output" in snapshot.stage.casefold()


class _RetryService:
    def __init__(self) -> None:
        self.attempt_count_seen = -1

    def submit(
        self,
        queue,
        entry_id,
        worker_id,
        render_request,
        production_package,
        *,
        lease_duration_seconds,
    ):
        entry = queue.entry(entry_id)
        assert entry is not None
        self.attempt_count_seen = entry.attempt_count
        assert self.attempt_count_seen == 1
        lease = ProductionExecutionLease(
            lease_id="PLEASE-RETRY-A002",
            queue_id=queue.queue_id,
            entry_id=entry.entry_id,
            task_id=entry.task_id,
            worker_id=worker_id,
            acquired_at=NOW,
            expires_at=NOW + timedelta(seconds=lease_duration_seconds),
            last_heartbeat_at=NOW,
        )
        handle = ProviderExecutionHandle(
            execution_id=f"PEX-{queue.queue_id}-{entry.entry_id}-A002",
            provider_id="LOCAL-COMFYUI-GPU-01",
            provider_job_id="prompt-retry-a002",
            state=ProviderExecutionState.QUEUED,
            submitted_at=NOW,
            progress=0.0,
        )
        return SimpleNamespace(
            submitted=True,
            handle=handle,
            lease=lease,
            queue=queue,
            provider=SimpleNamespace(provider_id="LOCAL-COMFYUI-GPU-01"),
            error_message=None,
        )


def test_retry_start_reconstructs_prior_attempt_before_submitting_a002(
    monkeypatch,
    tmp_path: Path,
) -> None:
    backend, task = _backend(tmp_path)
    backend.execution_jobs.repository.save(_durable_job(task, ProviderExecutionState.FAILED))
    package = backend.project_directory / "compiled.json"
    package.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        backend.package_compilation,
        "require_current",
        lambda _task: SimpleNamespace(path=package),
    )
    service = _RetryService()
    monkeypatch.setattr(
        backend,
        "_execution_service",
        lambda _task, _resource: (service, "WORKER-GPU-01"),
    )

    result = backend.start(task.task_id)

    assert service.attempt_count_seen == 1
    assert result.execution_id is not None
    assert result.execution_id.endswith("-A002")
    assert result.state.value == "submitted"
