from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

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
    ProviderExecutionHandle,
    ProviderExecutionState,
)
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend

NOW = datetime(2026, 8, 20, 14, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-16-LIVE-OUTPUT-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-16-LIVE-OUTPUT-001",
            revision=1,
            fingerprint="authority-live-output-gate",
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
        created_at=NOW,
    )


def _job(task: ProductionTask) -> DurableExecutionJob:
    return DurableExecutionJob(
        execution_id="PEX-LIVE-OUTPUT-A001",
        production_id=task.production_id,
        task_id=task.task_id,
        queue_id="PQ-LIVE-OUTPUT",
        entry_id=f"PQE-{task.task_id}",
        resource_id="GPU-01",
        worker_id="WORKER-GPU-01",
        lease_id="PLEASE-LIVE-OUTPUT",
        attempt_number=1,
        authority_fingerprint=task.authority.fingerprint,
        provider_id="LOCAL-COMFYUI-GPU-01",
        state=ProviderExecutionState.RUNNING,
        created_at=NOW,
        updated_at=NOW,
        provider_job_id="prompt-live-output",
        render_request_id=f"REQ-{task.task_id}",
        workflow_id="video_production_engine_v7_1_4",
        submitted_at=NOW,
        progress=0.5,
        events=(
            DurableExecutionEvent(
                state=ProviderExecutionState.RUNNING,
                observed_at=NOW,
                progress=0.5,
                provider_job_id="prompt-live-output",
            ),
        ),
    )


class _Adapter:
    def monitor(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        return ProviderExecutionHandle(
            execution_id=handle.execution_id,
            provider_id=handle.provider_id,
            provider_job_id=handle.provider_job_id,
            state=ProviderExecutionState.COMPLETED,
            submitted_at=handle.submitted_at,
            progress=1.0,
            metadata=handle.metadata,
        )

    def fetch_outputs(self, handle: ProviderExecutionHandle):
        assert handle.state is ProviderExecutionState.COMPLETED
        return ()


class _Adapters:
    def require(self, provider_id: str) -> _Adapter:
        assert provider_id == "LOCAL-COMFYUI-GPU-01"
        return _Adapter()


class _Runtime:
    def __init__(self) -> None:
        self.failed_reason: str | None = None

    def heartbeat(self, queue, entry_id, lease_id, *, duration_seconds):
        assert entry_id.startswith("PQE-")
        assert lease_id == "PLEASE-LIVE-OUTPUT"
        assert duration_seconds == 120.0
        return SimpleNamespace(
            lease_id=lease_id,
            expires_at=NOW + timedelta(seconds=duration_seconds),
        )

    def fail(self, queue, entry_id, lease_id, reason):
        self.failed_reason = reason
        return queue


class _Service:
    def __init__(self) -> None:
        self.runtime = _Runtime()
        self.adapters = _Adapters()


def test_current_session_provider_completion_without_outputs_is_failed_and_retryable(
    tmp_path: Path,
) -> None:
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
    job = _job(task)
    backend.execution_jobs.repository.save(job)
    candidate = backend._candidate(task, "GPU-01", job.entry_id)
    service = _Service()
    backend._active[task.task_id] = SimpleNamespace(
        candidate=candidate,
        queue=SimpleNamespace(),
        lease_id=job.lease_id,
        handle=ProviderExecutionHandle(
            execution_id=job.execution_id,
            provider_id=job.provider_id,
            provider_job_id=job.provider_job_id,
            state=ProviderExecutionState.RUNNING,
            submitted_at=NOW,
            progress=0.5,
        ),
        service=service,
    )

    result = backend.reconcile(task.task_id)

    assert result.state.value == "failed"
    assert "produced no production output files" in result.message.casefold()
    assert service.runtime.failed_reason is not None
    assert task.task_id not in backend._active
    latest = backend.execution_jobs.list_for_task(task.task_id)[-1]
    assert latest.state is ProviderExecutionState.FAILED
    assert not backend.has_execution(task.task_id)
