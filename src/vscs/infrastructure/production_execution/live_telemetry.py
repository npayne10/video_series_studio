"""Read-only ComfyUI telemetry observation for Phase 20.15.2."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from vscs.application.production_execution import (
    ProductionDeviceTelemetry,
    ProductionTelemetrySnapshot,
    ProductionTelemetryState,
)
from vscs.application.provider_execution import (
    DurableExecutionJob,
    ProviderExecutionHandle,
    ProviderExecutionState,
)
from vscs.infrastructure.rendering import (
    ComfyUIClient,
    ComfyUIHealthReport,
    UrllibComfyUITransport,
)


class ComfyUITelemetryClient(Protocol):
    """Read-only ComfyUI operations needed by the monitoring dashboard."""

    def queue(self) -> dict[str, object]: ...

    def health(self) -> ComfyUIHealthReport: ...


class ComfyUIProductionTelemetryReader:
    """Observe ComfyUI without mutating queue, lease, provider or production authority."""

    def __init__(
        self,
        endpoint: str,
        *,
        client: ComfyUITelemetryClient | None = None,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.endpoint = endpoint.strip().rstrip("/")
        self.client = client or ComfyUIClient(
            UrllibComfyUITransport(self.endpoint, timeout_seconds=timeout_seconds),
            self.endpoint,
        )

    def observe_live(
        self,
        handle: ProviderExecutionHandle,
        *,
        task_id: str,
        resource_id: str,
        queue_entry_id: str,
    ) -> ProductionTelemetrySnapshot:
        now = datetime.now(UTC)
        elapsed = max(0.0, (now - handle.submitted_at).total_seconds())
        issues: list[str] = []
        queue_state = "unknown"
        queue_position: int | None = None
        pending_count = 0
        running_count = 0
        try:
            queue = self.client.queue()
            running_ids = _prompt_ids(queue.get("queue_running", []))
            pending_ids = _prompt_ids(queue.get("queue_pending", []))
            running_count = len(running_ids)
            pending_count = len(pending_ids)
            if handle.provider_job_id in running_ids:
                queue_state = "running"
            elif handle.provider_job_id in pending_ids:
                queue_state = "pending"
                queue_position = pending_ids.index(handle.provider_job_id) + 1
            elif handle.state in {
                ProviderExecutionState.COMPLETED,
                ProviderExecutionState.FAILED,
                ProviderExecutionState.CANCELLED,
            }:
                queue_state = "terminal"
            else:
                queue_state = "not-listed"
        except Exception as exc:
            issues.append(f"Queue telemetry unavailable: {exc}")

        healthy: bool | None = None
        devices: tuple[ProductionDeviceTelemetry, ...] = ()
        system_metrics: tuple[tuple[str, str], ...] = ()
        try:
            health = self.client.health()
            healthy = health.healthy
            devices = tuple(_device(item) for item in health.devices)
            system_metrics = tuple(
                sorted(
                    (str(key), _metric_text(value))
                    for key, value in health.system.items()
                    if _simple_metric(value)
                )
            )
        except Exception as exc:
            healthy = False
            issues.append(f"System telemetry unavailable: {exc}")

        progress = handle.progress
        eta = _estimated_remaining(elapsed, progress)
        state = _telemetry_state(handle.state)
        stage = _stage(state, queue_state)
        detail = (
            "Live HTTP telemetry active. Detailed current-node and sampler-step progress are "
            "not exposed by the current ComfyUI polling contract."
        )
        if issues:
            detail = detail + " " + " ".join(issues)
        return ProductionTelemetrySnapshot(
            task_id=task_id,
            state=state,
            live=True,
            execution_id=handle.execution_id,
            provider_id=handle.provider_id,
            provider_job_id=handle.provider_job_id,
            resource_id=resource_id,
            queue_entry_id=queue_entry_id,
            stage=stage,
            progress=progress,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=eta,
            queue_state=queue_state,
            queue_position=queue_position,
            queue_pending_count=pending_count,
            queue_running_count=running_count,
            provider_healthy=healthy,
            provider_endpoint=self.endpoint or None,
            devices=devices,
            system_metrics=system_metrics,
            message=detail,
            observed_at=now,
        )

    def observe_durable(self, job: DurableExecutionJob) -> ProductionTelemetrySnapshot:
        """Return a non-live restart-safe summary without claiming recovery authority."""
        end = job.updated_at
        start = job.submitted_at or job.created_at
        elapsed = max(0.0, (end - start).total_seconds())
        return ProductionTelemetrySnapshot(
            task_id=job.task_id,
            state=_telemetry_state(job.state),
            live=False,
            execution_id=job.execution_id,
            provider_id=job.provider_id,
            provider_job_id=job.provider_job_id,
            resource_id=job.resource_id,
            queue_entry_id=job.entry_id,
            stage="Durable execution summary",
            progress=job.progress,
            elapsed_seconds=elapsed,
            queue_state="durable-summary",
            provider_endpoint=self.endpoint or None,
            message=(
                "Durable execution summary only. Live provider monitoring and authority are not "
                "reconstructed after restart in Phase 20.15.2; recovery remains Phase 20.16."
            ),
            observed_at=datetime.now(UTC),
        )


def _prompt_ids(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        if isinstance(item, list) and len(item) >= 2:
            prompt_id = str(item[1]).strip()
            if prompt_id:
                values.append(prompt_id)
    return values


def _device(raw: dict[str, object]) -> ProductionDeviceTelemetry:
    name = str(raw.get("name") or raw.get("type") or "ComfyUI device")
    kind = str(raw.get("type") or "device")
    return ProductionDeviceTelemetry(
        name=name,
        kind=kind,
        total_memory_bytes=_optional_int(raw.get("vram_total")),
        free_memory_bytes=_optional_int(raw.get("vram_free")),
        framework_total_memory_bytes=_optional_int(raw.get("torch_vram_total")),
        framework_free_memory_bytes=_optional_int(raw.get("torch_vram_free")),
        utilization_percent=_optional_float(raw.get("utilization")),
        metrics=tuple(
            sorted(
                (str(key), _metric_text(value))
                for key, value in raw.items()
                if key
                not in {
                    "name",
                    "type",
                    "vram_total",
                    "vram_free",
                    "torch_vram_total",
                    "torch_vram_free",
                    "utilization",
                }
                and _simple_metric(value)
            )
        ),
    )


def _telemetry_state(state: ProviderExecutionState) -> ProductionTelemetryState:
    mapping = {
        ProviderExecutionState.QUEUED: ProductionTelemetryState.QUEUED,
        ProviderExecutionState.PREPARING: ProductionTelemetryState.PREPARING,
        ProviderExecutionState.RUNNING: ProductionTelemetryState.RUNNING,
        ProviderExecutionState.COMPLETED: ProductionTelemetryState.COMPLETED,
        ProviderExecutionState.FAILED: ProductionTelemetryState.FAILED,
        ProviderExecutionState.CANCELLED: ProductionTelemetryState.CANCELLED,
        ProviderExecutionState.RETRYING: ProductionTelemetryState.RETRYING,
    }
    return mapping.get(state, ProductionTelemetryState.UNKNOWN)


def _stage(state: ProductionTelemetryState, queue_state: str) -> str:
    if queue_state == "pending":
        return "Waiting in ComfyUI queue"
    if queue_state == "running":
        return "Generating video in ComfyUI"
    mapping = {
        ProductionTelemetryState.QUEUED: "Queued for provider execution",
        ProductionTelemetryState.PREPARING: "Preparing production workflow",
        ProductionTelemetryState.RUNNING: "Running production workflow",
        ProductionTelemetryState.COMPLETED: "Production completed",
        ProductionTelemetryState.FAILED: "Production failed",
        ProductionTelemetryState.CANCELLED: "Production cancelled",
        ProductionTelemetryState.RETRYING: "Retrying provider execution",
        ProductionTelemetryState.UNKNOWN: "Execution state unavailable",
    }
    return mapping[state]


def _estimated_remaining(elapsed: float, progress: float) -> float | None:
    if progress <= 0.0 or progress >= 1.0:
        return None
    # Phase 20.5's HTTP polling intentionally uses 0.1 and 0.5 as coarse state markers.
    # Do not present those markers as a precise ETA. Future detailed progress values will
    # automatically enable the estimate without changing this contract.
    if progress in {0.1, 0.5}:
        return None
    return max(0.0, elapsed * (1.0 - progress) / progress)


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return max(0, int(value))
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _simple_metric(value: object) -> bool:
    return isinstance(value, str | int | float | bool)


def _metric_text(value: object) -> str:
    return str(value)
