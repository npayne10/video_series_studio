"""Integration acceptance for Phase 20.4 registration into Phase 20.5 live ComfyUI."""

from __future__ import annotations

import json
from pathlib import Path

from vscs.application.production_tasks import (
    ProductionCapability,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    ProviderExecutionContext,
    ProviderExecutionState,
    ProviderHealthState,
    ProviderRegistration,
    RenderProviderExecutionCompiler,
)
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
    WorkflowInputKind,
    WorkflowManifest,
    WorkflowMetadata,
    WorkflowNodeBinding,
    WorkflowNodeSelector,
    WorkflowRegistry,
)
from vscs.domain.generated_media import GeneratedMediaKind
from vscs.infrastructure.provider_execution import ComfyUIProviderAdapterFactory
from vscs.infrastructure.rendering import ComfyUIAdapter, ComfyUIWorkflowCompiler


class IntegrationTransport:
    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        if method == "POST" and path == "/prompt":
            assert payload is not None
            return {"prompt_id": "PROMPT-INTEGRATION-001"}
        if method == "GET" and path == "/history/PROMPT-INTEGRATION-001":
            return {}
        if method == "GET" and path == "/queue":
            return {
                "queue_running": [[1, "PROMPT-INTEGRATION-001", {}, {}, []]],
                "queue_pending": [],
            }
        if method == "GET" and path == "/system_stats":
            return {"system": {}, "devices": []}
        raise AssertionError(f"Unexpected request: {method} {path}")


def _foundation(tmp_path: Path) -> ComfyUIAdapter:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}}}),
        encoding="utf-8",
    )
    manifest = WorkflowManifest(
        metadata=WorkflowMetadata(
            workflow_id="LTX-LIVE",
            display_name="LTX Live",
            description="Phase 20.5 integration",
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
        workflow_file="workflow.json",
    )
    registry = WorkflowRegistry()
    registry.register(manifest)
    return ComfyUIAdapter(
        registry,
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(tmp_path),
    )


def _render_request() -> RenderRequest:
    return RenderRequest(
        request_id="REQ-INTEGRATION-001",
        production_id="PROD-001",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="LTX-LIVE",
        quality_level=QualityLevel.PRODUCTION,
        prompt_package=PromptPackageReference("PROMPT-PACKAGE-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(1920, 1080, 24, 240),
        output=OutputSettings("provider_outputs", "clip-001"),
        metadata={"positive_prompt": "A controlled atmospheric descent."},
    )


def test_phase_20_5_registration_composes_live_provider_execution(tmp_path: Path) -> None:
    registration = ProviderRegistration(
        provider_id="LOCAL-COMFYUI-01",
        adapter_type="comfyui",
        resource_id="LOCAL-GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
        supported_media_kinds=frozenset({GeneratedMediaKind.VIDEO}),
        endpoint="http://127.0.0.1:8188",
        health=ProviderHealthState.UNKNOWN,
    )
    provider = ComfyUIProviderAdapterFactory().build(
        registration,
        _foundation(tmp_path),
        transport=IntegrationTransport(),
    )
    context = ProviderExecutionContext(
        execution_id="PEX-001",
        production_id="PROD-001",
        task_id="PT-001",
        queue_id="PQ-001",
        entry_id="PQE-001",
        resource_id="LOCAL-GPU-01",
        worker_id="WORKER-01",
        lease_id="LEASE-001",
        attempt_number=1,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        required_capabilities=(ProductionCapability.VIDEO_GENERATION,),
        authority_fingerprint="authority-fingerprint",
    )
    compiler = RenderProviderExecutionCompiler()
    execution_request = compiler.compile(
        context,
        _render_request(),
        provider.adapter,
    )

    handle = provider.submit(execution_request)
    running = provider.monitor(handle)

    assert handle.provider_id == "LOCAL-COMFYUI-01"
    assert handle.provider_job_id == "PROMPT-INTEGRATION-001"
    assert handle.execution_id == "PEX-001"
    assert running.state is ProviderExecutionState.RUNNING
