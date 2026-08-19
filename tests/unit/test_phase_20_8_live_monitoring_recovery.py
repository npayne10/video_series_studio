"""Focused tests for Phase 20.8 live monitoring and recovery classification."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from vscs.application.production_tasks import ProductionCapability, ProductionTaskType
from vscs.application.provider_execution import (
    DurableExecutionJob,
    DurableExecutionJobService,
    DurableExecutionJobTracker,
    ExecutionMonitoringDisposition,
    ExecutionMonitoringPolicy,
    ExecutionRecoveryAction,
    LiveExecutionMonitoringService,
    ProviderExecutionAdapterRegistry,
    ProviderExecutionContext,
    ProviderExecutionHandle,
    ProviderExecutionState,
    ProviderExecutionValidation,
)

NOW = datetime(2026, 8, 18, 19, 0, tzinfo=UTC)


class MemoryExecutionRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, DurableExecutionJob] = {}

    def get(self, execution_id: str) -> DurableExecutionJob | None:
        return self.jobs.get(execution_id)

    def save(self, job: DurableExecutionJob) -> DurableExecutionJob:
        self.jobs[job.execution_id] = job
        return job

    def list_for_task(self, task_id: str) -> tuple[DurableExecutionJob, ...]:
        return tuple(job for job in self.jobs.values() if job.task_id == task_id)

    def list_for_queue_entry(self, queue_id: str, entry_id: str) -> tuple[DurableExecutionJob, ...]:
        return tuple(
            job
            for job in self.jobs.values()
            if job.queue_id == queue_id and job.entry_id == entry_id
        )

    def list_for_provider(self, provider_id: str) -> tuple[DurableExecutionJob, ...]:
        return tuple(job for job in self.jobs.values() if job.provider_id == provider_id)

    def list_active(self) -> tuple[DurableExecutionJob, ...]:
        return tuple(
            sorted(
                (job for job in self.jobs.values() if not job.terminal),
                key=lambda j: j.execution_id,
            )
        )


class RecoveringAdapter:
    provider_id = "PROVIDER-01"

    def __init__(self, state: ProviderExecutionState, *, fail_monitor: bool = False) -> None:
        self.state = state
        self.fail_monitor = fail_monitor
        self.monitor_calls = 0

    def validate(self, request: object) -> ProviderExecutionValidation:
        return ProviderExecutionValidation(True)

    def submit(self, request: object) -> ProviderExecutionHandle:
        raise AssertionError("not used")

    def monitor(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        self.monitor_calls += 1
        if self.fail_monitor:
            raise RuntimeError("provider unavailable")
        return replace(
            handle,
            state=self.state,
            progress=1.0 if self.state is ProviderExecutionState.COMPLETED else 0.5,
        )

    def cancel(self, handle: ProviderExecutionHandle) -> ProviderExecutionHandle:
        return replace(handle, state=ProviderExecutionState.CANCELLED)

    def fetch_outputs(self, handle: ProviderExecutionHandle) -> tuple[()]:
        return ()

    def restore_handle(self, job: DurableExecutionJob) -> ProviderExecutionHandle:
        assert job.provider_job_id is not None
        assert job.submitted_at is not None
        return ProviderExecutionHandle(
            execution_id=job.execution_id,
            provider_id=job.provider_id,
            provider_job_id=job.provider_job_id,
            state=job.state,
            submitted_at=job.submitted_at,
            progress=job.progress,
            failure_reason=job.failure_reason,
            metadata=job.provider_metadata,
        )


def _context() -> ProviderExecutionContext:
    return ProviderExecutionContext(
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


def _service(state: ProviderExecutionState, *, fail_monitor: bool = False):
    repository = MemoryExecutionRepository()
    jobs = DurableExecutionJobService(repository, DurableExecutionJobTracker())
    prepared = jobs.prepare(
        _context(),
        "PROVIDER-01",
        render_request_id="REQ-001",
        workflow_id="WF-001",
        now=NOW,
    )
    submitted = ProviderExecutionHandle(
        execution_id=prepared.execution_id,
        provider_id="PROVIDER-01",
        provider_job_id="prompt-001",
        state=ProviderExecutionState.QUEUED,
        submitted_at=NOW,
        metadata=(("render_job_id", "RJ-001"), ("request_id", "REQ-001")),
    )
    jobs.observe(prepared.execution_id, submitted, now=NOW)
    adapter = RecoveringAdapter(state, fail_monitor=fail_monitor)
    adapters = ProviderExecutionAdapterRegistry()
    adapters.register(adapter)
    monitoring = LiveExecutionMonitoringService(
        jobs,
        adapters,
        ExecutionMonitoringPolicy(stale_after_seconds=60),
    )
    return jobs, adapter, monitoring


def test_monitoring_persists_terminal_provider_observation() -> None:
    jobs, _adapter, monitoring = _service(ProviderExecutionState.COMPLETED)

    result = monitoring.inspect("PEX-PQ-001-PQE-001-A001", now=NOW + timedelta(seconds=30))

    assert result.disposition is ExecutionMonitoringDisposition.RECONCILIATION_REQUIRED
    assert result.recovery_action is ExecutionRecoveryAction.RECONCILE_QUEUE
    assert result.execution_job.state is ProviderExecutionState.COMPLETED
    assert jobs.require(result.execution_job.execution_id).terminal


def test_stale_active_execution_is_reobserved_without_being_failed() -> None:
    jobs, _adapter, monitoring = _service(ProviderExecutionState.RUNNING)

    result = monitoring.inspect("PEX-PQ-001-PQE-001-A001", now=NOW + timedelta(seconds=120))

    assert result.disposition is ExecutionMonitoringDisposition.STALE_ACTIVE
    assert result.recovery_action is ExecutionRecoveryAction.CONTINUE_MONITORING
    assert result.execution_job.state is ProviderExecutionState.RUNNING
    assert not jobs.require(result.execution_job.execution_id).terminal


def test_unreachable_provider_does_not_mutate_durable_execution() -> None:
    jobs, _adapter, monitoring = _service(ProviderExecutionState.RUNNING, fail_monitor=True)
    before = jobs.require("PEX-PQ-001-PQE-001-A001")

    result = monitoring.inspect(before.execution_id, now=NOW + timedelta(seconds=30))

    assert result.disposition is ExecutionMonitoringDisposition.PROVIDER_UNREACHABLE
    assert result.recovery_action is ExecutionRecoveryAction.RETRY_PROVIDER_QUERY
    assert jobs.require(before.execution_id) == before


def test_stale_unreachable_provider_requires_operator_review() -> None:
    _jobs, _adapter, monitoring = _service(ProviderExecutionState.RUNNING, fail_monitor=True)

    result = monitoring.inspect(
        "PEX-PQ-001-PQE-001-A001",
        now=NOW + timedelta(seconds=120),
    )

    assert result.disposition is ExecutionMonitoringDisposition.PROVIDER_UNREACHABLE
    assert result.recovery_action is ExecutionRecoveryAction.REQUIRE_OPERATOR_REVIEW


def test_terminal_durable_job_is_not_requeried() -> None:
    _jobs, adapter, monitoring = _service(ProviderExecutionState.COMPLETED)
    first = monitoring.inspect("PEX-PQ-001-PQE-001-A001", now=NOW + timedelta(seconds=30))
    calls = adapter.monitor_calls

    second = monitoring.inspect(first.execution_job.execution_id, now=NOW + timedelta(seconds=40))

    assert second.disposition is ExecutionMonitoringDisposition.TERMINAL
    assert adapter.monitor_calls == calls
