"""Live ComfyUI HTTP client and renderer adapter for Phase 20.5."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from vscs.application.rendering import (
    CompiledRenderRequest,
    QualityLevel,
    RenderAdapter,
    RendererKind,
    RenderJob,
    RenderJobStatus,
    RenderOutput,
    RenderOutputKind,
    RenderRequest,
    RequestValidation,
    WorkflowCapabilities,
)

from .comfyui import ComfyUIAdapter, ComfyUIAdapterError


class ComfyUILiveAdapterError(ComfyUIAdapterError):
    """Raised when live ComfyUI communication or response handling fails."""


class ComfyUITransport(Protocol):
    """Minimal JSON transport used by the live ComfyUI client."""

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        """Perform one JSON request against ComfyUI."""
        ...


@dataclass(slots=True)
class UrllibComfyUITransport:
    """Standard-library HTTP transport for local or remote ComfyUI servers."""

    endpoint: str
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        normalized = self.endpoint.strip().rstrip("/")
        if not normalized:
            raise ValueError("ComfyUI endpoint cannot be blank")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.endpoint = normalized

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        relative = path if path.startswith("/") else f"/{path}"
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.endpoint}{relative}",
            data=body,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ComfyUILiveAdapterError(
                f"ComfyUI HTTP {exc.code} for {relative}: {detail or exc.reason}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ComfyUILiveAdapterError(
                f"Unable to contact ComfyUI at {self.endpoint}: {exc}"
            ) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ComfyUILiveAdapterError(
                f"ComfyUI returned invalid JSON for {relative}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True)
class ComfyUIHealthReport:
    """One live health observation from a ComfyUI server."""

    healthy: bool
    endpoint: str
    observed_at: datetime
    system: dict[str, object]
    devices: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class _SubmittedRenderContext:
    """Transient render metadata needed to classify provider outputs."""

    request_id: str
    workflow_id: str
    quality_level: QualityLevel


@dataclass(slots=True)
class ComfyUIClient:
    """Typed client for the ComfyUI HTTP endpoints used by VSCS."""

    transport: ComfyUITransport
    endpoint: str

    def health(self) -> ComfyUIHealthReport:
        raw = _mapping(self.transport.request("GET", "/system_stats"), "system_stats")
        system = _mapping(raw.get("system", {}), "system")
        devices_raw = raw.get("devices", [])
        if not isinstance(devices_raw, list):
            raise ComfyUILiveAdapterError("ComfyUI system_stats devices must be an array")
        devices = tuple(_mapping(item, "device") for item in devices_raw)
        return ComfyUIHealthReport(
            healthy=True,
            endpoint=self.endpoint,
            observed_at=datetime.now(UTC),
            system=dict(system),
            devices=tuple(dict(item) for item in devices),
        )

    def submit(self, payload: dict[str, object]) -> str:
        raw = _mapping(self.transport.request("POST", "/prompt", payload), "prompt response")
        prompt_id = str(raw.get("prompt_id", "")).strip()
        if not prompt_id:
            error = str(raw.get("error", "")).strip()
            raise ComfyUILiveAdapterError(
                f"ComfyUI did not return prompt_id{f': {error}' if error else ''}"
            )
        return prompt_id

    def queue(self) -> dict[str, object]:
        return dict(_mapping(self.transport.request("GET", "/queue"), "queue response"))

    def history(self, prompt_id: str) -> dict[str, object] | None:
        normalized = prompt_id.strip()
        if not normalized:
            raise ValueError("prompt_id cannot be blank")
        raw = _mapping(
            self.transport.request("GET", f"/history/{normalized}"),
            "history response",
        )
        item = raw.get(normalized)
        if item is None:
            return None
        return dict(_mapping(item, "history item"))

    def delete_queued(self, prompt_id: str) -> None:
        normalized = prompt_id.strip()
        if not normalized:
            raise ValueError("prompt_id cannot be blank")
        self.transport.request("POST", "/queue", {"delete": [normalized]})


@dataclass(slots=True)
class LiveComfyUIAdapter(RenderAdapter):
    """Execute compiled workflows against a live ComfyUI server."""

    foundation: ComfyUIAdapter
    client: ComfyUIClient
    renderer: RendererKind = RendererKind.COMFYUI
    _submitted: dict[str, _SubmittedRenderContext] = field(default_factory=dict)

    def capabilities(self, workflow_id: str) -> WorkflowCapabilities:
        return self.foundation.capabilities(workflow_id)

    def validate_request(self, request: RenderRequest) -> RequestValidation:
        return self.foundation.validate_request(request)

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        return self.foundation.compile_request(request)

    def health(self) -> ComfyUIHealthReport:
        """Probe the configured ComfyUI instance without mutating provider state."""
        return self.client.health()

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        """Submit one compiled workflow and capture the ComfyUI prompt identity."""
        if request.renderer is not self.renderer:
            raise ComfyUILiveAdapterError("compiled request does not target ComfyUI")
        prompt_id = self.client.submit(request.payload)
        quality = _quality_level(request.payload)
        self._submitted[prompt_id] = _SubmittedRenderContext(
            request_id=request.request_id,
            workflow_id=request.workflow_id,
            quality_level=quality,
        )
        return RenderJob(
            job_id=f"COMFY-{uuid4().hex}",
            request_id=request.request_id,
            status=RenderJobStatus.QUEUED,
            submitted_at=datetime.now(UTC),
            renderer_job_id=prompt_id,
        )

    def monitor(self, job: RenderJob) -> RenderJob:
        """Refresh one ComfyUI prompt from history first, then active queue state."""
        prompt_id = self._prompt_id(job)
        history = self.client.history(prompt_id)
        if history is not None:
            return self._from_history(job, history)

        queue = self.client.queue()
        if _queue_contains(queue.get("queue_running", []), prompt_id):
            if job.status is RenderJobStatus.RUNNING:
                return replace(job, progress=max(job.progress, 0.1))
            if job.status is RenderJobStatus.QUEUED:
                return job.transition(
                    RenderJobStatus.PREPARING,
                    started_at=job.started_at or datetime.now(UTC),
                    progress=max(job.progress, 0.1),
                ).transition(RenderJobStatus.RUNNING, progress=max(job.progress, 0.1))
            if job.status is RenderJobStatus.PREPARING:
                return job.transition(RenderJobStatus.RUNNING, progress=max(job.progress, 0.1))
            return job
        if _queue_contains(queue.get("queue_pending", []), prompt_id):
            return job
        return job

    def cancel(self, job: RenderJob) -> RenderJob:
        """Delete a queued prompt; running prompts are not globally interrupted by VSCS."""
        if job.status is RenderJobStatus.CANCELLED:
            return job
        if job.status in {RenderJobStatus.COMPLETED, RenderJobStatus.FAILED}:
            raise ComfyUILiveAdapterError("terminal ComfyUI jobs cannot be cancelled")
        prompt_id = self._prompt_id(job)
        queue = self.client.queue()
        if _queue_contains(queue.get("queue_running", []), prompt_id):
            raise ComfyUILiveAdapterError(
                "ComfyUI running-job cancellation would require the global /interrupt endpoint; "
                "VSCS will not interrupt unrelated provider work"
            )
        if not _queue_contains(queue.get("queue_pending", []), prompt_id):
            history = self.client.history(prompt_id)
            if history is not None:
                refreshed = self._from_history(job, history)
                if refreshed.status in {RenderJobStatus.COMPLETED, RenderJobStatus.FAILED}:
                    raise ComfyUILiveAdapterError("terminal ComfyUI jobs cannot be cancelled")
            raise ComfyUILiveAdapterError("ComfyUI prompt is not queued for cancellation")
        self.client.delete_queued(prompt_id)
        return job.transition(
            RenderJobStatus.CANCELLED,
            finished_at=datetime.now(UTC),
        )

    def fetch_outputs(self, job: RenderJob) -> tuple[RenderOutput, ...]:
        """Discover completed ComfyUI files without creating Generated Media authority."""
        prompt_id = self._prompt_id(job)
        history = self.client.history(prompt_id)
        if history is None:
            return ()
        status = _history_status(history)
        if status is not RenderJobStatus.COMPLETED:
            return ()
        context = self._submitted.get(prompt_id)
        if context is None:
            raise ComfyUILiveAdapterError(
                "ComfyUI output classification context is unavailable; durable execution "
                "reconstruction is introduced in a later Phase 20 subphase"
            )
        outputs = _history_outputs(history)
        return tuple(
            RenderOutput(
                output_id=f"RO-COMFY-{prompt_id}-{index:03d}",
                kind=_output_kind(path, context.quality_level),
                relative_path=path,
                request_id=context.request_id,
                renderer=self.renderer,
                workflow_id=context.workflow_id,
                quality_level=context.quality_level,
            )
            for index, path in enumerate(outputs, start=1)
        )

    @staticmethod
    def _prompt_id(job: RenderJob) -> str:
        prompt_id = (job.renderer_job_id or "").strip()
        if not prompt_id:
            raise ComfyUILiveAdapterError("RenderJob does not contain a ComfyUI prompt_id")
        return prompt_id

    @staticmethod
    def _from_history(job: RenderJob, history: dict[str, object]) -> RenderJob:
        status = _history_status(history)
        now = datetime.now(UTC)
        if status is RenderJobStatus.COMPLETED:
            return replace(
                job,
                status=RenderJobStatus.COMPLETED,
                started_at=job.started_at or job.submitted_at or now,
                finished_at=job.finished_at or now,
                progress=1.0,
                failure_reason=None,
            )
        if status is RenderJobStatus.FAILED:
            return replace(
                job,
                status=RenderJobStatus.FAILED,
                started_at=job.started_at or job.submitted_at or now,
                finished_at=job.finished_at or now,
                failure_reason=_history_failure_reason(history),
            )
        return job


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComfyUILiveAdapterError(f"ComfyUI {field_name} must be an object")
    return {str(key): item for key, item in value.items()}


def _quality_level(payload: dict[str, object]) -> QualityLevel:
    extra = payload.get("extra_data", {})
    if not isinstance(extra, dict):
        return QualityLevel.PRODUCTION
    raw = str(extra.get("quality_level", QualityLevel.PRODUCTION.value))
    try:
        return QualityLevel(raw)
    except ValueError as exc:
        raise ComfyUILiveAdapterError(
            f"Unsupported VSCS quality level in ComfyUI payload: {raw}"
        ) from exc


def _queue_contains(raw: object, prompt_id: str) -> bool:
    if not isinstance(raw, list):
        raise ComfyUILiveAdapterError("ComfyUI queue collection must be an array")
    for item in raw:
        if isinstance(item, list) and len(item) >= 2 and str(item[1]) == prompt_id:
            return True
    return False


def _history_status(history: dict[str, object]) -> RenderJobStatus | None:
    raw_status = history.get("status")
    if not isinstance(raw_status, dict):
        return None
    completed = bool(raw_status.get("completed", False))
    status_str = str(raw_status.get("status_str", "")).casefold()
    if completed and status_str in {"success", "completed"}:
        return RenderJobStatus.COMPLETED
    if completed:
        return RenderJobStatus.FAILED
    if status_str in {"error", "failed"}:
        return RenderJobStatus.FAILED
    return None


def _history_failure_reason(history: dict[str, object]) -> str:
    raw_status = history.get("status")
    if not isinstance(raw_status, dict):
        return "ComfyUI execution failed"
    messages = raw_status.get("messages", [])
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, list) and len(item) >= 2:
                return f"ComfyUI {item[0]}: {item[1]}"
    status_str = str(raw_status.get("status_str", "")).strip()
    return status_str or "ComfyUI execution failed"


def _history_outputs(history: dict[str, object]) -> tuple[str, ...]:
    raw_outputs = history.get("outputs", {})
    if not isinstance(raw_outputs, dict):
        raise ComfyUILiveAdapterError("ComfyUI history outputs must be an object")
    paths: set[str] = set()
    for node_output in raw_outputs.values():
        if not isinstance(node_output, dict):
            continue
        for collection in node_output.values():
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict):
                    continue
                output_type = str(item.get("type", "output")).casefold()
                if output_type != "output":
                    continue
                filename = str(item.get("filename", "")).strip()
                if not filename:
                    continue
                subfolder = str(item.get("subfolder", "")).strip().replace("\\", "/")
                candidate = (
                    PurePosixPath(subfolder) / filename if subfolder else PurePosixPath(filename)
                )
                normalized = str(candidate)
                if normalized.startswith("/") or ".." in candidate.parts:
                    raise ComfyUILiveAdapterError(
                        "ComfyUI output path must remain project-relative"
                    )
                paths.add(normalized)
    return tuple(sorted(paths))


def _output_kind(path: str, quality: QualityLevel) -> RenderOutputKind:
    suffix = PurePosixPath(path).suffix.casefold()
    if suffix in {".mp4", ".webm", ".mov", ".mkv", ".avi"}:
        return (
            RenderOutputKind.PREVIEW_VIDEO
            if quality is QualityLevel.PREVIEW
            else RenderOutputKind.PRODUCTION_VIDEO
        )
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        return RenderOutputKind.REFERENCE_FRAME
    raise ComfyUILiveAdapterError(f"Unsupported ComfyUI output type for Phase 20.5: {path}")
