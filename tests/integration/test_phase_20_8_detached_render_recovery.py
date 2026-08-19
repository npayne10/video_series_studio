"""Integration acceptance for Phase 20.8 detached provider re-query and recovery."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.production_tasks import ProductionCapability, ProductionTaskType
from vscs.application.provider_execution import (
    DurableExecutionJobService,
    ExecutionMonitoringDisposition,
    ExecutionRecoveryAction,
    LiveExecutionMonitoringService,
    ProviderExecutionAdapterRegistry,
    ProviderExecutionContext,
    ProviderExecutionHandle,
    ProviderExecutionState,
    RenderProviderExecutionAdapter,
)
from vscs.application.rendering import (
    CompiledRenderRequest,
    RendererKind,
    RenderJob,
    RenderJobStatus,
    RequestValidation,
    WorkflowCapabilities,
)
from vscs.infrastructure.provider_execution import JsonDurableExecutionJobRepository

NOW = datetime(2026, 8, 18, 19, 30, tzinfo=UTC)


class RecoverableRenderAdapter:
    renderer = RendererKind.COMFYUI

    def capabilities(self, workflow_id: str) -> WorkflowCapabilities:
        return WorkflowCapabilities(text_to_video=True)

    def validate_request(self, request: object) -> RequestValidation:
        return RequestValidation(True)

    def compile_request(self, request: object) -> CompiledRenderRequest:
        raise AssertionError("not used")

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        raise AssertionError("not used")

    def monitor(self, job: RenderJob) -> RenderJob:
        assert job.renderer_job_id == "prompt-live-001"
        return replace(
            job,
            status=RenderJobStatus.COMPLETED,
            progress=1.0,
            finished_at=NOW + timedelta(minutes=5),
        )

    def cancel(self, job: RenderJob) -> RenderJob:
        raise AssertionError("not used")

    def fetch_outputs(self, job: RenderJob) -> tuple[()]:
        return ()


def test_detached_durable_render_can_be_requeried_after_service_reconstruction(tmp_path) -> None:
    repository = JsonDurableExecutionJobRepository(tmp_path / "execution-jobs")
    jobs = DurableExecutionJobService(repository)
    context = ProviderExecutionContext(
        execution_id="PEX-PQ-001-PQE-001-A001",
        production_id="XORIX",
        task_id="PT-001",
        queue_id="PQ-001",
        entry_id="PQE-001",
        resource_id="GPU-01",
        worker_id="WORKER-01",
        lease_id="LEASE-001",
        attempt_number=1,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        required_capabilities=(ProductionCapability.VIDEO_GENERATION,),
        authority_fingerprint="approved-authority",
    )
    jobs.prepare(
        context,
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )
    jobs.observe(
        context.execution_id,
        ProviderExecutionHandle(
            execution_id=context.execution_id,
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="prompt-live-001",
            state=ProviderExecutionState.RUNNING,
            submitted_at=NOW,
            progress=0.5,
            metadata=(("render_job_id", "COMFY-001"), ("request_id", "REQ-001")),
        ),
        now=NOW,
    )

    restarted_jobs = DurableExecutionJobService(
        JsonDurableExecutionJobRepository(tmp_path / "execution-jobs")
    )
    adapters = ProviderExecutionAdapterRegistry()
    adapters.register(
        RenderProviderExecutionAdapter("LOCAL-COMFYUI-01", RecoverableRenderAdapter())
    )
    monitoring = LiveExecutionMonitoringService(restarted_jobs, adapters)

    result = monitoring.inspect(context.execution_id, now=NOW + timedelta(minutes=5))

    assert result.provider_observed
    assert result.execution_job.state is ProviderExecutionState.COMPLETED
    assert result.disposition is ExecutionMonitoringDisposition.RECONCILIATION_REQUIRED
    assert result.recovery_action is ExecutionRecoveryAction.RECONCILE_QUEUE
    persisted = restarted_jobs.require(context.execution_id)
    assert persisted.provider_job_id == "prompt-live-001"
    assert persisted.terminal
