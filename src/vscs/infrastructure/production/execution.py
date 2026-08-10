"""End-to-end render execution orchestration for production jobs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from vscs.application.acpp import RenderJob
from vscs.application.production_pipeline import (
    ExecutionRequest,
    ExecutionResult,
    ExecutorRegistry,
    LeaseManager,
    ProductionExecutor,
    ProductionNode,
    ProductionPipeline,
    ProductionStage,
    ProductionState,
    QueueState,
    RenderQueue,
    RenderQueueEngine,
    RenderQueueEntry,
    WorkerIdentity,
)

from .staging import AssetStager, StagingManifest, StagingRequest


class RenderExecutionEventType(StrEnum):
    """Stable event categories emitted during one render execution."""

    CLAIMED = "claimed"
    STAGED = "staged"
    STARTED = "started"
    COMPLETED = "completed"
    RETRY_SCHEDULED = "retry_scheduled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RenderExecutionEvent:
    """One immutable event emitted by the render execution service."""

    event_type: RenderExecutionEventType
    occurred_at: datetime
    entry_id: str
    job_id: str
    message: str


@dataclass(frozen=True, slots=True)
class RenderExecutionRequest:
    """Inputs required to execute one ready render queue entry."""

    queue: RenderQueue
    pipeline: ProductionPipeline
    jobs: tuple[RenderJob, ...]
    worker: WorkerIdentity
    staging_requests: tuple[StagingRequest, ...] = ()
    entry_id: str | None = None
    lease_duration_seconds: float = 3600.0

    def __post_init__(self) -> None:
        if self.lease_duration_seconds <= 0:
            raise ValueError("lease_duration_seconds must be positive")


@dataclass(frozen=True, slots=True)
class RenderExecutionOutcome:
    """Queue, pipeline, staging, and executor results after one execution."""

    queue: RenderQueue
    pipeline: ProductionPipeline
    entry: RenderQueueEntry
    execution_result: ExecutionResult | None
    staging_manifest: StagingManifest | None
    events: tuple[RenderExecutionEvent, ...]


@dataclass(frozen=True, slots=True)
class RenderExecutionConfig:
    """Policy controlling render execution orchestration."""

    cleanup_staging_on_success: bool = False


class RenderExecutionError(RuntimeError):
    """Raised when a render execution request cannot be started."""


class RenderExecutionService:
    """Claim, stage, execute, and reconcile one production render job."""

    def __init__(
        self,
        registry: ExecutorRegistry,
        *,
        stager: AssetStager | None = None,
        queue_engine: RenderQueueEngine | None = None,
        lease_manager: LeaseManager | None = None,
        config: RenderExecutionConfig | None = None,
    ) -> None:
        self.registry = registry
        self.stager = stager
        self.queue_engine = queue_engine or RenderQueueEngine()
        self.lease_manager = lease_manager or LeaseManager()
        self.config = config or RenderExecutionConfig()

    def execute(
        self,
        request: RenderExecutionRequest,
        *,
        now: datetime | None = None,
    ) -> RenderExecutionOutcome:
        """Execute one ready queue entry and reconcile all runtime state."""
        current = now or datetime.now(UTC)
        queue = self.queue_engine.refresh(request.queue, current)
        entry = self._select_entry(queue, request.entry_id, current)
        job = self._job(request.jobs, entry.job_id)
        executor = self._executor(job, request.worker)
        events: list[RenderExecutionEvent] = []

        queue = self.queue_engine.claim(
            queue,
            entry.entry_id,
            request.worker.worker_id,
            current,
        )
        events.append(self._event(RenderExecutionEventType.CLAIMED, entry, current))

        manifest: StagingManifest | None = None
        pipeline = request.pipeline
        try:
            if request.staging_requests:
                if self.stager is None:
                    raise RenderExecutionError(
                        "Staging requests were supplied without an AssetStager"
                    )
                plan = self.stager.plan(job.job_id, request.staging_requests)
                manifest = self.stager.stage(plan)
                self.stager.validate(manifest)
                events.append(self._event(RenderExecutionEventType.STAGED, entry, current))

            queue = self.queue_engine.start(queue, entry.entry_id, current)
            pipeline = self._set_render_state(
                pipeline,
                entry.clip_id,
                ProductionState.RUNNING,
            )
            events.append(self._event(RenderExecutionEventType.STARTED, entry, current))
            lease = self.lease_manager.acquire(
                job.job_id,
                request.worker.worker_id,
                duration_seconds=request.lease_duration_seconds,
                now=current,
            )
            result = executor.execute(ExecutionRequest(job, request.worker, lease, current))
        except Exception as exc:
            claimed = queue.entry(entry.entry_id)
            if claimed is not None and claimed.state is QueueState.CLAIMED:
                queue = self.queue_engine.start(queue, entry.entry_id, current)
            return self._failure_outcome(
                queue,
                pipeline,
                entry,
                job,
                str(exc),
                manifest,
                events,
                current,
            )

        completed_at = result.completed_at
        if result.succeeded:
            queue = self.queue_engine.complete(queue, entry.entry_id, completed_at)
            pipeline = self._set_render_state(
                pipeline,
                entry.clip_id,
                ProductionState.COMPLETED,
            )
            events.append(
                self._event(
                    RenderExecutionEventType.COMPLETED,
                    entry,
                    completed_at,
                    "Render execution completed",
                )
            )
            if (
                manifest is not None
                and self.stager is not None
                and self.config.cleanup_staging_on_success
            ):
                self.stager.cleanup(manifest)
        else:
            message = result.error_message or "Render execution failed"
            queue = self.queue_engine.fail(
                queue,
                entry.entry_id,
                message,
                retry_delay_seconds=job.retry_policy.backoff_seconds,
                now=completed_at,
            )
            refreshed = queue.entry(entry.entry_id)
            terminal = refreshed is not None and refreshed.state is QueueState.FAILED
            pipeline = self._set_render_state(
                pipeline,
                entry.clip_id,
                ProductionState.FAILED if terminal else ProductionState.PENDING,
            )
            event_type = (
                RenderExecutionEventType.FAILED
                if terminal
                else RenderExecutionEventType.RETRY_SCHEDULED
            )
            events.append(self._event(event_type, entry, completed_at, message))

        final_entry = queue.entry(entry.entry_id)
        if final_entry is None:
            raise RenderExecutionError(f"Queue entry disappeared: {entry.entry_id}")
        return RenderExecutionOutcome(
            queue=queue,
            pipeline=pipeline,
            entry=final_entry,
            execution_result=result,
            staging_manifest=manifest,
            events=tuple(events),
        )

    def _failure_outcome(
        self,
        queue: RenderQueue,
        pipeline: ProductionPipeline,
        entry: RenderQueueEntry,
        job: RenderJob,
        message: str,
        manifest: StagingManifest | None,
        events: list[RenderExecutionEvent],
        now: datetime,
    ) -> RenderExecutionOutcome:
        queue = self.queue_engine.fail(
            queue,
            entry.entry_id,
            message,
            retry_delay_seconds=job.retry_policy.backoff_seconds,
            now=now,
        )
        final_entry = queue.entry(entry.entry_id)
        if final_entry is None:
            raise RenderExecutionError(f"Queue entry disappeared: {entry.entry_id}")
        terminal = final_entry.state is QueueState.FAILED
        pipeline = self._set_render_state(
            pipeline,
            entry.clip_id,
            ProductionState.FAILED if terminal else ProductionState.PENDING,
        )
        events.append(
            self._event(
                RenderExecutionEventType.FAILED
                if terminal
                else RenderExecutionEventType.RETRY_SCHEDULED,
                entry,
                now,
                message,
            )
        )
        return RenderExecutionOutcome(
            queue=queue,
            pipeline=pipeline,
            entry=final_entry,
            execution_result=None,
            staging_manifest=manifest,
            events=tuple(events),
        )

    def _select_entry(
        self,
        queue: RenderQueue,
        entry_id: str | None,
        now: datetime,
    ) -> RenderQueueEntry:
        ready = self.queue_engine.ready_entries(queue, now)
        if entry_id is not None:
            entry = next((item for item in ready if item.entry_id == entry_id), None)
            if entry is None:
                raise RenderExecutionError(f"Queue entry is not ready: {entry_id}")
            return entry
        if not ready:
            raise RenderExecutionError("No render queue entries are ready")
        return ready[0]

    @staticmethod
    def _job(jobs: tuple[RenderJob, ...], job_id: str) -> RenderJob:
        job = next((item for item in jobs if item.job_id == job_id), None)
        if job is None:
            raise RenderExecutionError(f"Render job not found: {job_id}")
        return job

    def _executor(self, job: RenderJob, worker: WorkerIdentity) -> ProductionExecutor:
        executor = self.registry.get(worker.executor_id)
        if executor is None:
            raise RenderExecutionError(f"Worker executor is not registered: {worker.executor_id}")
        required = frozenset(job.required_capabilities)
        if not required.issubset(executor.capabilities):
            raise RenderExecutionError(f"Executor does not support render job: {job.job_id}")
        if not required.issubset(worker.capabilities):
            raise RenderExecutionError(f"Worker does not support render job: {job.job_id}")
        return executor

    @staticmethod
    def _set_render_state(
        pipeline: ProductionPipeline,
        clip_id: str,
        state: ProductionState,
    ) -> ProductionPipeline:
        nodes: list[ProductionNode] = []
        for node in pipeline.nodes:
            if node.stage is ProductionStage.RENDERING and node.clip_id == clip_id:
                nodes.append(replace(node, state=state))
            else:
                nodes.append(node)
        return replace(pipeline, nodes=tuple(nodes))

    @staticmethod
    def _event(
        event_type: RenderExecutionEventType,
        entry: RenderQueueEntry,
        occurred_at: datetime,
        message: str | None = None,
    ) -> RenderExecutionEvent:
        return RenderExecutionEvent(
            event_type=event_type,
            occurred_at=occurred_at,
            entry_id=entry.entry_id,
            job_id=entry.job_id,
            message=message or event_type.value.replace("_", " ").title(),
        )
