"""Concrete ComfyUI production executor and HTTP client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from collections.abc import Callable
from typing import Any, Protocol
from uuid import uuid4

from vscs.application.acpp import RenderCapability, RenderJob
from vscs.application.production_pipeline import (
    ExecutionRequest,
    ExecutionResult,
    ExecutorErrorCode,
)


class ComfyUIClientError(RuntimeError):
    """Raised when ComfyUI rejects or cannot complete a request."""


class ComfyUITimeoutError(ComfyUIClientError):
    """Raised when ComfyUI does not complete before the execution deadline."""


class ComfyUIWorkflowCompiler(Protocol):
    """Compile one renderer-neutral render job into a ComfyUI API workflow."""

    def compile(self, job: RenderJob) -> dict[str, Any]:
        """Return one API-format ComfyUI prompt graph."""
        ...


@dataclass(frozen=True, slots=True)
class ComfyUIExecutorConfig:
    """Configuration for one concrete ComfyUI production executor."""

    base_url: str = "http://127.0.0.1:8188"
    request_timeout_seconds: float = 15.0
    execution_timeout_seconds: float = 3600.0
    poll_interval_seconds: float = 1.0
    require_outputs: bool = True

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("base_url must not be empty")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be positive")
        if self.execution_timeout_seconds <= 0:
            raise ValueError("execution_timeout_seconds must be positive")
        if self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")


class ComfyUIClient:
    """Minimal synchronous ComfyUI HTTP transport for production execution."""

    def __init__(
        self,
        config: ComfyUIExecutorConfig | None = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config or ComfyUIExecutorConfig()
        self.base_url = self.config.base_url.rstrip("/")
        self.client_id = f"vscs-production-{uuid4()}"
        self._sleep = sleeper
        self._monotonic = monotonic

    def healthcheck(self) -> None:
        """Verify that the ComfyUI server is reachable."""
        self._request("GET", "/system_stats")

    def submit(self, workflow: dict[str, Any]) -> str:
        """Submit one API-format prompt and return its prompt identity."""
        response = self._request(
            "POST",
            "/prompt",
            {"prompt": workflow, "client_id": self.client_id},
        )
        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIClientError(f"ComfyUI did not return a prompt_id: {response}")
        return prompt_id

    def wait(self, prompt_id: str) -> dict[str, Any]:
        """Wait for one submitted prompt to finish and return its history record."""
        started = self._monotonic()
        while self._monotonic() - started <= self.config.execution_timeout_seconds:
            history = self._request("GET", f"/history/{prompt_id}")
            record = history.get(prompt_id)
            if isinstance(record, dict):
                status = record.get("status")
                if isinstance(status, dict):
                    status_value = status.get("status_str")
                    if status_value in {"error", "failed"}:
                        details = status.get("messages", status)
                        raise ComfyUIClientError(
                            "ComfyUI workflow failed: "
                            + json.dumps(details, ensure_ascii=False)
                        )
                    if status.get("completed") is True:
                        return record
                if record.get("outputs") is not None:
                    return record
            self._sleep(self.config.poll_interval_seconds)
        raise ComfyUITimeoutError(
            "ComfyUI execution timed out after "
            f"{self.config.execution_timeout_seconds:.0f} seconds"
        )

    @staticmethod
    def output_paths(history: dict[str, Any]) -> tuple[str, ...]:
        """Extract stable output paths from a ComfyUI history record."""
        outputs = history.get("outputs")
        if not isinstance(outputs, dict):
            return ()
        paths: list[str] = []
        for node in outputs.values():
            if not isinstance(node, dict):
                continue
            for key in ("videos", "gifs", "images", "audio"):
                values = node.get(key)
                if not isinstance(values, list):
                    continue
                for item in values:
                    if not isinstance(item, dict):
                        continue
                    filename = item.get("filename")
                    if not isinstance(filename, str) or not filename:
                        continue
                    subfolder = item.get("subfolder")
                    path = (
                        f"{subfolder.strip('/\\')}/{filename}"
                        if isinstance(subfolder, str) and subfolder.strip("/\\")
                        else filename
                    )
                    if path not in paths:
                        paths.append(path)
        return tuple(paths)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.request_timeout_seconds,
            ) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyUIClientError(
                f"ComfyUI rejected {method} {path} with HTTP {exc.code}: "
                f"{detail[:8000]}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ComfyUIClientError(
                f"Unable to communicate with ComfyUI at {self.base_url}: {exc}"
            ) from exc
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComfyUIClientError(f"ComfyUI returned invalid JSON: {raw[:1000]}") from exc
        if not isinstance(value, dict):
            raise ComfyUIClientError("ComfyUI returned an unexpected response")
        return value


@dataclass(slots=True)
class ComfyUIProductionExecutor:
    """Concrete Phase 15.1 executor implementing the production contract."""

    workflow_compiler: ComfyUIWorkflowCompiler
    client: ComfyUIClient = field(default_factory=ComfyUIClient)
    executor_id: str = "comfyui"
    capabilities: frozenset[RenderCapability] = field(
        default_factory=lambda: frozenset(RenderCapability)
    )

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Compile, submit, monitor, and collect one ComfyUI render job."""
        started = datetime.now(UTC)
        error = self._validate_request(request, started)
        if error is not None:
            return error
        try:
            workflow = self.workflow_compiler.compile(request.job)
            if not workflow:
                raise ValueError("Workflow compiler returned an empty graph")
            self.client.healthcheck()
            prompt_id = self.client.submit(workflow)
            history = self.client.wait(prompt_id)
            outputs = self.client.output_paths(history)
            if self.client.config.require_outputs and not outputs:
                return self._failure(
                    request,
                    started,
                    ExecutorErrorCode.INVALID_OUTPUT,
                    "ComfyUI completed without reporting an output",
                    (("prompt_id", prompt_id),),
                )
            return ExecutionResult(
                job_id=request.job.job_id,
                worker_id=request.worker.worker_id,
                succeeded=True,
                started_at=started,
                completed_at=datetime.now(UTC),
                output_paths=outputs or (request.job.output_path,),
                metadata=(("prompt_id", prompt_id), ("provider", "comfyui")),
            )
        except ComfyUITimeoutError as exc:
            return self._failure(
                request,
                started,
                ExecutorErrorCode.TIMEOUT,
                str(exc),
            )
        except (ComfyUIClientError, OSError, ValueError) as exc:
            return self._failure(
                request,
                started,
                ExecutorErrorCode.PROVIDER_ERROR,
                str(exc),
            )

    def _validate_request(
        self,
        request: ExecutionRequest,
        started: datetime,
    ) -> ExecutionResult | None:
        if request.worker.executor_id != self.executor_id:
            return self._failure(
                request,
                started,
                ExecutorErrorCode.UNSUPPORTED_JOB,
                "Worker executor identity does not match ComfyUI executor",
            )
        required = frozenset(request.job.required_capabilities)
        if not required.issubset(self.capabilities):
            return self._failure(
                request,
                started,
                ExecutorErrorCode.UNSUPPORTED_JOB,
                "ComfyUI executor does not support all required capabilities",
            )
        if not required.issubset(request.worker.capabilities):
            return self._failure(
                request,
                started,
                ExecutorErrorCode.UNSUPPORTED_JOB,
                "Worker does not advertise all required capabilities",
            )
        if request.lease.worker_id != request.worker.worker_id:
            return self._failure(
                request,
                started,
                ExecutorErrorCode.CANCELLED,
                "Execution lease belongs to a different worker",
            )
        if request.lease.job_id != request.job.job_id:
            return self._failure(
                request,
                started,
                ExecutorErrorCode.CANCELLED,
                "Execution lease belongs to a different render job",
            )
        if request.lease.is_expired(started):
            return self._failure(
                request,
                started,
                ExecutorErrorCode.CANCELLED,
                "Execution lease expired before ComfyUI submission",
            )
        return None

    @staticmethod
    def _failure(
        request: ExecutionRequest,
        started: datetime,
        code: ExecutorErrorCode,
        message: str,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> ExecutionResult:
        return ExecutionResult(
            job_id=request.job.job_id,
            worker_id=request.worker.worker_id,
            succeeded=False,
            started_at=started,
            completed_at=datetime.now(UTC),
            error_code=code,
            error_message=message,
            metadata=metadata,
        )
