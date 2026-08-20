from datetime import UTC, datetime
from pathlib import Path

import vscs.infrastructure.production_execution.compiled_backend as compiled_module
from vscs.application.production_execution.recovery import (
    RestartRecoveryLeaseManager,
    RestartRecoveryQueueAdopter,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueAttempt,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleSnapshot,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    production_schedule_fingerprint,
)
from vscs.application.provider_execution import (
    DurableExecutionEvent,
    DurableExecutionJob,
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionState,
)
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend
from vscs.infrastructure.production_execution.restart_recovery import (
    ComfyUIRecoveryObservation,
    ComfyUIRecoveryPresence,
    ComfyUIRestartRecoveryProbe,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-16-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-16-001",
            revision=1,
            fingerprint="authority-20-16",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=NOW,
    )


def _queue(task: ProductionTask) -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-PS-20-16-R000001",
        production_id=task.production_id,
        schedule_id="PS-20-16",
        schedule_revision=1,
        schedule_fingerprint="schedule-20-16",
        entries=(
            ProductionQueueEntry(
                entry_id=f"PQE-{task.task_id}",
                task_id=task.task_id,
                resource_id="GPU-01",
                task_type=task.task_type,
                state=ProductionQueueState.READY,
                priority=task.priority,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def test_restart_adoption_uses_fresh_recovery_lease_identity() -> None:
    task = _task()
    queue = _queue(task)
    worker = ProductionWorker(
        worker_id="WORKER-GPU-01",
        resource_id="GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
    )
    attempts = (
        ProductionQueueAttempt(
            attempt_number=1,
            worker_id=worker.worker_id,
            started_at=NOW,
        ),
    )
    leases = RestartRecoveryLeaseManager()

    adoption = RestartRecoveryQueueAdopter(leases).adopt(
        queue,
        task,
        worker,
        attempts,
        lease_duration_seconds=120.0,
        now=NOW,
    )

    recovered = adoption.queue.entry_for_task(task.task_id)
    assert recovered is not None
    assert recovered.state is ProductionQueueState.RUNNING
    assert recovered.attempts == attempts
    assert recovered.claimed_by == worker.worker_id
    assert adoption.lease.lease_id.startswith("PRLEASE-")
    assert (
        adoption.lease.lease_id != f"PLEASE-{queue.queue_id}-PQE-{task.task_id}-{worker.worker_id}"
    )


class _RecoveryClient:
    def __init__(self, *, history=None, queue=None) -> None:
        self._history = history
        self._queue = queue or {"queue_running": [], "queue_pending": []}

    def history(self, prompt_id: str):
        return self._history

    def queue(self):
        return self._queue


def test_comfyui_recovery_probe_classifies_running_and_completed_outputs() -> None:
    running = ComfyUIRestartRecoveryProbe(
        "http://127.0.0.1:8188",
        client=_RecoveryClient(queue={"queue_running": [[0, "prompt-1"]], "queue_pending": []}),
    ).observe("prompt-1")
    assert running.presence is ComfyUIRecoveryPresence.RUNNING

    history = {
        "status": {"completed": True, "status_str": "success"},
        "outputs": {
            "save": {
                "videos": [
                    {
                        "filename": "clip.mp4",
                        "subfolder": "Xorix/Production",
                        "type": "output",
                    }
                ]
            }
        },
    }
    probe = ComfyUIRestartRecoveryProbe(
        "http://127.0.0.1:8188",
        client=_RecoveryClient(history=history),
    )
    completed = probe.observe("prompt-1")
    outputs = probe.completed_outputs("prompt-1")

    assert completed.presence is ComfyUIRecoveryPresence.COMPLETED
    assert len(outputs) == 1
    assert outputs[0].relative_path == "Xorix/Production/clip.mp4"
    assert outputs[0].media_kind == "production_video"


def _persist_schedule(
    backend: LocalComfyUIProductionExecutionBackend, task: ProductionTask
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
        schedule_id="PS-20-16",
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
            notes="Approved for recovery test",
            reviewed_at=NOW,
        )
    )


def _durable_job(task: ProductionTask) -> DurableExecutionJob:
    queue_id = "PQ-PS-20-16-R000001"
    entry_id = f"PQE-{task.task_id}"
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
        state=ProviderExecutionState.QUEUED,
        created_at=NOW,
        updated_at=NOW,
        provider_job_id="prompt-20-16",
        render_request_id=f"REQ-{task.task_id}",
        workflow_id="video_production_engine_v7_1_4",
        submitted_at=NOW,
        progress=0.0,
        provider_metadata=(
            ("render_job_id", "COMFY-20-16"),
            ("request_id", f"REQ-{task.task_id}"),
        ),
        events=(
            DurableExecutionEvent(
                state=ProviderExecutionState.QUEUED,
                observed_at=NOW,
                progress=0.0,
                provider_job_id="prompt-20-16",
            ),
        ),
    )


class _Adapter:
    provider_id = "LOCAL-COMFYUI-GPU-01"

    def __init__(self, terminal: bool) -> None:
        self.terminal = terminal

    def restore_handle(self, job: DurableExecutionJob) -> ProviderExecutionHandle:
        assert job.provider_job_id is not None
        assert job.submitted_at is not None
        return ProviderExecutionHandle(
            execution_id=job.execution_id,
            provider_id=job.provider_id,
            provider_job_id=job.provider_job_id,
            state=job.state,
            submitted_at=job.submitted_at,
            progress=job.progress,
            metadata=job.provider_metadata,
        )

    def monitor(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        return ProviderExecutionHandle(
            execution_id=handle.execution_id,
            provider_id=handle.provider_id,
            provider_job_id=handle.provider_job_id,
            state=(
                ProviderExecutionState.COMPLETED
                if self.terminal
                else ProviderExecutionState.RUNNING
            ),
            submitted_at=handle.submitted_at,
            progress=1.0 if self.terminal else 0.5,
            metadata=handle.metadata,
        )


class _Adapters:
    def __init__(self, adapter: _Adapter) -> None:
        self.adapter = adapter

    def require(self, provider_id: str) -> _Adapter:
        assert provider_id == self.adapter.provider_id
        return self.adapter


class _Service:
    def __init__(self, runtime: ProductionQueueRuntimeService, adapter: _Adapter) -> None:
        self.runtime = runtime
        self.adapters = _Adapters(adapter)


class _Probe:
    def __init__(self, terminal: bool, output: ProviderExecutionOutput | None = None) -> None:
        self.terminal = terminal
        self.output = output

    def observe(self, prompt_id: str) -> ComfyUIRecoveryObservation:
        return ComfyUIRecoveryObservation(
            ComfyUIRecoveryPresence.COMPLETED if self.terminal else ComfyUIRecoveryPresence.RUNNING,
            prompt_id,
            "provider observation",
        )

    def completed_outputs(self, prompt_id: str) -> tuple[ProviderExecutionOutput, ...]:
        return (self.output,) if self.output is not None else ()


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
    backend.execution_jobs.repository.save(_durable_job(task))
    backend._workers.register(
        ProductionWorker(
            worker_id="WORKER-GPU-01",
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    return backend, task


def test_backend_reattaches_running_durable_execution_with_new_session_lease(
    monkeypatch, tmp_path: Path
) -> None:
    backend, task = _backend(tmp_path)
    adapter = _Adapter(terminal=False)
    service = _Service(
        ProductionQueueRuntimeService(backend.tasks, backend._workers, leases=backend._leases),
        adapter,
    )
    monkeypatch.setattr(
        backend, "_execution_service", lambda _task, _resource: (service, "WORKER-GPU-01")
    )
    monkeypatch.setattr(
        compiled_module, "ComfyUIRestartRecoveryProbe", lambda _endpoint: _Probe(False)
    )

    result = backend.reconcile(task.task_id)

    assert result.state.value == "running"
    assert task.task_id in backend._active
    active = backend._active[task.task_id]
    assert active.lease_id.startswith("PRLEASE-")
    assert active.lease_id != _durable_job(task).lease_id
    assert "not resubmitted" in result.message


def test_backend_reconciles_completed_durable_execution_and_ingests_output(
    monkeypatch, tmp_path: Path
) -> None:
    backend, task = _backend(tmp_path)
    provider_file = backend.comfyui_output_directory / "Xorix" / "Production" / "clip.mp4"
    provider_file.parent.mkdir(parents=True)
    provider_file.write_bytes(b"phase-20.16-recovered-video")
    output = ProviderExecutionOutput(
        output_id="PEO-RO-COMFY-prompt-20-16-001",
        relative_path="Xorix/Production/clip.mp4",
        media_kind="production_video",
        source_output_id="RO-COMFY-prompt-20-16-001",
        metadata=(("renderer", "comfyui"), ("recovered_after_restart", "true")),
    )
    adapter = _Adapter(terminal=True)
    service = _Service(
        ProductionQueueRuntimeService(backend.tasks, backend._workers, leases=backend._leases),
        adapter,
    )
    monkeypatch.setattr(
        backend, "_execution_service", lambda _task, _resource: (service, "WORKER-GPU-01")
    )
    monkeypatch.setattr(
        compiled_module,
        "ComfyUIRestartRecoveryProbe",
        lambda _endpoint: _Probe(True, output),
    )

    result = backend.reconcile(task.task_id)

    assert result.state.value == "completed"
    assert len(result.generated_media_ids) == 1
    media = backend.media.get(result.generated_media_ids[0])
    assert media is not None
    assert (backend.project_directory / Path(media.file.relative_path)).read_bytes() == (
        b"phase-20.16-recovered-video"
    )
    assert provider_file.exists()
    assert task.task_id not in backend._active
