"""Persistence contract for durable provider execution jobs."""

from __future__ import annotations

from typing import Protocol

from .execution_records import DurableExecutionJob


class DurableExecutionJobRepositoryError(RuntimeError):
    """Raised when durable execution persistence cannot complete safely."""


class DurableExecutionJobRepository(Protocol):
    """Persistence boundary for provider execution attempts."""

    def get(self, execution_id: str) -> DurableExecutionJob | None:
        """Return one execution job by stable VSCS execution identity."""
        ...

    def save(self, job: DurableExecutionJob) -> DurableExecutionJob:
        """Create or replace one durable execution job."""
        ...

    def list_for_task(self, task_id: str) -> tuple[DurableExecutionJob, ...]:
        """Return execution attempts for one ProductionTask in deterministic order."""
        ...

    def list_for_queue_entry(self, queue_id: str, entry_id: str) -> tuple[DurableExecutionJob, ...]:
        """Return attempts for one queue entry in deterministic attempt order."""
        ...

    def list_for_provider(self, provider_id: str) -> tuple[DurableExecutionJob, ...]:
        """Return jobs submitted or prepared for one provider."""
        ...

    def list_active(self) -> tuple[DurableExecutionJob, ...]:
        """Return non-terminal execution jobs for later restart reconciliation."""
        ...
