"""Compatibility bridge from existing RenderAdapter contracts to provider execution."""

from __future__ import annotations

from vscs.application.rendering import (
    CompiledRenderRequest,
    RenderAdapter,
    RenderJob,
    RenderJobStatus,
    RenderOutput,
    RenderRequest,
)

from .contracts import ProviderExecutionAdapter, ProviderExecutionValidation
from .execution_records import DurableExecutionJob
from .models import (
    ProviderExecutionContext,
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionPayloadKind,
    ProviderExecutionRequest,
    ProviderExecutionState,
)


class RenderProviderExecutionError(RuntimeError):
    """Raised when a rendering contract cannot be used as provider execution."""


_RENDER_STATE_MAP: dict[RenderJobStatus, ProviderExecutionState] = {
    RenderJobStatus.QUEUED: ProviderExecutionState.QUEUED,
    RenderJobStatus.PREPARING: ProviderExecutionState.PREPARING,
    RenderJobStatus.RUNNING: ProviderExecutionState.RUNNING,
    RenderJobStatus.COMPLETED: ProviderExecutionState.COMPLETED,
    RenderJobStatus.FAILED: ProviderExecutionState.FAILED,
    RenderJobStatus.CANCELLED: ProviderExecutionState.CANCELLED,
    RenderJobStatus.RETRYING: ProviderExecutionState.RETRYING,
}
_RENDER_STATUS_MAP: dict[ProviderExecutionState, RenderJobStatus] = {
    provider: render for render, provider in _RENDER_STATE_MAP.items()
}


class RenderProviderExecutionCompiler:
    """Compile an existing universal RenderRequest inside governed runtime authority."""

    def compile(
        self,
        context: ProviderExecutionContext,
        render_request: RenderRequest,
        adapter: RenderAdapter,
    ) -> ProviderExecutionRequest:
        self._validate_scope(context, render_request)
        validation = adapter.validate_request(render_request)
        if not validation.passed:
            raise RenderProviderExecutionError("; ".join(validation.messages))
        compiled = adapter.compile_request(render_request)
        return ProviderExecutionRequest(
            context=context,
            payload_kind=ProviderExecutionPayloadKind.RENDER,
            payload=compiled,
        )

    @staticmethod
    def _validate_scope(context: ProviderExecutionContext, request: RenderRequest) -> None:
        if request.production_id != context.production_id:
            raise RenderProviderExecutionError(
                "RenderRequest production does not match provider execution authority"
            )
        if request.request_id.strip() == "":
            raise RenderProviderExecutionError("RenderRequest request_id cannot be blank")


class RenderProviderExecutionAdapter(ProviderExecutionAdapter):
    """Adapt an existing RenderAdapter to the Phase 20 provider execution lifecycle."""

    def __init__(self, provider_id: str, adapter: RenderAdapter) -> None:
        normalized = provider_id.strip()
        if not normalized:
            raise ValueError("provider_id cannot be blank")
        self._provider_id = normalized
        self.adapter = adapter

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def validate(self, request: ProviderExecutionRequest) -> ProviderExecutionValidation:
        if request.payload_kind is not ProviderExecutionPayloadKind.RENDER:
            return ProviderExecutionValidation(False, ("execution payload is not render",))
        if not isinstance(request.payload, CompiledRenderRequest):
            return ProviderExecutionValidation(
                False,
                ("render execution payload must be CompiledRenderRequest",),
            )
        if request.payload.renderer is not self.adapter.renderer:
            return ProviderExecutionValidation(
                False,
                ("compiled request renderer does not match adapter",),
            )
        return ProviderExecutionValidation(True)

    def submit(self, request: ProviderExecutionRequest) -> ProviderExecutionHandle:
        validation = self.validate(request)
        if not validation.passed:
            raise RenderProviderExecutionError("; ".join(validation.messages))
        compiled = request.payload
        if not isinstance(compiled, CompiledRenderRequest):
            raise RenderProviderExecutionError("invalid compiled render payload")
        job = self.adapter.submit(compiled)
        return self._handle(request.context.execution_id, job)

    def monitor(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        job = self._require_job(handle)
        refreshed = self.adapter.monitor(job)
        return self._handle(handle.execution_id, refreshed)

    def cancel(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        job = self._require_job(handle)
        cancelled = self.adapter.cancel(job)
        return self._handle(handle.execution_id, cancelled)

    def fetch_outputs(self, handle: ProviderExecutionHandle) -> tuple[ProviderExecutionOutput, ...]:
        job = self._require_job(handle)
        outputs = self.adapter.fetch_outputs(job)
        return tuple(self._output(output) for output in outputs)

    def restore_handle(self, job: DurableExecutionJob) -> ProviderExecutionHandle:
        """Rebuild transient render state from durable provider identity after detachment."""
        if job.provider_id != self.provider_id:
            raise RenderProviderExecutionError("durable execution belongs to a different provider")
        if job.provider_job_id is None or job.submitted_at is None:
            raise RenderProviderExecutionError(
                "durable execution does not contain submitted provider identity"
            )
        metadata = dict(job.provider_metadata)
        render_job_id = metadata.get("render_job_id", "").strip()
        request_id = (metadata.get("request_id") or job.render_request_id or "").strip()
        if not render_job_id or not request_id:
            raise RenderProviderExecutionError(
                "durable execution lacks render_job_id/request_id recovery metadata"
            )
        render_job = RenderJob(
            job_id=render_job_id,
            request_id=request_id,
            status=_RENDER_STATUS_MAP[job.state],
            submitted_at=job.submitted_at,
            started_at=(job.submitted_at if job.state is ProviderExecutionState.RUNNING else None),
            finished_at=(job.updated_at if job.terminal else None),
            progress=job.progress,
            renderer_job_id=job.provider_job_id,
            failure_reason=job.failure_reason,
        )
        return ProviderExecutionHandle(
            execution_id=job.execution_id,
            provider_id=job.provider_id,
            provider_job_id=job.provider_job_id,
            state=job.state,
            submitted_at=job.submitted_at,
            progress=job.progress,
            failure_reason=job.failure_reason,
            metadata=job.provider_metadata,
            native_handle=render_job,
        )

    def _handle(self, execution_id: str, job: RenderJob) -> ProviderExecutionHandle:
        provider_job_id = job.renderer_job_id or job.job_id
        submitted_at = job.submitted_at or job.started_at or job.finished_at
        if submitted_at is None:
            raise RenderProviderExecutionError("RenderJob does not expose a submission timestamp")
        return ProviderExecutionHandle(
            execution_id=execution_id,
            provider_id=self.provider_id,
            provider_job_id=provider_job_id,
            state=_RENDER_STATE_MAP[job.status],
            submitted_at=submitted_at,
            progress=job.progress,
            failure_reason=job.failure_reason,
            metadata=(("render_job_id", job.job_id), ("request_id", job.request_id)),
            native_handle=job,
        )

    def _require_job(self, handle: ProviderExecutionHandle) -> RenderJob:
        if handle.provider_id != self.provider_id:
            raise RenderProviderExecutionError("provider handle belongs to a different provider")
        if not isinstance(handle.native_handle, RenderJob):
            raise RenderProviderExecutionError("provider handle does not contain a RenderJob")
        return handle.native_handle

    @staticmethod
    def _output(output: RenderOutput) -> ProviderExecutionOutput:
        return ProviderExecutionOutput(
            output_id=f"PEO-{output.output_id}",
            relative_path=output.relative_path,
            media_kind=output.kind.value,
            source_output_id=output.output_id,
            metadata=(
                ("renderer", output.renderer.value),
                ("workflow_id", output.workflow_id),
                ("quality_level", output.quality_level.value),
                ("version", output.version),
            ),
        )
