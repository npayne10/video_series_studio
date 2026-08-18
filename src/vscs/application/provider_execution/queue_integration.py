"""Phase 20 orchestration from authoritative ProductionQueue state to provider execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import PurePath

from vscs.application.production_tasks import (
    ProductionExecutionLease,
    ProductionQueue,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionTask,
    ProductionTaskRepository,
)
from vscs.application.rendering import RenderRequest

from .adapter_registry import ProviderExecutionAdapterRegistry
from .binding import ProviderExecutionContextFactory
from .execution_records import DurableExecutionJob
from .execution_service import DurableExecutionJobService
from .models import (
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionState,
)
from .provider_registry import ProviderRegistration
from .provider_service import ProviderRegistryService
from .rendering_bridge import (
    RenderProviderExecutionAdapter,
    RenderProviderExecutionCompiler,
)


class QueueProviderExecutionError(RuntimeError):
    """Raised when authoritative queue work cannot be routed or executed safely."""


@dataclass(frozen=True, slots=True)
class QueueProviderExecutionSubmission:
    """Result of one queue-authorised provider submission attempt."""

    queue: ProductionQueue
    provider: ProviderRegistration
    lease: ProductionExecutionLease | None
    handle: ProviderExecutionHandle | None
    execution_job: DurableExecutionJob | None = None
    error_message: str | None = None

    @property
    def submitted(self) -> bool:
        return self.handle is not None and self.error_message is None


@dataclass(frozen=True, slots=True)
class QueueProviderExecutionReconciliation:
    """Provider observation reconciled back to authoritative queue state."""

    queue: ProductionQueue
    handle: ProviderExecutionHandle
    lease: ProductionExecutionLease | None
    outputs: tuple[ProviderExecutionOutput, ...] = ()
    execution_job: DurableExecutionJob | None = None

    @property
    def terminal(self) -> bool:
        return self.handle.state in {
            ProviderExecutionState.COMPLETED,
            ProviderExecutionState.FAILED,
            ProviderExecutionState.CANCELLED,
        }


class QueueProviderExecutionService:
    """Bridge Phase 19 queue authority to Phase 20 provider execution."""

    def __init__(
        self,
        *,
        runtime: ProductionQueueRuntimeService,
        tasks: ProductionTaskRepository,
        resources: ProductionResourceCatalog,
        providers: ProviderRegistryService,
        adapters: ProviderExecutionAdapterRegistry,
        execution_jobs: DurableExecutionJobService | None = None,
        context_factory: ProviderExecutionContextFactory | None = None,
        compiler: RenderProviderExecutionCompiler | None = None,
    ) -> None:
        self.runtime = runtime
        self.tasks = tasks
        self.resources = resources
        self.providers = providers
        self.adapters = adapters
        self.execution_jobs = execution_jobs
        self.context_factory = context_factory or ProviderExecutionContextFactory()
        self.compiler = compiler or RenderProviderExecutionCompiler()

    def submit(
        self,
        queue: ProductionQueue,
        entry_id: str,
        worker_id: str,
        render_request: RenderRequest,
        production_package: str,
        *,
        lease_duration_seconds: float,
        provider_id: str | None = None,
        now: datetime | None = None,
    ) -> QueueProviderExecutionSubmission:
        """Claim/start one queue entry and submit its governed render request to a provider."""
        current = now or datetime.now(UTC)
        entry = queue.entry(entry_id)
        if entry is None:
            raise QueueProviderExecutionError(f"ProductionQueue entry not found: {entry_id}")
        if entry.state is not ProductionQueueState.READY:
            raise QueueProviderExecutionError(
                f"ProductionQueue entry must be READY before provider submission: {entry_id}"
            )
        task = self.tasks.get(entry.task_id)
        if task is None:
            raise QueueProviderExecutionError(f"ProductionTask not found: {entry.task_id}")
        resource = self.resources.resource(entry.resource_id)
        if resource is None:
            raise QueueProviderExecutionError(f"ProductionResource not found: {entry.resource_id}")
        provider = self._select_provider(task, resource, provider_id)
        adapter = self.adapters.require(provider.provider_id)
        if not isinstance(adapter, RenderProviderExecutionAdapter):
            raise QueueProviderExecutionError(
                f"Provider does not expose render execution: {provider.provider_id}"
            )
        request = self._bind_request(task.production_id, render_request, production_package)

        claim = self.runtime.claim(
            queue,
            entry.entry_id,
            worker_id,
            lease_duration_seconds=lease_duration_seconds,
            now=current,
        )
        running = self.runtime.start(
            claim.queue,
            entry.entry_id,
            claim.lease.lease_id,
            now=current,
        )
        durable_job: DurableExecutionJob | None = None
        execution_id: str | None = None
        try:
            context = self.context_factory.bind(
                running,
                entry.entry_id,
                claim.lease,
                task,
                now=current,
            )
            execution_id = context.execution_id
            if self.execution_jobs is not None:
                durable_job = self.execution_jobs.prepare(
                    context,
                    provider.provider_id,
                    render_request_id=request.request_id,
                    workflow_id=request.workflow_id,
                    now=current,
                )
            execution_request = self.compiler.compile(context, request, adapter.adapter)
            validation = adapter.validate(execution_request)
            if not validation.passed:
                raise QueueProviderExecutionError("; ".join(validation.messages))
            handle = adapter.submit(execution_request)
            if self.execution_jobs is not None:
                durable_job = self.execution_jobs.observe(
                    context.execution_id,
                    handle,
                    now=current,
                )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            if self.execution_jobs is not None and execution_id is not None and durable_job is not None:
                try:
                    durable_job = self.execution_jobs.submission_failed(
                        execution_id,
                        message,
                        now=current,
                    )
                except Exception as persistence_exc:
                    message = f"{message}; durable execution persistence failed: {persistence_exc}"
            failed = self.runtime.fail(
                running,
                entry.entry_id,
                claim.lease.lease_id,
                message,
                now=current,
            )
            return QueueProviderExecutionSubmission(
                queue=failed,
                provider=provider,
                lease=None,
                handle=None,
                execution_job=durable_job,
                error_message=message,
            )
        return QueueProviderExecutionSubmission(
            queue=running,
            provider=provider,
            lease=claim.lease,
            handle=handle,
            execution_job=durable_job,
        )

    def reconcile(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        handle: ProviderExecutionHandle,
        *,
        lease_duration_seconds: float,
        now: datetime | None = None,
    ) -> QueueProviderExecutionReconciliation:
        """Poll provider state and reconcile terminal results back to ProductionQueue."""
        current = now or datetime.now(UTC)
        adapter = self.adapters.require(handle.provider_id)
        renewed = self.runtime.heartbeat(
            queue,
            entry_id,
            lease_id,
            duration_seconds=lease_duration_seconds,
            now=current,
        )
        refreshed = adapter.monitor(handle)
        durable_job = self._observe_durable(refreshed, current)
        if refreshed.state is ProviderExecutionState.COMPLETED:
            outputs = adapter.fetch_outputs(refreshed)
            completed = self.runtime.complete(queue, entry_id, lease_id, now=current)
            return QueueProviderExecutionReconciliation(
                queue=completed,
                handle=refreshed,
                lease=None,
                outputs=outputs,
                execution_job=durable_job,
            )
        if refreshed.state is ProviderExecutionState.FAILED:
            failed = self.runtime.fail(
                queue,
                entry_id,
                lease_id,
                refreshed.failure_reason or "provider execution failed",
                now=current,
            )
            return QueueProviderExecutionReconciliation(
                queue=failed,
                handle=refreshed,
                lease=None,
                execution_job=durable_job,
            )
        if refreshed.state is ProviderExecutionState.CANCELLED:
            return QueueProviderExecutionReconciliation(
                queue=self._cancel_queue(queue, entry_id, lease_id, current),
                handle=refreshed,
                lease=None,
                execution_job=durable_job,
            )
        return QueueProviderExecutionReconciliation(
            queue=queue,
            handle=refreshed,
            lease=renewed,
            execution_job=durable_job,
        )

    def cancel(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        handle: ProviderExecutionHandle,
        *,
        now: datetime | None = None,
    ) -> QueueProviderExecutionReconciliation:
        """Cancel a provider job and reconcile cancellation to the queue when supported."""
        current = now or datetime.now(UTC)
        adapter = self.adapters.require(handle.provider_id)
        cancelled_handle = adapter.cancel(handle)
        durable_job = self._observe_durable(cancelled_handle, current)
        cancelled_queue = self._cancel_queue(queue, entry_id, lease_id, current)
        return QueueProviderExecutionReconciliation(
            queue=cancelled_queue,
            handle=cancelled_handle,
            lease=None,
            execution_job=durable_job,
        )

    def _observe_durable(
        self,
        handle: ProviderExecutionHandle,
        now: datetime,
    ) -> DurableExecutionJob | None:
        if self.execution_jobs is None:
            return None
        return self.execution_jobs.observe(handle.execution_id, handle, now=now)

    def _cancel_queue(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        now: datetime,
    ) -> ProductionQueue:
        lease = self.runtime.leases.require_active(lease_id, now=now)
        entry = queue.entry(entry_id)
        if entry is None:
            raise QueueProviderExecutionError(f"ProductionQueue entry not found: {entry_id}")
        if (
            lease.queue_id != queue.queue_id
            or lease.entry_id != entry.entry_id
            or lease.task_id != entry.task_id
            or lease.worker_id != entry.claimed_by
        ):
            raise QueueProviderExecutionError(
                "Production execution lease does not own this queue entry"
            )
        cancelled = self.runtime.queue_engine.cancel(queue, entry_id, now=now)
        self.runtime.leases.release(lease_id)
        return cancelled

    def _select_provider(
        self,
        task: ProductionTask,
        resource: ProductionResource,
        provider_id: str | None,
    ) -> ProviderRegistration:
        eligible = self.providers.eligible_providers(task, resource)
        if provider_id is not None:
            normalized = provider_id.strip()
            if not normalized:
                raise QueueProviderExecutionError("provider_id cannot be blank when supplied")
            selected = next((item for item in eligible if item.provider_id == normalized), None)
            if selected is None:
                raise QueueProviderExecutionError(
                    f"Requested provider is not eligible for queue work: {normalized}"
                )
            return selected
        if not eligible:
            raise QueueProviderExecutionError(
                f"No eligible provider exists for ProductionTask: {task.task_id}"
            )
        if len(eligible) > 1:
            provider_ids = ", ".join(item.provider_id for item in eligible)
            raise QueueProviderExecutionError(
                f"Multiple eligible providers require explicit selection: {provider_ids}"
            )
        return eligible[0]

    @staticmethod
    def _bind_request(
        production_id: str,
        request: RenderRequest,
        production_package: str,
    ) -> RenderRequest:
        if request.production_id != production_id:
            raise QueueProviderExecutionError(
                "RenderRequest production does not match ProductionTask authority"
            )
        package = production_package.strip()
        if not package:
            raise QueueProviderExecutionError("production_package cannot be blank")
        if PurePath(package).name in {"", ".", ".."}:
            raise QueueProviderExecutionError("production_package path is invalid")
        metadata = dict(request.metadata)
        metadata["production_package"] = package
        return replace(request, metadata=metadata)
