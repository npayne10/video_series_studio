"""Integration acceptance for Phase 20.6 queue-to-provider execution orchestration."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import GeneratedMediaKind
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
    ProviderExecutionAdapterRegistry,
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistryService,
    QueueProviderExecutionError,
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
from vscs.infrastructure.provider_execution import JsonProviderRegistrationRepository

NOW = datetime(2026, 8, 18, 18, 0, tzinfo=UTC)


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


class ControlledRenderAdapter:
    renderer = RendererKind.COMFYUI

    def __init__(self, *, fail_submit: bool = False) -> None:
        self.fail_submit = fail_submit
        self.compiled_package: str | None = None

    def capabilities(self, workflow_id: str) -> WorkflowCapabilities:
        return WorkflowCapabilities(text_to_video=True)

    def validate_request(self, request: RenderRequest) -> RequestValidation:
        return RequestValidation(True)

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        self.compiled_package = request.metadata.get("production_package")
        return CompiledRenderRequest(
            request_id=request.request_id,
            renderer=self.renderer,
            workflow_id=request.workflow_id,
            payload={"production_package": self.compiled_package or ""},
        )

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        if self.fail_submit:
            raise RuntimeError("provider submission failed")
        return RenderJob(
            job_id="RJ-001",
            request_id=request.request_id,
            status=RenderJobStatus.QUEUED,
            submitted_at=NOW,
            renderer_job_id="prompt-001",
        )

    def monitor(self, job: RenderJob) -> RenderJob:
        return replace(
            job,
            status=RenderJobStatus.COMPLETED,
            started_at=NOW,
            finished_at=NOW,
            progress=1.0,
        )

    def cancel(self, job: RenderJob) -> RenderJob:
        return replace(job, status=RenderJobStatus.CANCELLED, finished_at=NOW)

    def fetch_outputs(self, job: RenderJob) -> tuple[RenderOutput, ...]:
        return (
            RenderOutput(
                output_id="RO-001",
                kind=RenderOutputKind.PRODUCTION_VIDEO,
                relative_path="renders/production/clip-001.mp4",
                request_id=job.request_id,
                renderer=self.renderer,
                workflow_id="video_production_engine_v7_1_4",
                quality_level=QualityLevel.PRODUCTION,
            ),
        )


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-001",
            revision=1,
            fingerprint="approved-authority",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _queue() -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-001",
        production_id="XORIX",
        schedule_id="SCHED-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-PT-001",
                task_id="PT-001",
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
        request_id="REQ-001",
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
        output=OutputSettings("renders/production", "clip-001"),
    )


def _provider(provider_id: str) -> ProviderRegistration:
    return ProviderRegistration(
        provider_id=provider_id,
        adapter_type="comfyui",
        resource_id="GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
        supported_media_kinds=frozenset({GeneratedMediaKind.VIDEO}),
        endpoint="http://127.0.0.1:8188",
        health=ProviderHealthState.HEALTHY,
    )


def _service(tmp_path, *, second_provider: bool = False, fail_submit: bool = False):
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
    providers.register(_provider("PROVIDER-A"))
    adapters = ProviderExecutionAdapterRegistry()
    controlled = ControlledRenderAdapter(fail_submit=fail_submit)
    adapters.register(RenderProviderExecutionAdapter("PROVIDER-A", controlled))
    if second_provider:
        providers.register(_provider("PROVIDER-B"))
        adapters.register(RenderProviderExecutionAdapter("PROVIDER-B", ControlledRenderAdapter()))
    return (
        QueueProviderExecutionService(
            runtime=runtime,
            tasks=tasks,
            resources=resources,
            providers=providers,
            adapters=adapters,
        ),
        controlled,
    )


def test_phase_20_6_submit_and_reconcile_completion(tmp_path) -> None:
    service, controlled = _service(tmp_path)
    package = r"D:\Xorix\Production\XPC_Output\ACPP-QUEUE-001.json"

    submitted = service.submit(
        _queue(),
        "PQE-PT-001",
        "WORKER-01",
        _request(),
        package,
        lease_duration_seconds=300,
        now=NOW,
    )

    assert submitted.submitted
    assert submitted.queue.entry("PQE-PT-001").state is ProductionQueueState.RUNNING
    assert controlled.compiled_package == package
    assert submitted.lease is not None
    assert submitted.handle is not None

    reconciled = service.reconcile(
        submitted.queue,
        "PQE-PT-001",
        submitted.lease.lease_id,
        submitted.handle,
        lease_duration_seconds=300,
        now=NOW,
    )
    assert reconciled.queue.entry("PQE-PT-001").state is ProductionQueueState.COMPLETED
    assert reconciled.lease is None
    assert len(reconciled.outputs) == 1
    assert reconciled.outputs[0].source_output_id == "RO-001"


def test_phase_20_6_requires_explicit_provider_when_multiple_are_eligible(tmp_path) -> None:
    service, _controlled = _service(tmp_path, second_provider=True)

    with pytest.raises(QueueProviderExecutionError, match="Multiple eligible providers"):
        service.submit(
            _queue(),
            "PQE-PT-001",
            "WORKER-01",
            _request(),
            r"D:\Xorix\Production\XPC_Output\ACPP-QUEUE-001.json",
            lease_duration_seconds=300,
            now=NOW,
        )


def test_phase_20_6_submission_failure_reconciles_attempt_to_retry(tmp_path) -> None:
    service, _controlled = _service(tmp_path, fail_submit=True)
    outcome = service.submit(
        _queue(),
        "PQE-PT-001",
        "WORKER-01",
        _request(),
        r"D:\Xorix\Production\XPC_Output\ACPP-QUEUE-001.json",
        lease_duration_seconds=300,
        now=NOW,
    )

    assert not outcome.submitted
    assert outcome.error_message == "provider submission failed"
    assert outcome.lease is None
    assert outcome.queue.entry("PQE-PT-001").state is ProductionQueueState.RETRYING
