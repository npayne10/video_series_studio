"""Integration acceptance for Phase 20.8 live-session provider recovery."""

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
    ExecutionMonitoringDisposition,
    LiveExecutionMonitoringService,
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
    RenderJob,
    RenderJobStatus,
    RendererKind,
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

NOW = datetime(2026, 8, 18, 20, 0, tzinfo=UTC)


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
            job_id="RJ-20-8-001",
            request_id=request.request_id,
            status=RenderJobStatus.QUEUED,
            submitted_at=NOW,
            renderer_job_id="prompt-20-8-001",
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
                output_id="RO-20-8-001",
                kind=RenderOutputKind.PRODUCTION_VIDEO,
                relative_path="Xorix/Production/preview/phase_20_8.mp4",
                request_id=job.request_id,
                renderer=self.renderer,
                workflow_id="video_production_engine_v7_1_4",
                quality_level=QualityLevel.PRODUCTION,
            ),
        )


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-8-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-8-001",
            revision=1,
            fingerprint="authority-20-8",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _queue() -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-20-8-001",
        production_id="XORIX",
        schedule_id="SCHED-20-8-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-20-8",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-PT-20-8-001",
                task_id="PT-20-8-001",
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
        request_id="REQ-20-8-001",
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
        output=OutputSettings("renders/production", "phase-20-8"),
    )


def test_live_monitoring_reconciles_terminal_provider_state_through_original_lease(tmp_path) -> None:
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
    providers = ProviderRegistryService(
        JsonProviderRegistrationRepository(tmp_path / "providers")
    )
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
    adapters.register(
        RenderProviderExecutionAdapter("LOCAL-COMFYUI-01", CompletingRenderAdapter())
    )
    durable = DurableExecutionJobService(
        JsonDurableExecutionJobRepository(tmp_path / "executions")
    )
    queue_service = QueueProviderExecutionService(
        runtime=runtime,
        tasks=tasks,
        resources=resources,
        providers=providers,
        adapters=adapters,
        execution_jobs=durable,
    )
    submitted = queue_service.submit(
        _queue(),
        "PQE-PT-20-8-001",
        "WORKER-01",
        _request(),
        r"D:\VSCS TSR2\Queues\preview_production_queue.json",
        lease_duration_seconds=300,
        now=NOW,
    )
    assert submitted.execution_job is not None
    assert submitted.lease is not None

    monitoring = LiveExecutionMonitoringService(durable, adapters)
    recovered = monitoring.recover_live(
        submitted.queue,
        submitted.execution_job.execution_id,
        queue_service,
        lease_duration_seconds=300,
        now=NOW + timedelta(seconds=30),
    )

    assert recovered.reconciliation is not None
    assert recovered.monitoring.disposition is ExecutionMonitoringDisposition.TERMINAL
    assert recovered.reconciliation.queue.entry("PQE-PT-20-8-001").state is ProductionQueueState.COMPLETED
    assert recovered.reconciliation.outputs[0].relative_path.endswith("phase_20_8.mp4")
    assert runtime.leases.active_for_entry("PQ-20-8-001", "PQE-PT-20-8-001", now=NOW + timedelta(seconds=30)) is None
