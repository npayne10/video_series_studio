"""Focused tests for Phase 20.7 durable execution jobs and attempts."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_tasks import ProductionCapability, ProductionTaskType
from vscs.application.provider_execution import (
    DurableExecutionJobError,
    DurableExecutionJobRepositoryError,
    DurableExecutionJobService,
    ProviderExecutionContext,
    ProviderExecutionHandle,
    ProviderExecutionState,
)
from vscs.infrastructure.provider_execution import JsonDurableExecutionJobRepository

NOW = datetime(2026, 8, 18, 18, 30, tzinfo=UTC)


def _context(*, execution_id: str = "PEX-PQ-001-PQE-001-A001") -> ProviderExecutionContext:
    return ProviderExecutionContext(
        execution_id=execution_id,
        production_id="PROD-001",
        task_id="PT-001",
        queue_id="PQ-001",
        entry_id="PQE-001",
        resource_id="GPU-01",
        worker_id="WORKER-01",
        lease_id="PLEASE-PQ-001-PQE-001-WORKER-01",
        attempt_number=1,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        required_capabilities=(ProductionCapability.VIDEO_GENERATION,),
        authority_fingerprint="authority-fingerprint",
    )


def _handle(
    state: ProviderExecutionState,
    *,
    progress: float = 0.0,
    provider_job_id: str = "prompt-001",
    failure_reason: str | None = None,
) -> ProviderExecutionHandle:
    return ProviderExecutionHandle(
        execution_id="PEX-PQ-001-PQE-001-A001",
        provider_id="LOCAL-COMFYUI-01",
        provider_job_id=provider_job_id,
        state=state,
        submitted_at=NOW + timedelta(seconds=1),
        progress=progress,
        failure_reason=failure_reason,
    )


def test_prepare_persists_restart_safe_execution_authority(tmp_path) -> None:
    root = tmp_path / "executions"
    service = DurableExecutionJobService(JsonDurableExecutionJobRepository(root))

    prepared = service.prepare(
        _context(),
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )

    restarted = DurableExecutionJobService(JsonDurableExecutionJobRepository(root))
    restored = restarted.require(prepared.execution_id)
    assert restored == prepared
    assert restored.state is ProviderExecutionState.PREPARING
    assert restored.provider_job_id is None
    assert restored.task_id == "PT-001"
    assert restored.lease_id == "PLEASE-PQ-001-PQE-001-WORKER-01"
    assert restored.attempt_number == 1


def test_provider_observations_persist_job_identity_and_history(tmp_path) -> None:
    service = DurableExecutionJobService(JsonDurableExecutionJobRepository(tmp_path / "executions"))
    prepared = service.prepare(
        _context(),
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )
    queued = service.observe(
        prepared.execution_id,
        _handle(ProviderExecutionState.QUEUED),
        now=NOW + timedelta(seconds=1),
    )
    running = service.observe(
        prepared.execution_id,
        _handle(ProviderExecutionState.RUNNING, progress=0.5),
        now=NOW + timedelta(seconds=2),
    )
    completed = service.observe(
        prepared.execution_id,
        _handle(ProviderExecutionState.COMPLETED, progress=1.0),
        now=NOW + timedelta(seconds=3),
    )

    assert queued.provider_job_id == "prompt-001"
    assert running.progress == 0.5
    assert completed.terminal
    assert [event.state for event in completed.events] == [
        ProviderExecutionState.PREPARING,
        ProviderExecutionState.QUEUED,
        ProviderExecutionState.RUNNING,
        ProviderExecutionState.COMPLETED,
    ]
    assert service.list_active() == ()


def test_submission_failure_is_durable_without_provider_job_id(tmp_path) -> None:
    service = DurableExecutionJobService(JsonDurableExecutionJobRepository(tmp_path / "executions"))
    prepared = service.prepare(
        _context(),
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )

    failed = service.submission_failed(
        prepared.execution_id,
        "provider submission failed",
        now=NOW + timedelta(seconds=1),
    )

    assert failed.state is ProviderExecutionState.FAILED
    assert failed.provider_job_id is None
    assert failed.failure_reason == "provider submission failed"
    assert failed.terminal


def test_provider_job_identity_cannot_change_mid_execution(tmp_path) -> None:
    service = DurableExecutionJobService(JsonDurableExecutionJobRepository(tmp_path / "executions"))
    prepared = service.prepare(
        _context(),
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )
    service.observe(
        prepared.execution_id,
        _handle(ProviderExecutionState.QUEUED),
        now=NOW + timedelta(seconds=1),
    )

    with pytest.raises(DurableExecutionJobError, match="identity changed"):
        service.observe(
            prepared.execution_id,
            _handle(ProviderExecutionState.RUNNING, provider_job_id="prompt-OTHER"),
            now=NOW + timedelta(seconds=2),
        )


def test_terminal_execution_cannot_return_to_running(tmp_path) -> None:
    service = DurableExecutionJobService(JsonDurableExecutionJobRepository(tmp_path / "executions"))
    prepared = service.prepare(
        _context(),
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )
    service.observe(
        prepared.execution_id,
        _handle(ProviderExecutionState.QUEUED),
        now=NOW + timedelta(seconds=1),
    )
    service.observe(
        prepared.execution_id,
        _handle(ProviderExecutionState.COMPLETED, progress=1.0),
        now=NOW + timedelta(seconds=2),
    )

    with pytest.raises(DurableExecutionJobError, match="terminal"):
        service.observe(
            prepared.execution_id,
            _handle(ProviderExecutionState.RUNNING, progress=0.5),
            now=NOW + timedelta(seconds=3),
        )


def test_repository_rejects_unsafe_execution_identity(tmp_path) -> None:
    repository = JsonDurableExecutionJobRepository(tmp_path / "executions")
    service = DurableExecutionJobService(repository)
    prepared = service.prepare(
        _context(),
        "LOCAL-COMFYUI-01",
        render_request_id="REQ-001",
        workflow_id="video_production_engine_v7_1_4",
        now=NOW,
    )
    unsafe = replace(prepared, execution_id="../PEX-001")

    with pytest.raises(DurableExecutionJobRepositoryError, match="filesystem-safe"):
        repository.save(unsafe)
