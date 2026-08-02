"""Tests for Phase 14.3 production executors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.acpp import (
    RenderCapability,
    RenderJob,
    RenderQualityMode,
    RetryPolicy,
    SeedPolicy,
)
from vscs.application.production_pipeline import (
    ExecutionRequest,
    ExecutorRegistry,
    ExecutorRegistryError,
    LeaseManager,
    MockProductionExecutor,
    WorkerIdentity,
)

NOW = datetime(2026, 8, 2, 8, 0, tzinfo=UTC)


def _job(*capabilities: RenderCapability) -> RenderJob:
    return RenderJob(
        job_id="JOB-001",
        clip_id="CLIP-001",
        width=1920,
        height=800,
        frames_per_second=24,
        frame_count=240,
        quality_mode=RenderQualityMode.PRODUCTION,
        seed_policy=SeedPolicy.DERIVED,
        fixed_seed=None,
        positive_prompt="A controlled bridge performance.",
        negative_prompt="No identity drift.",
        input_references=(),
        start_reference_id=None,
        end_reference_id=None,
        output_path="production/clip-001.mp4",
        dependencies=(),
        retry_policy=RetryPolicy(),
        required_capabilities=capabilities,
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
    )


def test_registry_selects_compatible_executor() -> None:
    registry = ExecutorRegistry()
    text = MockProductionExecutor(
        executor_id="text",
        capabilities=frozenset({RenderCapability.TEXT_TO_VIDEO}),
    )
    image = MockProductionExecutor(
        executor_id="image",
        capabilities=frozenset(
            {RenderCapability.TEXT_TO_VIDEO, RenderCapability.IMAGE_TO_VIDEO}
        ),
    )
    registry.register(text)
    registry.register(image)

    selected = registry.select(
        _job(RenderCapability.TEXT_TO_VIDEO, RenderCapability.IMAGE_TO_VIDEO)
    )

    assert selected.executor_id == "image"


def test_registry_rejects_duplicates_and_unsupported_jobs() -> None:
    registry = ExecutorRegistry()
    executor = MockProductionExecutor(
        capabilities=frozenset({RenderCapability.TEXT_TO_VIDEO})
    )
    registry.register(executor)

    with pytest.raises(ExecutorRegistryError):
        registry.register(executor)
    with pytest.raises(ExecutorRegistryError):
        registry.select(_job(RenderCapability.END_FRAME_CONDITIONING))


def test_lease_acquire_heartbeat_and_expiry() -> None:
    manager = LeaseManager()
    lease = manager.acquire(
        "JOB-001",
        "worker-a",
        duration_seconds=30,
        now=NOW,
    )

    assert lease.is_expired(NOW + timedelta(seconds=20)) is False
    renewed = manager.heartbeat(
        lease,
        duration_seconds=30,
        now=NOW + timedelta(seconds=20),
    )
    assert renewed.last_heartbeat_at == NOW + timedelta(seconds=20)
    assert renewed.expires_at == NOW + timedelta(seconds=50)

    with pytest.raises(ValueError):
        manager.heartbeat(
            lease,
            duration_seconds=30,
            now=NOW + timedelta(seconds=31),
        )


def test_mock_executor_returns_success_result() -> None:
    executor = MockProductionExecutor()
    worker = WorkerIdentity(
        worker_id="worker-a",
        executor_id=executor.executor_id,
        capabilities=executor.capabilities,
    )
    lease = LeaseManager().acquire(
        "JOB-001",
        worker.worker_id,
        duration_seconds=60,
        now=NOW,
    )

    result = executor.execute(
        ExecutionRequest(
            job=_job(RenderCapability.TEXT_TO_VIDEO),
            worker=worker,
            lease=lease,
            submitted_at=NOW,
        )
    )

    assert result.succeeded is True
    assert result.output_paths == ("mock/output.mp4",)
    assert result.worker_id == "worker-a"


def test_mock_executor_returns_provider_neutral_failure() -> None:
    executor = MockProductionExecutor(succeed=False)
    worker = WorkerIdentity(
        worker_id="worker-a",
        executor_id=executor.executor_id,
        capabilities=executor.capabilities,
    )
    lease = LeaseManager().acquire(
        "JOB-001",
        worker.worker_id,
        duration_seconds=60,
        now=NOW,
    )

    result = executor.execute(
        ExecutionRequest(
            job=_job(RenderCapability.TEXT_TO_VIDEO),
            worker=worker,
            lease=lease,
            submitted_at=NOW,
        )
    )

    assert result.succeeded is False
    assert result.error_code is not None
    assert result.error_message == "Mock executor failure"
