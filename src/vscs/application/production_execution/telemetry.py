"""Provider-neutral live production telemetry contracts for Phase 20.15.2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class ProductionTelemetryState(StrEnum):
    """Read-only execution states shown by the live production monitor."""

    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProductionDeviceTelemetry:
    """Provider-neutral device observation reported by an execution provider."""

    name: str
    kind: str = "device"
    total_memory_bytes: int | None = None
    free_memory_bytes: int | None = None
    framework_total_memory_bytes: int | None = None
    framework_free_memory_bytes: int | None = None
    utilization_percent: float | None = None
    metrics: tuple[tuple[str, str], ...] = ()

    @property
    def used_memory_bytes(self) -> int | None:
        if self.total_memory_bytes is None or self.free_memory_bytes is None:
            return None
        return max(0, self.total_memory_bytes - self.free_memory_bytes)


@dataclass(frozen=True, slots=True)
class ProductionTelemetrySnapshot:
    """One read-only observation of current or durable production execution state."""

    task_id: str
    state: ProductionTelemetryState
    live: bool
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    execution_id: str | None = None
    provider_id: str | None = None
    provider_job_id: str | None = None
    resource_id: str | None = None
    queue_entry_id: str | None = None
    stage: str = ""
    current_node: str | None = None
    progress: float | None = None
    step_current: int | None = None
    step_total: int | None = None
    elapsed_seconds: float | None = None
    estimated_remaining_seconds: float | None = None
    queue_state: str = "unknown"
    queue_position: int | None = None
    queue_pending_count: int = 0
    queue_running_count: int = 0
    provider_healthy: bool | None = None
    provider_endpoint: str | None = None
    devices: tuple[ProductionDeviceTelemetry, ...] = ()
    system_metrics: tuple[tuple[str, str], ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id cannot be blank")
        if self.progress is not None and not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")
        if self.step_current is not None and self.step_current < 0:
            raise ValueError("step_current cannot be negative")
        if self.step_total is not None and self.step_total < 1:
            raise ValueError("step_total must be positive")
        if self.step_current is not None and self.step_total is None:
            raise ValueError("step_total is required when step_current is supplied")
        if (
            self.step_current is not None
            and self.step_total is not None
            and self.step_current > self.step_total
        ):
            raise ValueError("step_current cannot exceed step_total")
        if self.elapsed_seconds is not None and self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds cannot be negative")
        if self.estimated_remaining_seconds is not None and self.estimated_remaining_seconds < 0:
            raise ValueError("estimated_remaining_seconds cannot be negative")
        if self.queue_pending_count < 0 or self.queue_running_count < 0:
            raise ValueError("queue counts cannot be negative")
        if self.queue_position is not None and self.queue_position < 1:
            raise ValueError("queue_position must be positive")

    @property
    def terminal(self) -> bool:
        return self.state in {
            ProductionTelemetryState.COMPLETED,
            ProductionTelemetryState.FAILED,
            ProductionTelemetryState.CANCELLED,
        }
