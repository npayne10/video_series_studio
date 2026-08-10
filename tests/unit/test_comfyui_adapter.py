"""Tests for manifest-driven ComfyUI workflow compilation."""

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
    ComfyUIAdapterError,
    ComfyUIWorkflowCompiler,
)


def _manifest() -> WorkflowManifest:
    return WorkflowManifest(
        metadata=WorkflowMetadata(
            workflow_id="test_comfyui",
            display_name="Test ComfyUI",
            description="Test workflow",
            renderer=RendererKind.COMFYUI,
            workflow_version="1.0",
        ),
        quality_levels=(QualityLevel.PREVIEW,),
        capabilities=("text_to_video", "seed_control"),
        bindings=(
            WorkflowNodeBinding(
                WorkflowInputKind.POSITIVE_PROMPT,
                WorkflowNodeSelector(
                    logical_name="positive_prompt",
                    node_title="VSCS Positive Prompt",
                    class_type="CLIPTextEncode",
                ),
                "inputs.text",
            ),
            WorkflowNodeBinding(
                WorkflowInputKind.WIDTH,
                WorkflowNodeSelector(
                    logical_name="video_settings",
                    node_title="VSCS Video Settings",
                ),
                "inputs.width",
            ),
            WorkflowNodeBinding(
                WorkflowInputKind.SEED,
                WorkflowNodeSelector(
                    logical_name="sampler",
                    node_id="3",
                ),
                "inputs.seed",
                required=False,
            ),
        ),
        workflow_file="workflows/test_api.json",
    )


def _request() -> RenderRequest:
    return RenderRequest(
        request_id="REQ-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="test_comfyui",
        quality_level=QualityLevel.PREVIEW,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(960, 400, 24, 240, seed=42),
        output=OutputSettings("renders/preview", "shot-001"),
        metadata={"positive_prompt": "The Iron Horizon enters Xorix orbit."},
    )


def _write_workflow(root: Path, *, duplicate_title: bool = False) -> None:
    workflow = {
        "1": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "old"},
            "_meta": {"title": "VSCS Positive Prompt"},
        },
        "2": {
            "class_type": "VideoSettings",
            "inputs": {"width": 1},
            "_meta": {"title": "VSCS Video Settings"},
        },
        "3": {
            "class_type": "Sampler",
            "inputs": {"seed": 0},
            "_meta": {"title": "VSCS Sampler"},
        },
    }
    if duplicate_title:
        workflow["4"] = {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "duplicate"},
            "_meta": {"title": "VSCS Positive Prompt"},
        }
    path = root / "workflows" / "test_api.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(workflow), encoding="utf-8")


def _adapter(root: Path) -> ComfyUIAdapter:
    registry = WorkflowRegistry()
    registry.register(_manifest())
    return ComfyUIAdapter(
        registry,
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(root),
    )


def test_comfyui_compiler_injects_manifest_bound_values(tmp_path: Path) -> None:
    _write_workflow(tmp_path)
    compiled = _adapter(tmp_path).compile_request(_request())
    prompt = compiled.payload["prompt"]

    assert isinstance(prompt, dict)
    assert prompt["1"]["inputs"]["text"] == ("The Iron Horizon enters Xorix orbit.")
    assert prompt["2"]["inputs"]["width"] == 960
    assert prompt["3"]["inputs"]["seed"] == 42
    assert compiled.payload["extra_data"]["shot_id"] == "SHT-001"


def test_comfyui_validation_reports_missing_required_input(tmp_path: Path) -> None:
    _write_workflow(tmp_path)
    request = _request()
    request.metadata.clear()

    validation = _adapter(tmp_path).validate_request(request)

    assert not validation.passed
    assert "missing required workflow input: positive_prompt" in validation.messages


def test_comfyui_compiler_rejects_ambiguous_selector(tmp_path: Path) -> None:
    _write_workflow(tmp_path, duplicate_title=True)

    with pytest.raises(ComfyUIAdapterError, match="ambiguous"):
        _adapter(tmp_path).compile_request(_request())


def test_comfyui_submit_is_dry_run_and_cancelable(tmp_path: Path) -> None:
    _write_workflow(tmp_path)
    adapter = _adapter(tmp_path)
    job = adapter.submit(adapter.compile_request(_request()))

    assert job.status is RenderJobStatus.QUEUED
    assert job.renderer_job_id == "dry-run:REQ-001"
    assert adapter.fetch_outputs(job) == ()

    cancelled = adapter.cancel(job)
    assert cancelled.status is RenderJobStatus.CANCELLED
