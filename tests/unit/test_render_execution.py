"""Tests for Phase 15.4 production render execution."""

from __future__ import annotations

from datetime import UTC, datetime

from vscs.application.acpp import (
    RenderCapability,
    RenderJob,
    RenderQualityMode,
    RetryPolicy,
    SeedPolicy,
)
from vscs.application.production_pipeline import (
    ExecutorRegistry,
    MockProductionExecutor,
    ProductionNode,
    ProductionPipeline,
    ProductionStage,
    ProductionState,
    QueuePriority,
    QueueState,
    RenderQueue,
    RenderQueueEntry,
    WorkerIdentity,
)
from vscs.infrastructure.production import (
    RenderExecutionEventType,
    RenderExecutionRequest,
    RenderExecutionService,
)

NOW = datetime.now(UTC)


def _job(maximum_attempts: int = 3) -> RenderJob:
    return RenderJob(
        job_id="JOB-001",
        clip_id="CLIP-001",
        width=1920,
        height=800,
        frames_per_second=24,
        frame_count=240,
        quality_mode=RenderQualityMode.PRODUCTION,
        seed_policy=SeedPolicy.FIXED,
        fixed_seed=42,
        positive_prompt="James stands on the bridge.",
        negative_prompt="No drift.",
        input_references=(),
        start_reference_id=None,
        end_reference_id=None,
        output_path="production/clip-001.mp4",
        dependencies=(),
        retry_policy=RetryPolicy(maximum_attempts=maximum_attempts, backoff_seconds=5),
        required_capabilities=(RenderCapability.TEXT_TO_VIDEO,),
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
    )


def _queue(maximum_attempts: int = 3) -> RenderQueue:
    return RenderQueue(
        "QUEUE-001",
        "PIPE-001",
        (
            RenderQueueEntry(
                "Q-001",
                "JOB-001",
                "CLIP-001",
                state=QueueState.READY,
                priority=QueuePriority.HIGH,
                maximum_attempts=maximum_attempts,
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )


def _pipeline() -> ProductionPipeline:
    return ProductionPipeline(
        "PIPE-001",
        "PROD-001",
        "EP-001",
        (
            ProductionNode(
                "NODE-RENDER-001",
                ProductionStage.RENDERING,
                state=ProductionState.READY,
                clip_id="CLIP-001",
            ),
        ),
    )


def _worker() -> WorkerIdentity:
    return WorkerIdentity(
        "worker-a",
        "mock",
        frozenset({RenderCapability.TEXT_TO_VIDEO}),
    )


def _service(*, succeed: bool = True) -> RenderExecutionService:
    registry = ExecutorRegistry()
    registry.register(MockProductionExecutor(succeed=succeed))
    return RenderExecutionService(registry)


def test_successful_execution_completes_queue_and_pipeline() -> None:
    outcome = _service().execute(
        RenderExecutionRequest(_queue(), _pipeline(), (_job(),), _worker()),
        now=NOW,
    )

    assert outcome.entry.state is QueueState.COMPLETED
    assert outcome.execution_result is not None
    assert outcome.execution_result.succeeded is True
    assert outcome.pipeline.nodes[0].state is ProductionState.COMPLETED
    assert tuple(item.event_type for item in outcome.events) == (
        RenderExecutionEventType.CLAIMED,
        RenderExecutionEventType.STARTED,
        RenderExecutionEventType.COMPLETED,
    )


def test_failed_execution_schedules_retry() -> None:
    outcome = _service(succeed=False).execute(
        RenderExecutionRequest(_queue(), _pipeline(), (_job(),), _worker()),
        now=NOW,
    )

    assert outcome.entry.state is QueueState.RETRYING
    assert outcome.entry.available_at is not None
    assert outcome.pipeline.nodes[0].state is ProductionState.PENDING
    assert outcome.events[-1].event_type is RenderExecutionEventType.RETRY_SCHEDULED


def test_failed_execution_becomes_terminal_when_attempts_exhausted() -> None:
    outcome = _service(succeed=False).execute(
        RenderExecutionRequest(
            _queue(maximum_attempts=1),
            _pipeline(),
            (_job(maximum_attempts=1),),
            _worker(),
        ),
        now=NOW,
    )

    assert outcome.entry.state is QueueState.FAILED
    assert outcome.pipeline.nodes[0].state is ProductionState.FAILED
    assert outcome.events[-1].event_type is RenderExecutionEventType.FAILED


def test_explicit_non_ready_entry_is_rejected() -> None:
    waiting = RenderQueue(
        "QUEUE-001",
        "PIPE-001",
        (
            RenderQueueEntry(
                "Q-001",
                "JOB-001",
                "CLIP-001",
                state=QueueState.WAITING,
                dependencies=("Q-MISSING",),
                created_at=NOW,
                updated_at=NOW,
            ),
        ),
    )

    try:
        _service().execute(
            RenderExecutionRequest(
                waiting,
                _pipeline(),
                (_job(),),
                _worker(),
                entry_id="Q-001",
            ),
            now=NOW,
        )
    except RuntimeError as exc:
        assert "not ready" in str(exc)
    else:
        raise AssertionError("Expected non-ready entry rejection")


def test_missing_render_job_is_rejected_before_claim() -> None:
    try:
        _service().execute(
            RenderExecutionRequest(_queue(), _pipeline(), (), _worker()),
            now=NOW,
        )
    except RuntimeError as exc:
        assert "Render job not found" in str(exc)
    else:
        raise AssertionError("Expected missing render job rejection")
