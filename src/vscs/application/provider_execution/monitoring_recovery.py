"""Live provider monitoring and recovery classification for durable executions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol, runtime_checkable

from vscs.application.production_tasks import ProductionQueue

from .adapter_registry import ProviderExecutionAdapterRegistry
from .execution_records import DurableExecutionJob
from .execution_service import DurableExecutionJobService
from .models import ProviderExecutionHandle
from .queue_integration import QueueProviderExecutionReconciliation, QueueProviderExecutionService


class ExecutionMonitoringDisposition(StrEnum):
    """Deterministic outcome of one provider execution monitoring cycle."""

    ACTIVE = "active"
    TERMINAL = "terminal"
    STALE_ACTIVE = "stale_active"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class ExecutionRecoveryAction(StrEnum):
    """Explicit recovery recommendation; never an implicit authority mutation."""

    NONE = "none"
    CONTINUE_MONITORING = "continue_monitoring"
    RECONCILE_QUEUE = "reconcile_queue"
    RETRY_PROVIDER_QUERY = "retry_provider_query"
    REQUIRE_OPERATOR_REVIEW = "require_operator_review"


@dataclass(frozen=True, slots=True)
class ExecutionMonitoringPolicy:
    """Thresholds controlling stale detection without changing provider state."""

    stale_after_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")


@dataclass(frozen=True, slots=True)
class ExecutionMonitoringResult:
    """One monitored provider observation and its explicit recovery disposition."""

    execution_job: DurableExecutionJob
    disposition: ExecutionMonitoringDisposition
    recovery_action: ExecutionRecoveryAction
    observed_at: datetime
    provider_observed: bool
    message: str
    handle: ProviderExecutionHandle | None = None

    @property
    def terminal(self) -> bool:
        return self.execution_job.terminal


@dataclass(frozen=True, slots=True)
class LiveExecutionRecoveryResult:
    """Provider monitoring plus authoritative live-session queue reconciliation."""

    monitoring: ExecutionMonitoringResult
    reconciliation: QueueProviderExecutionReconciliation | None


@runtime_checkable
class ProviderExecutionHandleRestorer(Protocol):
    """Adapter capability for rebuilding a transient handle from durable identity."""

    def restore_handle(self, job: DurableExecutionJob) -> ProviderExecutionHandle:
        """Reconstruct only transient provider state; never queue authority."""
        ...


class ExecutionMonitoringError(RuntimeError):
    """Raised when durable execution monitoring cannot be performed safely."""


class LiveExecutionMonitoringService:
    """Re-query durable provider jobs without fabricating Phase 19 authority."""

    def __init__(
        self,
        execution_jobs: DurableExecutionJobService,
        adapters: ProviderExecutionAdapterRegistry,
        policy: ExecutionMonitoringPolicy | None = None,
    ) -> None:
        self.execution_jobs = execution_jobs
        self.adapters = adapters
        self.policy = policy or ExecutionMonitoringPolicy()

    def inspect(
        self, execution_id: str, *, now: datetime | None = None
    ) -> ExecutionMonitoringResult:
        """Reconstruct, query, and durably record one provider execution."""
        current = now or datetime.now(UTC)
        job = self.execution_jobs.require(execution_id)
        if job.terminal:
            return ExecutionMonitoringResult(
                execution_job=job,
                disposition=ExecutionMonitoringDisposition.TERMINAL,
                recovery_action=ExecutionRecoveryAction.NONE,
                observed_at=current,
                provider_observed=False,
                message="durable execution is already terminal",
            )
        if job.provider_job_id is None:
            return ExecutionMonitoringResult(
                execution_job=job,
                disposition=ExecutionMonitoringDisposition.RECONCILIATION_REQUIRED,
                recovery_action=ExecutionRecoveryAction.REQUIRE_OPERATOR_REVIEW,
                observed_at=current,
                provider_observed=False,
                message="execution has no provider job identity to query",
            )

        was_stale = self._is_stale(job, current)
        adapter = self.adapters.require(job.provider_id)
        if not isinstance(adapter, ProviderExecutionHandleRestorer):
            raise ExecutionMonitoringError(
                f"Provider adapter cannot restore durable execution handles: {job.provider_id}"
            )
        handle = adapter.restore_handle(job)
        try:
            refreshed = adapter.monitor(handle)
        except Exception as exc:
            return ExecutionMonitoringResult(
                execution_job=job,
                disposition=ExecutionMonitoringDisposition.PROVIDER_UNREACHABLE,
                recovery_action=(
                    ExecutionRecoveryAction.REQUIRE_OPERATOR_REVIEW
                    if was_stale
                    else ExecutionRecoveryAction.RETRY_PROVIDER_QUERY
                ),
                observed_at=current,
                provider_observed=False,
                message=str(exc) or exc.__class__.__name__,
                handle=handle,
            )

        observed = self.execution_jobs.observe(job.execution_id, refreshed, now=current)
        if observed.terminal:
            return ExecutionMonitoringResult(
                execution_job=observed,
                disposition=ExecutionMonitoringDisposition.RECONCILIATION_REQUIRED,
                recovery_action=ExecutionRecoveryAction.RECONCILE_QUEUE,
                observed_at=current,
                provider_observed=True,
                message=f"provider reports terminal state: {observed.state.value}",
                handle=refreshed,
            )
        return ExecutionMonitoringResult(
            execution_job=observed,
            disposition=(
                ExecutionMonitoringDisposition.STALE_ACTIVE
                if was_stale
                else ExecutionMonitoringDisposition.ACTIVE
            ),
            recovery_action=ExecutionRecoveryAction.CONTINUE_MONITORING,
            observed_at=current,
            provider_observed=True,
            message=(
                "stale durable execution was successfully re-observed as active"
                if was_stale
                else "provider execution remains active"
            ),
            handle=refreshed,
        )

    def inspect_active(
        self, *, now: datetime | None = None
    ) -> tuple[ExecutionMonitoringResult, ...]:
        """Inspect all durable non-terminal executions in deterministic identity order."""
        current = now or datetime.now(UTC)
        return tuple(
            self.inspect(job.execution_id, now=current) for job in self.execution_jobs.list_active()
        )

    def recover_live(
        self,
        queue: ProductionQueue,
        execution_id: str,
        queue_service: QueueProviderExecutionService,
        *,
        lease_duration_seconds: float,
        now: datetime | None = None,
    ) -> LiveExecutionRecoveryResult:
        """Monitor and reconcile only when the original live Phase 19 lease still exists."""
        current = now or datetime.now(UTC)
        monitored = self.inspect(execution_id, now=current)
        handle = monitored.handle
        job = monitored.execution_job
        if (
            handle is None
            or monitored.disposition is ExecutionMonitoringDisposition.PROVIDER_UNREACHABLE
        ):
            return LiveExecutionRecoveryResult(monitored, None)

        lease = queue_service.runtime.leases.active_for_entry(
            job.queue_id,
            job.entry_id,
            now=current,
        )
        if lease is None or lease.lease_id != job.lease_id:
            detached = ExecutionMonitoringResult(
                execution_job=job,
                disposition=ExecutionMonitoringDisposition.RECONCILIATION_REQUIRED,
                recovery_action=ExecutionRecoveryAction.RECONCILE_QUEUE,
                observed_at=current,
                provider_observed=monitored.provider_observed,
                message="provider state observed but original Phase 19 lease is unavailable",
                handle=handle,
            )
            return LiveExecutionRecoveryResult(detached, None)

        reconciled = queue_service.reconcile(
            queue,
            job.entry_id,
            lease.lease_id,
            handle,
            lease_duration_seconds=lease_duration_seconds,
            now=current,
        )
        final_job = reconciled.execution_job or self.execution_jobs.require(job.execution_id)
        disposition = (
            ExecutionMonitoringDisposition.TERMINAL
            if reconciled.terminal
            else ExecutionMonitoringDisposition.ACTIVE
        )
        final = ExecutionMonitoringResult(
            execution_job=final_job,
            disposition=disposition,
            recovery_action=(
                ExecutionRecoveryAction.NONE
                if reconciled.terminal
                else ExecutionRecoveryAction.CONTINUE_MONITORING
            ),
            observed_at=current,
            provider_observed=True,
            message=(
                "provider terminal state reconciled to ProductionQueue"
                if reconciled.terminal
                else "provider execution monitored and Phase 19 lease renewed"
            ),
            handle=reconciled.handle,
        )
        return LiveExecutionRecoveryResult(final, reconciled)

    def _is_stale(self, job: DurableExecutionJob, now: datetime) -> bool:
        threshold = timedelta(seconds=self.policy.stale_after_seconds)
        return now - job.updated_at > threshold
