from datetime import UTC, datetime
from pathlib import Path

import vscs.infrastructure.production_execution.comfyui_backend as backend_module
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEntry,
    ProductionQueueState,
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleSnapshot,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    production_schedule_fingerprint,
)
from vscs.application.provider_execution import (
    DurableExecutionEvent,
    DurableExecutionJob,
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionState,
    QueueProviderExecutionReconciliation,
)
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend

NOW = datetime(2026, 8, 19, 18, 30, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-15-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-15-001",
            revision=1,
            fingerprint="authority-20-15",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=NOW,
    )


def _persist_approved_schedule(
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
        schedule_id="PS-20-15",
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
            notes="Approved for production execution",
            reviewed_at=NOW,
        )
    )


def _queue(task: ProductionTask) -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-20-15",
        production_id=task.production_id,
        schedule_id="PS-20-15",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint-20-15",
        entries=(
            ProductionQueueEntry(
                entry_id=f"PQE-{task.task_id}",
                task_id=task.task_id,
                resource_id="GPU-01",
                task_type=task.task_type,
                state=ProductionQueueState.RUNNING,
                priority=ProductionTaskPriority.NORMAL,
                claimed_by="WORKER-GPU-01",
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def _handle(state: ProviderExecutionState) -> ProviderExecutionHandle:
    return ProviderExecutionHandle(
        execution_id="PEX-20-15-001",
        provider_id="LOCAL-COMFYUI-GPU-01",
        provider_job_id="prompt-20-15",
        state=state,
        submitted_at=NOW,
        progress=1.0 if state is ProviderExecutionState.COMPLETED else 0.5,
    )


def _completed_job(task: ProductionTask) -> DurableExecutionJob:
    return DurableExecutionJob(
        execution_id="PEX-20-15-001",
        production_id=task.production_id,
        task_id=task.task_id,
        queue_id="PQ-20-15",
        entry_id=f"PQE-{task.task_id}",
        resource_id="GPU-01",
        worker_id="WORKER-GPU-01",
        lease_id="PLEASE-20-15",
        attempt_number=1,
        authority_fingerprint=task.authority.fingerprint,
        provider_id="LOCAL-COMFYUI-GPU-01",
        state=ProviderExecutionState.COMPLETED,
        created_at=NOW,
        updated_at=NOW,
        provider_job_id="prompt-20-15",
        render_request_id=f"REQ-{task.task_id}",
        workflow_id="video_production_engine_v7_1_4",
        submitted_at=NOW,
        progress=1.0,
        events=(
            DurableExecutionEvent(
                state=ProviderExecutionState.COMPLETED,
                observed_at=NOW,
                progress=1.0,
                provider_job_id="prompt-20-15",
            ),
        ),
    )


class _CompletedService:
    def __init__(
        self,
        task: ProductionTask,
        output: ProviderExecutionOutput,
    ) -> None:
        self.task = task
        self.output = output

    def reconcile(self, queue, entry_id, lease_id, handle, *, lease_duration_seconds):
        assert entry_id == f"PQE-{self.task.task_id}"
        assert lease_id == "PLEASE-20-15"
        assert lease_duration_seconds == 120.0
        return QueueProviderExecutionReconciliation(
            queue=queue,
            handle=_handle(ProviderExecutionState.COMPLETED),
            lease=None,
            outputs=(self.output,),
            execution_job=_completed_job(self.task),
        )


def test_backend_discovers_only_human_approved_scheduled_video_work(tmp_path: Path) -> None:
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

    assert backend.candidates() == ()

    _persist_approved_schedule(backend, task)

    candidates = backend.candidates()
    assert len(candidates) == 1
    assert candidates[0].task_id == task.task_id
    assert candidates[0].resource_id == "GPU-01"
    assert candidates[0].queue_entry_id == f"PQE-{task.task_id}"


def test_completed_execution_is_ingested_under_configured_project_media_output(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    output = tmp_path / "comfyui-output"
    project.mkdir()
    output.mkdir()
    provider_file = output / "Xorix" / "Production" / "clip.mp4"
    provider_file.parent.mkdir(parents=True)
    provider_file.write_bytes(b"phase-20.15-render")

    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=output,
        managed_media_directory="Media Output",
    )
    task = _task()
    backend.tasks.save(task)
    candidate = backend._candidate(task, "GPU-01", f"PQE-{task.task_id}")
    provider_output = ProviderExecutionOutput(
        output_id="PEO-20-15-001",
        relative_path="Xorix/Production/clip.mp4",
        media_kind="production_video",
        source_output_id="RO-20-15-001",
        discovered_at=NOW,
    )
    backend._active[task.task_id] = backend_module._ActiveExecution(
        candidate=candidate,
        queue=_queue(task),
        lease_id="PLEASE-20-15",
        handle=_handle(ProviderExecutionState.RUNNING),
        service=_CompletedService(task, provider_output),
    )

    result = backend.reconcile(task.task_id)

    assert result.state.value == "completed"
    assert len(result.generated_media_ids) == 1
    media = backend.media.get(result.generated_media_ids[0])
    assert media is not None
    assert media.file.relative_path.startswith("Media Output/generated_media/")
    managed_file = project / Path(media.file.relative_path)
    assert managed_file.read_bytes() == b"phase-20.15-render"
    assert provider_file.exists()
    assert provider_file.read_bytes() == b"phase-20.15-render"
