"""Integration acceptance for durable Phase 20.7 queue/provider execution records."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
)
from vscs.application.provider_execution import (
    DurableExecutionJobService,
    ProviderExecutionAdapterRegistry,
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistryService,
    QueueProviderExecutionService,
    RenderProviderExecutionAdapter,
)
from vscs.application.rendering import (
    AssetPackageReference,
    CompiledRenderRequest,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderJob,
    RenderJobStatus,
    RenderOutput,
    RenderOutputKind,
    RenderRequest,
    RenderSettings,
    RequestValidation,
    WorkflowCapabilities,
)
from vscs.domain.generated_media import GeneratedMediaKind
from vscs.infrastructure.provider_execution import (
    JsonDurableExecutionJobRepository,
    JsonProviderRegistrationRepository,
)

NOW = datetime(2026, 8, 18, 19, 0, tzinfo=UTC)


class TaskRepository:
    def __init__(self, task: ProductionTask) -> None:
        self.task = task

    def get(self, task_id: str) -> ProductionTask | None:
        return self.task if task_id == self.task.task_id else None

    def save(self, task: ProductionTask) -> ProductionTask:
        self.task = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return (self.task,) if production_id == self.task.production_id else ()


class CompletingRenderAdapter:
    renderer = RendererKind.COMFYUI

    def capabilities(self, workflow_id: str) -> WorkflowCapabilities:
        return WorkflowCapabilities(text_to_video=True)

    def validate_request(self, request: RenderRequest) -> RequestValidation:
        return RequestValidation(True)

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        return CompiledRenderRequest(
            request_id=request.request_id,
            renderer=self.renderer,
            workflow_id=request.workflow_id,
            payload={"production_package": request.metadata["production_package"]},
        )

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        return RenderJob(
            job_id="RJ-20-7-001",
            request_id=request.request_id,
            status=RenderJobStatus.QUEUED,
            submitted_at=NOW,
            renderer_job_id="prompt-20-7-001",
        )

    def monitor(self, job: RenderJob) -> RenderJob:
        return replace(
            job,
            status=RenderJobStatus.COMPLETED,
            started_at=NOW,
            finished_at=NOW + timedelta(seconds=30),
            progress=1.0,
        )

    def cancel(self, job: RenderJob) -> RenderJob:
        return replace(job, status=RenderJobStatus.CANCELLED)

    def fetch_outputs(self, job: RenderJob) -> tuple[RenderOutput, ...]:
        return (
            RenderOutput(
                output_id="RO-20-7-001",
                kind=RenderOutputKind.PRODUCTION_VIDEO,
                relative_path="Xorix/Production/preview/phase_20_7.mp4",
                request_id=job.request_id,
                renderer=self.renderer,
                workflow_id="video_production_engine_v7_1_4",
                quality_level=QualityLevel.PRODUCTION,
            ),
        )


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-7-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-7-001",
            revision=1,
            fingerprint="authority-20-7",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _queue() -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-20-7-001",
        production_id="XORIX",
        schedule_id="SCHED-20-7-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-20-7",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-PT-20-7-001",
                task_id="PT-20-7-001",
                resource_id="GPU-01",
                task_type=ProductionTaskType.VIDEO_GENERATION,
                state=ProductionQueueState.READY,
                priority=ProductionTaskPriority.NORMAL,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def _request() -> RenderRequest:
    return RenderRequest(
        request_id="REQ-20-7-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="video_production_engine_v7_1_4",
        quality_level=QualityLevel.PRODUCTION,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(1280, 720, 24, 145),
        output=OutputSettings("renders/production", "phase-20-7"),
    )


def test_phase_20_7_queue_submission_and_completion_survive_repository_restart(tmp_path) -> None:
    task = _task()
    tasks = TaskRepository(task)
    workers = ProductionWorkerRegistry()
    workers.register(
        ProductionWorker(
            worker_id="WORKER-01",
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    runtime = ProductionQueueRuntimeService(tasks, workers)
    resources = ProductionResourceCatalog(
        (
            ProductionResource(
                resource_id="GPU-01",
                capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
            ),
        )
    )
    providers = ProviderRegistryService(JsonProviderRegistrationRepository(tmp_path / "providers"))
    providers.register(
        ProviderRegistration(
            provider_id="LOCAL-COMFYUI-01",
            adapter_type="comfyui",
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
            supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
            supported_media_kinds=frozenset({GeneratedMediaKind.VIDEO}),
            endpoint="http://127.0.0.1:8188",
            health=ProviderHealthState.HEALTHY,
        )
    )
    adapters = ProviderExecutionAdapterRegistry()
    adapters.register(RenderProviderExecutionAdapter("LOCAL-COMFYUI-01", CompletingRenderAdapter()))
    execution_root = tmp_path / "executions"
    durable = DurableExecutionJobService(JsonDurableExecutionJobRepository(execution_root))
    service = QueueProviderExecutionService(
        runtime=runtime,
        tasks=tasks,
        resources=resources,
        providers=providers,
        adapters=adapters,
        execution_jobs=durable,
    )

    submitted = service.submit(
        _queue(),
        "PQE-PT-20-7-001",
        "WORKER-01",
        _request(),
        r"D:\VSCS TSR2\Queues\preview_production_queue.json",
        lease_duration_seconds=300,
        now=NOW,
    )

    assert submitted.submitted
    assert submitted.execution_job is not None
    assert submitted.execution_job.provider_job_id == "prompt-20-7-001"
    assert submitted.lease is not None
    assert submitted.handle is not None

    after_submit_restart = DurableExecutionJobService(
        JsonDurableExecutionJobRepository(execution_root)
    )
    restored_active = after_submit_restart.require(submitted.execution_job.execution_id)
    assert restored_active.provider_job_id == "prompt-20-7-001"
    assert not restored_active.terminal
    assert after_submit_restart.list_active() == (restored_active,)

    reconciled = service.reconcile(
        submitted.queue,
        "PQE-PT-20-7-001",
        submitted.lease.lease_id,
        submitted.handle,
        lease_duration_seconds=300,
        now=NOW + timedelta(seconds=30),
    )

    assert reconciled.queue.entry("PQE-PT-20-7-001").state is ProductionQueueState.COMPLETED
    assert reconciled.execution_job is not None
    assert reconciled.execution_job.terminal
    assert reconciled.execution_job.provider_job_id == "prompt-20-7-001"

    after_completion_restart = DurableExecutionJobService(
        JsonDurableExecutionJobRepository(execution_root)
    )
    restored_completed = after_completion_restart.require(reconciled.execution_job.execution_id)
    assert restored_completed.state.value == "completed"
    assert restored_completed.progress == 1.0
    assert restored_completed.events[-1].state.value == "completed"
    assert after_completion_restart.list_active() == ()
