"""Bind Phase 19 queue/lease authority to provider execution context."""

from __future__ import annotations

from datetime import UTC, datetime

from vscs.application.production_tasks import (
    ProductionExecutionLease,
    ProductionQueue,
    ProductionQueueState,
    ProductionTask,
)

from .models import ProviderExecutionContext


class ProviderExecutionBindingError(ValueError):
    """Raised when provider execution is not backed by valid Phase 19 runtime authority."""


class ProviderExecutionContextFactory:
    """Create immutable provider execution context from a running queue attempt."""

    def bind(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease: ProductionExecutionLease,
        task: ProductionTask,
        *,
        now: datetime | None = None,
    ) -> ProviderExecutionContext:
        current = now or datetime.now(UTC)
        entry = queue.entry(entry_id)
        if entry is None:
            raise ProviderExecutionBindingError(f"ProductionQueue entry not found: {entry_id}")
        if entry.state is not ProductionQueueState.RUNNING:
            raise ProviderExecutionBindingError(
                f"Provider execution requires a RUNNING ProductionQueue entry: {entry.entry_id}"
            )
        if entry.claimed_by is None:
            raise ProviderExecutionBindingError("RUNNING ProductionQueue entry has no worker claim")
        if not entry.attempts or entry.attempts[-1].completed_at is not None:
            raise ProviderExecutionBindingError(
                "Provider execution requires an active ProductionQueue attempt"
            )
        if queue.production_id != task.production_id or entry.task_id != task.task_id:
            raise ProviderExecutionBindingError(
                "ProductionTask authority does not match ProductionQueue execution"
            )
        if lease.is_expired(current):
            raise ProviderExecutionBindingError(
                f"Production execution lease is expired: {lease.lease_id}"
            )
        if lease.queue_id != queue.queue_id or lease.entry_id != entry.entry_id:
            raise ProviderExecutionBindingError(
                "Production execution lease does not own this ProductionQueue entry"
            )
        if lease.task_id != task.task_id or lease.worker_id != entry.claimed_by:
            raise ProviderExecutionBindingError(
                "Production execution lease does not match task/worker ownership"
            )
        latest_attempt = entry.attempts[-1]
        if latest_attempt.worker_id != entry.claimed_by:
            raise ProviderExecutionBindingError(
                "ProductionQueue attempt worker does not match current claim"
            )

        return ProviderExecutionContext(
            execution_id=(
                f"PEX-{queue.queue_id}-{entry.entry_id}-A{latest_attempt.attempt_number:03d}"
            ),
            production_id=queue.production_id,
            task_id=task.task_id,
            queue_id=queue.queue_id,
            entry_id=entry.entry_id,
            resource_id=entry.resource_id,
            worker_id=entry.claimed_by,
            lease_id=lease.lease_id,
            attempt_number=latest_attempt.attempt_number,
            task_type=task.task_type,
            required_capabilities=tuple(
                sorted(task.capabilities, key=lambda capability: capability.value)
            ),
            authority_fingerprint=task.authority.fingerprint,
        )
