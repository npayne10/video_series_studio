"""Recovery policies and reconciliation for interrupted production work."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .executors import ExecutionLease
from .models import ProductionPipeline, ProductionStage, ProductionState
from .queue import RenderQueueEngine
from .queue_models import QueueState, RenderQueue, RenderQueueEntry


class OutputStatus(StrEnum):
    """Observed state of one expected production output."""

    PRESENT = "present"
    MISSING = "missing"
    CORRUPT = "corrupt"
    UNKNOWN = "unknown"


class RecoveryAction(StrEnum):
    """Recovery action applied to one queue entry."""

    NONE = "none"
    RELEASE_CLAIM = "release_claim"
    RETRY = "retry"
    FAIL = "fail"
    COMPLETE = "complete"
    RESET = "reset"
    CANCEL = "cancel"


class RecoveryReason(StrEnum):
    """Reason for one automatic or manual recovery decision."""

    EXPIRED_LEASE = "expired_lease"
    ABANDONED_CLAIM = "abandoned_claim"
    INTERRUPTED_WORKER = "interrupted_worker"
    MISSING_OUTPUT = "missing_output"
    CORRUPT_OUTPUT = "corrupt_output"
    OUTPUT_PRESENT = "output_present"
    ATTEMPTS_EXHAUSTED = "attempts_exhausted"
    MANUAL_ACTION = "manual_action"


@dataclass(frozen=True, slots=True)
class OutputObservation:
    """Observed output state for one render job."""

    job_id: str
    status: OutputStatus
    output_path: str | None = None
    checksum: str | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """One recovery decision for a queue entry."""

    entry_id: str
    job_id: str
    action: RecoveryAction
    reason: RecoveryReason
    message: str
    automatic: bool = True


@dataclass(frozen=True, slots=True)
class RecoveryEvent:
    """Auditable event emitted by the recovery engine."""

    event_id: str
    occurred_at: datetime
    entry_id: str
    job_id: str
    action: RecoveryAction
    reason: RecoveryReason
    message: str
    automatic: bool


@dataclass(frozen=True, slots=True)
class ProductionRecoveryResult:
    """Recovered queue and pipeline plus decisions and audit events."""

    queue: RenderQueue
    pipeline: ProductionPipeline
    decisions: tuple[RecoveryDecision, ...]
    events: tuple[RecoveryEvent, ...]


@dataclass(frozen=True, slots=True)
class ProductionRecoveryConfig:
    """Policy controlling automatic production recovery."""

    retry_delay_seconds: float = 0.0
    abandon_claim_after_seconds: float = 300.0
    complete_when_output_present: bool = True
    retry_missing_outputs: bool = True
    retry_corrupt_outputs: bool = True

    def __post_init__(self) -> None:
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds must not be negative")
        if self.abandon_claim_after_seconds <= 0:
            raise ValueError("abandon_claim_after_seconds must be positive")


class ProductionRecoveryError(ValueError):
    """Raised when a recovery action cannot be applied."""


class ProductionRecoveryEngine:
    """Reconcile persisted production state after interruption or restart."""

    def __init__(
        self,
        config: ProductionRecoveryConfig | None = None,
        queue_engine: RenderQueueEngine | None = None,
    ) -> None:
        self.config = config or ProductionRecoveryConfig()
        self.queue_engine = queue_engine or RenderQueueEngine()

    def reconcile(
        self,
        pipeline: ProductionPipeline,
        queue: RenderQueue,
        *,
        leases: tuple[ExecutionLease, ...] = (),
        outputs: tuple[OutputObservation, ...] = (),
        active_worker_ids: frozenset[str] | None = None,
        now: datetime | None = None,
    ) -> ProductionRecoveryResult:
        """Recover interrupted queue state and reconcile rendering nodes."""
        current = now or datetime.now(UTC)
        workers = active_worker_ids or frozenset()
        lease_by_job = {lease.job_id: lease for lease in leases}
        output_by_job = {output.job_id: output for output in outputs}
        recovered_entries: list[RenderQueueEntry] = []
        decisions: list[RecoveryDecision] = []

        for entry in queue.entries:
            recovered, decision = self._recover_entry(
                entry,
                lease_by_job.get(entry.job_id),
                output_by_job.get(entry.job_id),
                workers,
                current,
            )
            recovered_entries.append(recovered)
            if decision is not None:
                decisions.append(decision)

        recovered_queue = replace(queue, entries=tuple(recovered_entries))
        recovered_queue = self.queue_engine.refresh(recovered_queue, current)
        recovered_pipeline = self._reconcile_pipeline(pipeline, recovered_queue)
        events = tuple(
            self._event(index, decision, current)
            for index, decision in enumerate(decisions, start=1)
        )
        return ProductionRecoveryResult(
            queue=recovered_queue,
            pipeline=recovered_pipeline,
            decisions=tuple(decisions),
            events=events,
        )

    def apply_manual(
        self,
        pipeline: ProductionPipeline,
        queue: RenderQueue,
        entry_id: str,
        action: RecoveryAction,
        *,
        message: str = "Manual recovery action",
        now: datetime | None = None,
    ) -> ProductionRecoveryResult:
        """Apply one explicit manual recovery action."""
        current = now or datetime.now(UTC)
        entry = queue.entry(entry_id)
        if entry is None:
            raise ProductionRecoveryError(f"Queue entry not found: {entry_id}")
        recovered = self._apply_action(entry, action, current, message)
        recovered_queue = replace(
            queue,
            entries=tuple(
                recovered if item.entry_id == entry_id else item for item in queue.entries
            ),
        )
        recovered_queue = self.queue_engine.refresh(recovered_queue, current)
        recovered_pipeline = self._reconcile_pipeline(pipeline, recovered_queue)
        decision = RecoveryDecision(
            entry_id=entry.entry_id,
            job_id=entry.job_id,
            action=action,
            reason=RecoveryReason.MANUAL_ACTION,
            message=message,
            automatic=False,
        )
        return ProductionRecoveryResult(
            queue=recovered_queue,
            pipeline=recovered_pipeline,
            decisions=(decision,),
            events=(self._event(1, decision, current),),
        )

    def _recover_entry(
        self,
        entry: RenderQueueEntry,
        lease: ExecutionLease | None,
        output: OutputObservation | None,
        active_worker_ids: frozenset[str],
        now: datetime,
    ) -> tuple[RenderQueueEntry, RecoveryDecision | None]:
        if entry.state in {QueueState.CANCELLED, QueueState.FAILED}:
            return entry, None
        if entry.state is QueueState.COMPLETED:
            return self._recover_completed_output(entry, output, now)
        if (
            output is not None
            and output.status is OutputStatus.PRESENT
            and self.config.complete_when_output_present
        ):
            recovered = self._mark_completed(entry, now)
            return recovered, self._decision(
                entry,
                RecoveryAction.COMPLETE,
                RecoveryReason.OUTPUT_PRESENT,
                "Existing output verified; marked entry complete",
            )
        if entry.state is QueueState.CLAIMED:
            age = (now - entry.updated_at).total_seconds()
            lease_expired = lease is not None and lease.is_expired(now)
            worker_missing = entry.claimed_by not in active_worker_ids
            if lease_expired:
                return self._retry_or_fail(
                    entry,
                    now,
                    RecoveryReason.EXPIRED_LEASE,
                    "Expired lease released for recovery",
                )
            if worker_missing and age >= self.config.abandon_claim_after_seconds:
                return self._retry_or_fail(
                    entry,
                    now,
                    RecoveryReason.ABANDONED_CLAIM,
                    "Abandoned worker claim released for recovery",
                )
        if entry.state is QueueState.RUNNING:
            lease_expired = lease is None or lease.is_expired(now)
            worker_missing = entry.claimed_by not in active_worker_ids
            if lease_expired or worker_missing:
                return self._interrupt_running_entry(entry, now)
        return entry, None

    def _recover_completed_output(
        self,
        entry: RenderQueueEntry,
        output: OutputObservation | None,
        now: datetime,
    ) -> tuple[RenderQueueEntry, RecoveryDecision | None]:
        if output is None or output.status is OutputStatus.UNKNOWN:
            return entry, None
        if output.status is OutputStatus.PRESENT:
            return entry, None
        if output.status is OutputStatus.MISSING and self.config.retry_missing_outputs:
            return self._retry_or_fail(
                entry,
                now,
                RecoveryReason.MISSING_OUTPUT,
                "Completed entry output is missing",
            )
        if output.status is OutputStatus.CORRUPT and self.config.retry_corrupt_outputs:
            return self._retry_or_fail(
                entry,
                now,
                RecoveryReason.CORRUPT_OUTPUT,
                "Completed entry output is corrupt",
            )
        return entry, None

    def _interrupt_running_entry(
        self,
        entry: RenderQueueEntry,
        now: datetime,
    ) -> tuple[RenderQueueEntry, RecoveryDecision]:
        attempts = entry.attempts
        if attempts and attempts[-1].completed_at is None:
            latest = replace(
                attempts[-1],
                completed_at=now,
                succeeded=False,
                error_message="Execution interrupted during recovery",
            )
            attempts = (*attempts[:-1], latest)
        interrupted = replace(entry, attempts=attempts)
        return self._retry_or_fail(
            interrupted,
            now,
            RecoveryReason.INTERRUPTED_WORKER,
            "Interrupted running entry recovered",
        )

    def _retry_or_fail(
        self,
        entry: RenderQueueEntry,
        now: datetime,
        reason: RecoveryReason,
        message: str,
    ) -> tuple[RenderQueueEntry, RecoveryDecision]:
        retryable = entry.attempt_count < entry.maximum_attempts
        if retryable:
            recovered = replace(
                entry,
                state=QueueState.RETRYING,
                claimed_by=None,
                available_at=now + timedelta(seconds=self.config.retry_delay_seconds),
                updated_at=now,
            )
            action = RecoveryAction.RETRY
        else:
            recovered = replace(
                entry,
                state=QueueState.FAILED,
                claimed_by=None,
                available_at=None,
                updated_at=now,
            )
            action = RecoveryAction.FAIL
            reason = RecoveryReason.ATTEMPTS_EXHAUSTED
            message = f"{message}; attempts exhausted"
        return recovered, self._decision(entry, action, reason, message)

    @staticmethod
    def _mark_completed(entry: RenderQueueEntry, now: datetime) -> RenderQueueEntry:
        attempts = entry.attempts
        if attempts and attempts[-1].completed_at is None:
            latest = replace(attempts[-1], completed_at=now, succeeded=True)
            attempts = (*attempts[:-1], latest)
        return replace(
            entry,
            state=QueueState.COMPLETED,
            attempts=attempts,
            claimed_by=None,
            available_at=None,
            updated_at=now,
        )

    def _apply_action(
        self,
        entry: RenderQueueEntry,
        action: RecoveryAction,
        now: datetime,
        message: str,
    ) -> RenderQueueEntry:
        if action is RecoveryAction.RETRY:
            recovered, _ = self._retry_or_fail(
                entry,
                now,
                RecoveryReason.MANUAL_ACTION,
                message,
            )
            return recovered
        if action is RecoveryAction.FAIL:
            return replace(
                entry,
                state=QueueState.FAILED,
                claimed_by=None,
                available_at=None,
                updated_at=now,
            )
        if action is RecoveryAction.COMPLETE:
            return self._mark_completed(entry, now)
        if action in {RecoveryAction.RESET, RecoveryAction.RELEASE_CLAIM}:
            return replace(
                entry,
                state=QueueState.WAITING,
                claimed_by=None,
                available_at=None,
                updated_at=now,
            )
        if action is RecoveryAction.CANCEL:
            return replace(
                entry,
                state=QueueState.CANCELLED,
                claimed_by=None,
                available_at=None,
                updated_at=now,
            )
        if action is RecoveryAction.NONE:
            return entry
        raise ProductionRecoveryError(f"Unsupported recovery action: {action}")

    @staticmethod
    def _reconcile_pipeline(
        pipeline: ProductionPipeline,
        queue: RenderQueue,
    ) -> ProductionPipeline:
        states_by_clip = {entry.clip_id: entry.state for entry in queue.entries}
        nodes = []
        for node in pipeline.nodes:
            if node.stage is not ProductionStage.RENDERING or node.clip_id is None:
                nodes.append(node)
                continue
            queue_state = states_by_clip.get(node.clip_id)
            mapped = ProductionRecoveryEngine._pipeline_state(queue_state)
            nodes.append(replace(node, state=mapped if mapped is not None else node.state))
        return replace(pipeline, nodes=tuple(nodes))

    @staticmethod
    def _pipeline_state(state: QueueState | None) -> ProductionState | None:
        mapping = {
            QueueState.WAITING: ProductionState.PENDING,
            QueueState.READY: ProductionState.READY,
            QueueState.CLAIMED: ProductionState.RUNNING,
            QueueState.RUNNING: ProductionState.RUNNING,
            QueueState.RETRYING: ProductionState.PENDING,
            QueueState.COMPLETED: ProductionState.COMPLETED,
            QueueState.FAILED: ProductionState.FAILED,
            QueueState.CANCELLED: ProductionState.CANCELLED,
            QueueState.BLOCKED: ProductionState.BLOCKED,
        }
        return mapping.get(state)

    @staticmethod
    def _decision(
        entry: RenderQueueEntry,
        action: RecoveryAction,
        reason: RecoveryReason,
        message: str,
    ) -> RecoveryDecision:
        return RecoveryDecision(
            entry_id=entry.entry_id,
            job_id=entry.job_id,
            action=action,
            reason=reason,
            message=message,
        )

    @staticmethod
    def _event(
        index: int,
        decision: RecoveryDecision,
        occurred_at: datetime,
    ) -> RecoveryEvent:
        return RecoveryEvent(
            event_id=f"RECOVERY-{occurred_at.strftime('%Y%m%d%H%M%S')}-{index:04d}",
            occurred_at=occurred_at,
            entry_id=decision.entry_id,
            job_id=decision.job_id,
            action=decision.action,
            reason=decision.reason,
            message=decision.message,
            automatic=decision.automatic,
        )
