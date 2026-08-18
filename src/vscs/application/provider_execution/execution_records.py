"""Durable provider execution job and attempt records for Phase 20.7."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from .models import ProviderExecutionContext, ProviderExecutionHandle, ProviderExecutionState


_TERMINAL_STATES = frozenset(
    {
        ProviderExecutionState.COMPLETED,
        ProviderExecutionState.FAILED,
        ProviderExecutionState.CANCELLED,
    }
)


@dataclass(frozen=True, slots=True)
class DurableExecutionEvent:
    """One durable observation in a provider execution lifecycle."""

    state: ProviderExecutionState
    observed_at: datetime
    progress: float = 0.0
    provider_job_id: str | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")
        if self.provider_job_id is not None and not self.provider_job_id.strip():
            raise ValueError("provider_job_id cannot be blank when supplied")
        if self.failure_reason is not None and not self.failure_reason.strip():
            raise ValueError("failure_reason cannot be blank when supplied")
        if self.state is ProviderExecutionState.FAILED and self.failure_reason is None:
            raise ValueError("FAILED durable execution events require failure_reason")


@dataclass(frozen=True, slots=True)
class DurableExecutionJob:
    """Restart-safe record for one queue-authorised provider execution attempt.

    A DurableExecutionJob mirrors one Phase 19 queue attempt. It is observability and
    recovery state only; it never replaces ProductionQueue authority.
    """

    execution_id: str
    production_id: str
    task_id: str
    queue_id: str
    entry_id: str
    resource_id: str
    worker_id: str
    lease_id: str
    attempt_number: int
    authority_fingerprint: str
    provider_id: str
    state: ProviderExecutionState
    created_at: datetime
    updated_at: datetime
    provider_job_id: str | None = None
    render_request_id: str | None = None
    workflow_id: str | None = None
    submitted_at: datetime | None = None
    progress: float = 0.0
    failure_reason: str | None = None
    events: tuple[DurableExecutionEvent, ...] = ()

    def __post_init__(self) -> None:
        for field_name, value in (
            ("execution_id", self.execution_id),
            ("production_id", self.production_id),
            ("task_id", self.task_id),
            ("queue_id", self.queue_id),
            ("entry_id", self.entry_id),
            ("resource_id", self.resource_id),
            ("worker_id", self.worker_id),
            ("lease_id", self.lease_id),
            ("authority_fingerprint", self.authority_fingerprint),
            ("provider_id", self.provider_id),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")
        if self.provider_job_id is not None and not self.provider_job_id.strip():
            raise ValueError("provider_job_id cannot be blank when supplied")
        if self.render_request_id is not None and not self.render_request_id.strip():
            raise ValueError("render_request_id cannot be blank when supplied")
        if self.workflow_id is not None and not self.workflow_id.strip():
            raise ValueError("workflow_id cannot be blank when supplied")
        if self.failure_reason is not None and not self.failure_reason.strip():
            raise ValueError("failure_reason cannot be blank when supplied")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")
        if not self.events:
            raise ValueError("durable execution jobs require at least one event")
        if self.events[-1].state is not self.state:
            raise ValueError("latest durable execution event must match job state")
        if self.events[-1].progress != self.progress:
            raise ValueError("latest durable execution event must match job progress")
        if self.events[-1].provider_job_id != self.provider_job_id:
            raise ValueError("latest durable execution event must match provider_job_id")
        if self.events[-1].failure_reason != self.failure_reason:
            raise ValueError("latest durable execution event must match failure_reason")
        previous = self.created_at
        for event in self.events:
            if event.observed_at < previous:
                raise ValueError("durable execution events must be chronological")
            previous = event.observed_at
        if self.state is ProviderExecutionState.FAILED and self.failure_reason is None:
            raise ValueError("FAILED durable execution jobs require failure_reason")
        if self.provider_job_id is None and self.state not in {
            ProviderExecutionState.PREPARING,
            ProviderExecutionState.FAILED,
        }:
            raise ValueError("provider_job_id is required after provider submission")

    @property
    def terminal(self) -> bool:
        return self.state in _TERMINAL_STATES


class DurableExecutionJobError(RuntimeError):
    """Raised when durable provider execution state cannot be reconciled safely."""


class DurableExecutionJobTracker:
    """Create immutable durable execution snapshots from runtime execution observations."""

    def prepare(
        self,
        context: ProviderExecutionContext,
        provider_id: str,
        *,
        render_request_id: str,
        workflow_id: str,
        now: datetime | None = None,
    ) -> DurableExecutionJob:
        current = now or datetime.now(UTC)
        normalized_provider = provider_id.strip()
        if not normalized_provider:
            raise DurableExecutionJobError("provider_id cannot be blank")
        event = DurableExecutionEvent(
            state=ProviderExecutionState.PREPARING,
            observed_at=current,
        )
        return DurableExecutionJob(
            execution_id=context.execution_id,
            production_id=context.production_id,
            task_id=context.task_id,
            queue_id=context.queue_id,
            entry_id=context.entry_id,
            resource_id=context.resource_id,
            worker_id=context.worker_id,
            lease_id=context.lease_id,
            attempt_number=context.attempt_number,
            authority_fingerprint=context.authority_fingerprint,
            provider_id=normalized_provider,
            state=ProviderExecutionState.PREPARING,
            created_at=current,
            updated_at=current,
            render_request_id=render_request_id.strip(),
            workflow_id=workflow_id.strip(),
            events=(event,),
        )

    def observe(
        self,
        job: DurableExecutionJob,
        handle: ProviderExecutionHandle,
        *,
        now: datetime | None = None,
    ) -> DurableExecutionJob:
        self._validate_handle(job, handle)
        if job.terminal and handle.state is not job.state:
            raise DurableExecutionJobError("terminal durable execution state cannot be changed")
        current = now or datetime.now(UTC)
        submitted_at = job.submitted_at or handle.submitted_at
        failure_reason = handle.failure_reason
        if handle.state is ProviderExecutionState.FAILED and failure_reason is None:
            failure_reason = "provider execution failed"
        changed = (
            job.state is not handle.state
            or job.progress != handle.progress
            or job.provider_job_id != handle.provider_job_id
            or job.failure_reason != failure_reason
        )
        if not changed:
            return replace(job, updated_at=current, submitted_at=submitted_at)
        event = DurableExecutionEvent(
            state=handle.state,
            observed_at=current,
            progress=handle.progress,
            provider_job_id=handle.provider_job_id,
            failure_reason=failure_reason,
        )
        return replace(
            job,
            state=handle.state,
            updated_at=current,
            submitted_at=submitted_at,
            progress=handle.progress,
            provider_job_id=handle.provider_job_id,
            failure_reason=failure_reason,
            events=(*job.events, event),
        )

    def submission_failed(
        self,
        job: DurableExecutionJob,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> DurableExecutionJob:
        if job.terminal:
            raise DurableExecutionJobError("terminal durable execution state cannot be changed")
        message = reason.strip()
        if not message:
            raise DurableExecutionJobError("submission failure reason cannot be blank")
        current = now or datetime.now(UTC)
        event = DurableExecutionEvent(
            state=ProviderExecutionState.FAILED,
            observed_at=current,
            failure_reason=message,
        )
        return replace(
            job,
            state=ProviderExecutionState.FAILED,
            updated_at=current,
            failure_reason=message,
            events=(*job.events, event),
        )

    @staticmethod
    def _validate_handle(job: DurableExecutionJob, handle: ProviderExecutionHandle) -> None:
        if handle.execution_id != job.execution_id:
            raise DurableExecutionJobError("provider handle execution_id does not match durable job")
        if handle.provider_id != job.provider_id:
            raise DurableExecutionJobError("provider handle provider_id does not match durable job")
        if job.provider_job_id is not None and handle.provider_job_id != job.provider_job_id:
            raise DurableExecutionJobError("provider job identity changed during execution")
