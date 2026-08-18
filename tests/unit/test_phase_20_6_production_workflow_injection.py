"""Focused workflow tests for Phase 20.6 production-package injection."""

import json
from pathlib import Path

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderRequest,
    RenderSettings,
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.infrastructure.rendering import (
    ComfyUIWorkflowCompiler,
    ProductionPackageComfyUIAdapter,
)


def test_v714_reference_workflow_uses_queue_selected_production_package() -> None:
    root = Path("resources/workflows")
    raw = json.loads(
        (root / "manifests/video_production_engine_v7_1_4.json").read_text(encoding="utf-8")
    )
    registry = WorkflowRegistry()
    registry.register(WorkflowManifest.from_dict(raw))
    adapter = ProductionPackageComfyUIAdapter(
        registry,
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(root),
    )
    package = r"D:\Xorix\Production\XPC_Output\ACPP-QUEUE-SELECTED.json"
    request = RenderRequest(
        request_id="REQ-20-6-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="video_production_engine_v7_1_4",
        quality_level=QualityLevel.PRODUCTION,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(1280, 720, 24, 145),
        output=OutputSettings("renders/production", "clip-001"),
        metadata={"production_package": package},
    )

    compiled = adapter.compile_request(request)
    prompt = compiled.payload["prompt"]
    assert isinstance(prompt, dict)
    loader = prompt["107"]
    assert loader["class_type"] == "XorixProductionPackageLoaderV714"
    assert loader["inputs"]["production_package"] == package
