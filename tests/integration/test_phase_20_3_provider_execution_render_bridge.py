"""Integration acceptance for the Phase 20.3 rendering compatibility bridge."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionExecutionLease,
    ProductionQueue,
    ProductionQueueAttempt,
    ProductionQueueEntry,
    ProductionQueueState,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    ProviderExecutionContextFactory,
    ProviderExecutionState,
    RenderProviderExecutionAdapter,
    RenderProviderExecutionCompiler,
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

NOW = datetime(2026, 8, 18, 17, 30, tzinfo=UTC)


class FakeRenderAdapter:
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
            payload={"prompt": {"workflow": "compiled"}},
        )

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        return RenderJob(
            job_id="RJ-001",
            request_id=request.request_id,
            status=RenderJobStatus.QUEUED,
            submitted_at=NOW,
            renderer_job_id="provider-job-001",
        )

    def monitor(self, job: RenderJob) -> RenderJob:
        return replace(job, status=RenderJobStatus.RUNNING, progress=0.5, started_at=NOW)

    def cancel(self, job: RenderJob) -> RenderJob:
        return job.transition(RenderJobStatus.CANCELLED, finished_at=NOW)

    def fetch_outputs(self, job: RenderJob) -> tuple[RenderOutput, ...]:
        return (
            RenderOutput(
                output_id="RO-001",
                kind=RenderOutputKind.PRODUCTION_VIDEO,
                relative_path="provider_outputs/clip-001.mp4",
                request_id=job.request_id,
                renderer=self.renderer,
                workflow_id="LTX-VIDEO",
                quality_level=QualityLevel.PRODUCTION,
            ),
        )


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-001",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-001",
            revision=1,
            fingerprint="authority-fingerprint",
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
        production_id="PROD-001",
        schedule_id="SCHED-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-PT-001",
                task_id="PT-001",
                resource_id="GPU-01",
                task_type=ProductionTaskType.VIDEO_GENERATION,
                state=ProductionQueueState.RUNNING,
                priority=ProductionTaskPriority.NORMAL,
                attempts=(
                    ProductionQueueAttempt(
                        attempt_number=1,
                        worker_id="WORKER-01",
                        started_at=NOW,
                    ),
                ),
                claimed_by="WORKER-01",
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def _lease() -> ProductionExecutionLease:
    return ProductionExecutionLease(
        lease_id="LEASE-001",
        queue_id="PQ-001",
        entry_id="PQE-PT-001",
        task_id="PT-001",
        worker_id="WORKER-01",
        acquired_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
        last_heartbeat_at=NOW,
    )


def _render_request() -> RenderRequest:
    return RenderRequest(
        request_id="RR-001",
        production_id="PROD-001",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="LTX-VIDEO",
        quality_level=QualityLevel.PRODUCTION,
        prompt_package=PromptPackageReference(package_id="PROMPT-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(
            width=1920,
            height=1080,
            frames_per_second=24,
            frame_count=240,
        ),
        output=OutputSettings(
            relative_directory="provider_outputs",
            filename_stem="clip-001",
        ),
    )


def test_phase_20_3_bridges_running_queue_authority_to_render_adapter() -> None:
    context = ProviderExecutionContextFactory().bind(
        _queue(), "PQE-PT-001", _lease(), _task()
    )
    render_adapter = FakeRenderAdapter()
    execution_request = RenderProviderExecutionCompiler().compile(
        context,
        _render_request(),
        render_adapter,
    )
    adapter = RenderProviderExecutionAdapter("LOCAL-RENDER-01", render_adapter)

    assert adapter.validate(execution_request).passed
    submitted = adapter.submit(execution_request)
    assert submitted.execution_id == context.execution_id
    assert submitted.provider_id == "LOCAL-RENDER-01"
    assert submitted.provider_job_id == "provider-job-001"
    assert submitted.state is ProviderExecutionState.QUEUED

    running = adapter.monitor(submitted)
    assert running.state is ProviderExecutionState.RUNNING
    assert running.progress == 0.5

    outputs = adapter.fetch_outputs(running)
    assert len(outputs) == 1
    assert outputs[0].source_output_id == "RO-001"
    assert outputs[0].relative_path == "provider_outputs/clip-001.mp4"
    assert outputs[0].media_kind == "production_video"
