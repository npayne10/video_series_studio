"""Focused tests for Phase 20.5 live ComfyUI provider execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderJobStatus,
    RenderOutputKind,
    RenderRequest,
    RenderSettings,
    WorkflowCompatibilityValidator,
    WorkflowInputKind,
    WorkflowManifest,
    WorkflowMetadata,
    WorkflowNodeBinding,
    WorkflowNodeSelector,
    WorkflowRegistry,
)
from vscs.infrastructure.rendering import (
    ComfyUIAdapter,
    ComfyUIClient,
    ComfyUILiveAdapterError,
    ComfyUIWorkflowCompiler,
    LiveComfyUIAdapter,
)


class FakeComfyUITransport:
    def __init__(self) -> None:
        self.prompt_id = "PROMPT-LIVE-001"
        self.queue_running: list[object] = []
        self.queue_pending: list[object] = []
        self.history_item: dict[str, object] | None = None
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        self.calls.append((method, path, payload))
        if method == "GET" and path == "/system_stats":
            return {
                "system": {"os": "nt", "python_version": "3.13"},
                "devices": [{"name": "GPU-0", "type": "cuda"}],
            }
        if method == "POST" and path == "/prompt":
            return {"prompt_id": self.prompt_id, "number": 7}
        if method == "GET" and path == "/queue":
            return {
                "queue_running": self.queue_running,
                "queue_pending": self.queue_pending,
            }
        if method == "GET" and path == f"/history/{self.prompt_id}":
            return {self.prompt_id: self.history_item} if self.history_item is not None else {}
        if method == "POST" and path == "/queue":
            delete = payload.get("delete", []) if payload is not None else []
            if isinstance(delete, list):
                self.queue_pending = [
                    item
                    for item in self.queue_pending
                    if not (isinstance(item, list) and len(item) >= 2 and item[1] in delete)
                ]
            return {}
        raise AssertionError(f"Unexpected ComfyUI request: {method} {path}")


def _manifest() -> WorkflowManifest:
    return WorkflowManifest(
        metadata=WorkflowMetadata(
            workflow_id="phase_20_5_video",
            display_name="Phase 20.5 Video",
            description="Live adapter test workflow",
            renderer=RendererKind.COMFYUI,
            workflow_version="1.0",
        ),
        quality_levels=(QualityLevel.PRODUCTION,),
        capabilities=("text_to_video",),
        bindings=(
            WorkflowNodeBinding(
                WorkflowInputKind.POSITIVE_PROMPT,
                WorkflowNodeSelector(logical_name="prompt", node_id="1"),
                "inputs.text",
            ),
        ),
        workflow_file="phase_20_5_api.json",
    )


def _write_workflow(root: Path) -> None:
    (root / "phase_20_5_api.json").write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": "old"},
                }
            }
        ),
        encoding="utf-8",
    )


def _request() -> RenderRequest:
    return RenderRequest(
        request_id="REQ-LIVE-001",
        production_id="PROD-001",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="phase_20_5_video",
        quality_level=QualityLevel.PRODUCTION,
        prompt_package=PromptPackageReference("PROMPT-PACKAGE-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(1920, 1080, 24, 240),
        output=OutputSettings("provider_outputs", "clip-001"),
        metadata={"positive_prompt": "The Iron Horizon enters orbit."},
    )


def _live_adapter(tmp_path: Path) -> tuple[LiveComfyUIAdapter, FakeComfyUITransport]:
    _write_workflow(tmp_path)
    registry = WorkflowRegistry()
    registry.register(_manifest())
    foundation = ComfyUIAdapter(
        registry,
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(tmp_path),
    )
    transport = FakeComfyUITransport()
    return (
        LiveComfyUIAdapter(
            foundation,
            ComfyUIClient(transport, "http://127.0.0.1:8188"),
        ),
        transport,
    )


def test_live_comfyui_health_and_submission_use_http_contract(tmp_path: Path) -> None:
    adapter, transport = _live_adapter(tmp_path)

    health = adapter.health()
    compiled = adapter.compile_request(_request())
    job = adapter.submit(compiled)

    assert health.healthy
    assert health.endpoint == "http://127.0.0.1:8188"
    assert health.devices[0]["name"] == "GPU-0"
    assert job.status is RenderJobStatus.QUEUED
    assert job.renderer_job_id == "PROMPT-LIVE-001"
    assert any(method == "POST" and path == "/prompt" for method, path, _ in transport.calls)


def test_live_comfyui_monitor_maps_running_queue_state(tmp_path: Path) -> None:
    adapter, transport = _live_adapter(tmp_path)
    job = adapter.submit(adapter.compile_request(_request()))
    transport.queue_running = [[7, transport.prompt_id, {}, {}, []]]

    running = adapter.monitor(job)

    assert running.status is RenderJobStatus.RUNNING
    assert running.progress == 0.1
    assert running.started_at is not None


def test_live_comfyui_history_completes_job_and_discovers_video_output(tmp_path: Path) -> None:
    adapter, transport = _live_adapter(tmp_path)
    job = adapter.submit(adapter.compile_request(_request()))
    transport.history_item = {
        "status": {"status_str": "success", "completed": True, "messages": []},
        "outputs": {
            "42": {
                "gifs": [
                    {
                        "filename": "clip-001.mp4",
                        "subfolder": "provider_outputs",
                        "type": "output",
                    }
                ]
            }
        },
    }

    completed = adapter.monitor(job)
    outputs = adapter.fetch_outputs(completed)

    assert completed.status is RenderJobStatus.COMPLETED
    assert completed.progress == 1.0
    assert len(outputs) == 1
    assert outputs[0].kind is RenderOutputKind.PRODUCTION_VIDEO
    assert outputs[0].relative_path == "provider_outputs/clip-001.mp4"
    assert outputs[0].request_id == "REQ-LIVE-001"
    assert outputs[0].workflow_id == "phase_20_5_video"


def test_live_comfyui_history_maps_provider_failure(tmp_path: Path) -> None:
    adapter, transport = _live_adapter(tmp_path)
    job = adapter.submit(adapter.compile_request(_request()))
    transport.history_item = {
        "status": {
            "status_str": "error",
            "completed": True,
            "messages": [["execution_error", "model failed"]],
        },
        "outputs": {},
    }

    failed = adapter.monitor(job)

    assert failed.status is RenderJobStatus.FAILED
    assert failed.failure_reason is not None
    assert "execution_error" in failed.failure_reason


def test_live_comfyui_can_delete_queued_prompt(tmp_path: Path) -> None:
    adapter, transport = _live_adapter(tmp_path)
    job = adapter.submit(adapter.compile_request(_request()))
    transport.queue_pending = [[7, transport.prompt_id, {}, {}, []]]

    cancelled = adapter.cancel(job)

    assert cancelled.status is RenderJobStatus.CANCELLED
    assert transport.queue_pending == []
    assert any(
        method == "POST" and path == "/queue" and payload == {"delete": [transport.prompt_id]}
        for method, path, payload in transport.calls
    )


def test_live_comfyui_refuses_global_interrupt_for_running_prompt(tmp_path: Path) -> None:
    adapter, transport = _live_adapter(tmp_path)
    job = adapter.submit(adapter.compile_request(_request()))
    transport.queue_running = [[7, transport.prompt_id, {}, {}, []]]
    running = adapter.monitor(job)

    with pytest.raises(ComfyUILiveAdapterError, match="global /interrupt"):
        adapter.cancel(running)

    assert all(path != "/interrupt" for _method, path, _payload in transport.calls)
