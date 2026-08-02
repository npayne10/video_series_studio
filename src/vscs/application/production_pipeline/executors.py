"""Provider-neutral production executor contracts and registry."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol

from vscs.application.acpp import RenderCapability, RenderJob


class ExecutorErrorCode(StrEnum):
    """Provider-neutral executor failure categories."""

    UNSUPPORTED_JOB = "unsupported_job"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    CANCELLED = "cancelled"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True, slots=True)
class WorkerIdentity:
    """Identity and capability declaration for one production worker."""

    worker_id: str
    executor_id: str
    capabilities: frozenset[RenderCapability]
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.worker_id.strip():
            raise ValueError("worker_id must not be empty")
        if not self.executor_id.strip():
            raise ValueError("executor_id must not be empty")


@dataclass(frozen=True, slots=True)
class ExecutionLease:
    """Time-bound worker ownership for one render job."""

    lease_id: str
    worker_id: str
    job_id: str
    acquired_at: datetime
    expires_at: datetime
    last_heartbeat_at: datetime

    @property
    def expired(self) -> bool:
        """Return whether the lease is expired at current UTC time."""
        return self.expires_at <= datetime.now(UTC)

    def is_expired(self, now: datetime) -> bool:
        """Return whether the lease is expired at a supplied time."""
        return self.expires_at <= now


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """One executor invocation contract."""

    job: RenderJob
    worker: WorkerIdentity
    lease: ExecutionLease
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Provider-neutral result returned by an executor."""

    job_id: str
    worker_id: str
    succeeded: bool
    started_at: datetime
    completed_at: datetime
    output_paths: tuple[str, ...] = ()
    error_code: ExecutorErrorCode | None = None
    error_message: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.succeeded and self.error_code is not None:
            raise ValueError("Successful execution may not include an error code")
        if not self.succeeded and self.error_code is None:
            raise ValueError("Failed execution requires an error code")


class ProductionExecutor(Protocol):
    """Contract implemented by production render executors."""

    @property
    def executor_id(self) -> str:
        """Return stable executor identity."""
        ...

    @property
    def capabilities(self) -> frozenset[RenderCapability]:
        """Return supported renderer-neutral capabilities."""
        ...

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Execute one render job synchronously."""
        ...


class ExecutorRegistryError(ValueError):
    """Raised for invalid executor registration or matching."""


class ExecutorRegistry:
    """Register and select compatible production executors."""

    def __init__(self) -> None:
        self._executors: dict[str, ProductionExecutor] = {}

    def register(self, executor: ProductionExecutor) -> None:
        """Register one executor by stable identity."""
        executor_id = executor.executor_id.strip()
        if not executor_id:
            raise ExecutorRegistryError("executor_id must not be empty")
        if executor_id in self._executors:
            raise ExecutorRegistryError(f"Executor already registered: {executor_id}")
        self._executors[executor_id] = executor

    def get(self, executor_id: str) -> ProductionExecutor | None:
        """Return one registered executor."""
        return self._executors.get(executor_id)

    def compatible(self, job: RenderJob) -> tuple[ProductionExecutor, ...]:
        """Return executors supporting every job capability."""
        required = frozenset(job.required_capabilities)
        return tuple(
            executor
            for executor in self._executors.values()
            if required.issubset(executor.capabilities)
        )

    def select(self, job: RenderJob) -> ProductionExecutor:
        """Select the first compatible executor in registration order."""
        matches = self.compatible(job)
        if not matches:
            raise ExecutorRegistryError(
                f"No executor supports render job capabilities: {job.job_id}"
            )
        return matches[0]


class LeaseManager:
    """Create and renew time-bound execution leases."""

    def acquire(
        self,
        job_id: str,
        worker_id: str,
        *,
        duration_seconds: float,
        now: datetime | None = None,
    ) -> ExecutionLease:
        """Create one execution lease."""
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        current = now or datetime.now(UTC)
        return ExecutionLease(
            lease_id=f"LEASE-{job_id}-{worker_id}",
            worker_id=worker_id,
            job_id=job_id,
            acquired_at=current,
            expires_at=current + timedelta(seconds=duration_seconds),
            last_heartbeat_at=current,
        )

    def heartbeat(
        self,
        lease: ExecutionLease,
        *,
        duration_seconds: float,
        now: datetime | None = None,
    ) -> ExecutionLease:
        """Renew an active lease."""
        current = now or datetime.now(UTC)
        if lease.is_expired(current):
            raise ValueError(f"Cannot renew expired lease: {lease.lease_id}")
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        return replace(
            lease,
            expires_at=current + timedelta(seconds=duration_seconds),
            last_heartbeat_at=current,
        )


@dataclass(slots=True)
class MockProductionExecutor:
    """Deterministic executor used by orchestration integration tests."""

    executor_id: str = "mock"
    capabilities: frozenset[RenderCapability] = field(
        default_factory=lambda: frozenset(RenderCapability)
    )
    succeed: bool = True
    output_path: str = "mock/output.mp4"
    error_code: ExecutorErrorCode = ExecutorErrorCode.PROVIDER_ERROR

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Return a deterministic success or failure result."""
        started = request.submitted_at
        completed = started + timedelta(milliseconds=1)
        if self.succeed:
            return ExecutionResult(
                job_id=request.job.job_id,
                worker_id=request.worker.worker_id,
                succeeded=True,
                started_at=started,
                completed_at=completed,
                output_paths=(self.output_path,),
            )
        return ExecutionResult(
            job_id=request.job.job_id,
            worker_id=request.worker.worker_id,
            succeeded=False,
            started_at=started,
            completed_at=completed,
            error_code=self.error_code,
            error_message="Mock executor failure",
        )
