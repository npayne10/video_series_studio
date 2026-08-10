"""Tests for Phase 15.1 ComfyUI production executor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from vscs.application.acpp import (
    RenderCapability,
    RenderJob,
    RenderQualityMode,
    RetryPolicy,
    SeedPolicy,
)
from vscs.application.production_pipeline import (
    ExecutionLease,
    ExecutionRequest,
    ExecutorErrorCode,
    WorkerIdentity,
)
from vscs.infrastructure.production import (
    ComfyUIClient,
    ComfyUIClientError,
    ComfyUIExecutorConfig,
    ComfyUIProductionExecutor,
    ComfyUITimeoutError,
)

NOW = datetime.now(UTC)


class StubCompiler:
    def compile(self, job: RenderJob) -> dict[str, Any]:
        return {"1": {"class_type": "TestNode", "inputs": {"prompt": job.positive_prompt}}}


class StubClient(ComfyUIClient):
    def __init__(
        self,
        *,
        history: dict[str, Any] | None = None,
        error: Exception | None = None,
        require_outputs: bool = True,
    ) -> None:
        super().__init__(
            ComfyUIExecutorConfig(require_outputs=require_outputs),
            sleeper=lambda _seconds: None,
        )
        self.history = history or {}
        self.error = error
        self.submitted: dict[str, Any] | None = None

    def healthcheck(self) -> None:
        if self.error is not None:
            raise self.error

    def submit(self, workflow: dict[str, Any]) -> str:
        self.submitted = workflow
        return "prompt-001"

    def wait(self, prompt_id: str) -> dict[str, Any]:
        assert prompt_id == "prompt-001"
        if self.error is not None:
            raise self.error
        return self.history


def _job(
    capabilities: tuple[RenderCapability, ...] = (RenderCapability.TEXT_TO_VIDEO,),
) -> RenderJob:
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
        retry_policy=RetryPolicy(),
        required_capabilities=capabilities,
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
    )


def _request(
    *,
    job: RenderJob | None = None,
    worker_executor_id: str = "comfyui",
    lease_job_id: str = "JOB-001",
    expires_at: datetime | None = None,
) -> ExecutionRequest:
    selected_job = job or _job()
    worker = WorkerIdentity(
        worker_id="worker-a",
        executor_id=worker_executor_id,
        capabilities=frozenset(RenderCapability),
    )
    lease = ExecutionLease(
        lease_id="LEASE-001",
        worker_id=worker.worker_id,
        job_id=lease_job_id,
        acquired_at=NOW,
        expires_at=expires_at or NOW + timedelta(minutes=10),
        last_heartbeat_at=NOW,
    )
    return ExecutionRequest(selected_job, worker, lease, NOW)


def test_executor_submits_workflow_and_returns_outputs() -> None:
    client = StubClient(
        history={
            "outputs": {"9": {"videos": [{"filename": "clip-001.mp4", "subfolder": "production"}]}}
        }
    )
    executor = ComfyUIProductionExecutor(StubCompiler(), client)

    result = executor.execute(_request())

    assert result.succeeded is True
    assert result.output_paths == ("production/clip-001.mp4",)
    assert client.submitted is not None
    assert ("prompt_id", "prompt-001") in result.metadata


def test_executor_maps_timeout_to_provider_neutral_result() -> None:
    executor = ComfyUIProductionExecutor(
        StubCompiler(),
        StubClient(error=ComfyUITimeoutError("render timeout")),
    )

    result = executor.execute(_request())

    assert result.succeeded is False
    assert result.error_code is ExecutorErrorCode.TIMEOUT
    assert result.error_message == "render timeout"


def test_executor_maps_client_failure_to_provider_error() -> None:
    executor = ComfyUIProductionExecutor(
        StubCompiler(),
        StubClient(error=ComfyUIClientError("server unavailable")),
    )

    result = executor.execute(_request())

    assert result.succeeded is False
    assert result.error_code is ExecutorErrorCode.PROVIDER_ERROR


def test_executor_rejects_missing_output() -> None:
    executor = ComfyUIProductionExecutor(StubCompiler(), StubClient(history={"outputs": {}}))

    result = executor.execute(_request())

    assert result.succeeded is False
    assert result.error_code is ExecutorErrorCode.INVALID_OUTPUT


def test_executor_rejects_unsupported_worker_identity() -> None:
    executor = ComfyUIProductionExecutor(StubCompiler(), StubClient())

    result = executor.execute(_request(worker_executor_id="other"))

    assert result.succeeded is False
    assert result.error_code is ExecutorErrorCode.UNSUPPORTED_JOB


def test_executor_rejects_expired_or_wrong_job_lease() -> None:
    executor = ComfyUIProductionExecutor(StubCompiler(), StubClient())

    wrong_job = executor.execute(_request(lease_job_id="JOB-OTHER"))
    expired = executor.execute(_request(expires_at=NOW - timedelta(seconds=1)))

    assert wrong_job.error_code is ExecutorErrorCode.CANCELLED
    assert expired.error_code is ExecutorErrorCode.CANCELLED


def test_output_extraction_deduplicates_supported_media() -> None:
    history = {
        "outputs": {
            "1": {
                "images": [
                    {"filename": "frame.png", "subfolder": "preview"},
                    {"filename": "frame.png", "subfolder": "preview"},
                ],
                "audio": [{"filename": "clip.wav", "subfolder": "audio"}],
            }
        }
    }

    assert ComfyUIClient.output_paths(history) == (
        "preview/frame.png",
        "audio/clip.wav",
    )
