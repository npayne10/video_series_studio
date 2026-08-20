from __future__ import annotations

from datetime import UTC, datetime, timedelta

from vscs.application.production_execution import ProductionTelemetryState
from vscs.application.provider_execution import ProviderExecutionHandle, ProviderExecutionState
from vscs.infrastructure.production_execution.live_telemetry import (
    ComfyUIProductionTelemetryReader,
)
from vscs.infrastructure.rendering import ComfyUIHealthReport


class FakeTelemetryClient:
    def queue(self) -> dict[str, object]:
        return {
            "queue_running": [[1, "prompt-live-001", {}, {}]],
            "queue_pending": [
                [2, "prompt-pending-001", {}, {}],
                [3, "prompt-pending-002", {}, {}],
            ],
        }

    def health(self) -> ComfyUIHealthReport:
        return ComfyUIHealthReport(
            healthy=True,
            endpoint="http://127.0.0.1:8188",
            observed_at=datetime.now(UTC),
            system={"python_version": "3.12", "ram_total": 32_000_000_000},
            devices=(
                {
                    "name": "NVIDIA RTX 4060",
                    "type": "cuda",
                    "vram_total": 8_000_000_000,
                    "vram_free": 2_000_000_000,
                    "torch_vram_total": 7_500_000_000,
                    "torch_vram_free": 1_500_000_000,
                },
            ),
        )


def test_live_telemetry_reports_queue_health_device_and_coarse_progress() -> None:
    reader = ComfyUIProductionTelemetryReader(
        "http://127.0.0.1:8188",
        client=FakeTelemetryClient(),
    )
    handle = ProviderExecutionHandle(
        execution_id="PEX-20-15-2-001",
        provider_id="LOCAL-COMFYUI-GPU-01",
        provider_job_id="prompt-live-001",
        state=ProviderExecutionState.RUNNING,
        submitted_at=datetime.now(UTC) - timedelta(seconds=12),
        progress=0.5,
    )

    snapshot = reader.observe_live(
        handle,
        task_id="PT-VIDEO-001",
        resource_id="GPU-01",
        queue_entry_id="PQE-001",
    )

    assert snapshot.live is True
    assert snapshot.state is ProductionTelemetryState.RUNNING
    assert snapshot.queue_state == "running"
    assert snapshot.queue_running_count == 1
    assert snapshot.queue_pending_count == 2
    assert snapshot.provider_healthy is True
    assert snapshot.progress == 0.5
    assert snapshot.estimated_remaining_seconds is None
    assert snapshot.elapsed_seconds is not None and snapshot.elapsed_seconds >= 12
    assert snapshot.current_node is None
    assert snapshot.step_current is None
    assert snapshot.devices[0].name == "NVIDIA RTX 4060"
    assert snapshot.devices[0].used_memory_bytes == 6_000_000_000
    assert "Detailed current-node and sampler-step progress" in snapshot.message


def test_pending_prompt_reports_queue_position() -> None:
    reader = ComfyUIProductionTelemetryReader(
        "http://127.0.0.1:8188",
        client=FakeTelemetryClient(),
    )
    handle = ProviderExecutionHandle(
        execution_id="PEX-20-15-2-002",
        provider_id="LOCAL-COMFYUI-GPU-01",
        provider_job_id="prompt-pending-002",
        state=ProviderExecutionState.QUEUED,
        submitted_at=datetime.now(UTC),
        progress=0.0,
    )

    snapshot = reader.observe_live(
        handle,
        task_id="PT-VIDEO-002",
        resource_id="GPU-01",
        queue_entry_id="PQE-002",
    )

    assert snapshot.queue_state == "pending"
    assert snapshot.queue_position == 2
    assert snapshot.stage == "Waiting in ComfyUI queue"
