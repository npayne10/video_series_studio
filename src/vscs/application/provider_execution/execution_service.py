"""Application service for durable provider execution jobs."""

from __future__ import annotations

from datetime import datetime

from .execution_records import DurableExecutionJob, DurableExecutionJobTracker
from .execution_repository import DurableExecutionJobRepository, DurableExecutionJobRepositoryError
from .models import ProviderExecutionContext, ProviderExecutionHandle


class DurableExecutionJobService:
    """Persist immutable execution snapshots without replacing queue authority."""

    def __init__(
        self,
        repository: DurableExecutionJobRepository,
        tracker: DurableExecutionJobTracker | None = None,
    ) -> None:
        self.repository = repository
        self.tracker = tracker or DurableExecutionJobTracker()

    def prepare(
        self,
        context: ProviderExecutionContext,
        provider_id: str,
        *,
        render_request_id: str,
        workflow_id: str,
        now: datetime | None = None,
    ) -> DurableExecutionJob:
        if self.repository.get(context.execution_id) is not None:
            raise DurableExecutionJobRepositoryError(
                f"DurableExecutionJob already exists: {context.execution_id}"
            )
        job = self.tracker.prepare(
            context,
            provider_id,
            render_request_id=render_request_id,
            workflow_id=workflow_id,
            now=now,
        )
        return self.repository.save(job)

    def observe(
        self,
        execution_id: str,
        handle: ProviderExecutionHandle,
        *,
        now: datetime | None = None,
    ) -> DurableExecutionJob:
        job = self.require(execution_id)
        return self.repository.save(self.tracker.observe(job, handle, now=now))

    def submission_failed(
        self,
        execution_id: str,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> DurableExecutionJob:
        job = self.require(execution_id)
        return self.repository.save(self.tracker.submission_failed(job, reason, now=now))

    def get(self, execution_id: str) -> DurableExecutionJob | None:
        return self.repository.get(execution_id)

    def require(self, execution_id: str) -> DurableExecutionJob:
        normalized = execution_id.strip()
        if not normalized:
            raise DurableExecutionJobRepositoryError("execution_id cannot be blank")
        job = self.repository.get(normalized)
        if job is None:
            raise DurableExecutionJobRepositoryError(
                f"DurableExecutionJob not found: {normalized}"
            )
        return job

    def list_for_task(self, task_id: str) -> tuple[DurableExecutionJob, ...]:
        return self.repository.list_for_task(task_id)

    def list_for_queue_entry(self, queue_id: str, entry_id: str) -> tuple[DurableExecutionJob, ...]:
        return self.repository.list_for_queue_entry(queue_id, entry_id)

    def list_for_provider(self, provider_id: str) -> tuple[DurableExecutionJob, ...]:
        return self.repository.list_for_provider(provider_id)

    def list_active(self) -> tuple[DurableExecutionJob, ...]:
        return self.repository.list_active()
