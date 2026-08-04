"""End-to-end tests for the Phase 17.4.0 rendering foundation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityFrameReference,
    ContinuityPackage,
    ContinuityPackageReference,
    InstalledWorkflowResources,
    LipSyncPackageReference,
    ManifestDiscoveryResult,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RenderAdapterRegistry,
    RendererKind,
    RenderingContracts,
    RenderJobStatus,
    RenderRequest,
    RenderSettings,
    VoicePackageReference,
    WorkflowCompatibilityValidator,
    WorkflowDiagnosticsFormatter,
    WorkflowManifest,
    WorkflowManifestLoader,
    WorkflowRegistry,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.infrastructure.rendering import ComfyUIAdapter, ComfyUIWorkflowCompiler

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_MANIFEST_ROOT = _REPOSITORY_ROOT / "resources" / "workflows" / "manifests"


def _install_reference_manifests(root: Path) -> Path:
    manifest_root = root / "manifests"
    manifest_root.mkdir(parents=True)
    for filename in ("ltx23_preview_v1.json", "ltx23_production_v1.json"):
        shutil.copy2(_REFERENCE_MANIFEST_ROOT / filename, manifest_root / filename)
    return manifest_root


def _write_api_workflow(root: Path, manifest: WorkflowManifest) -> None:
    workflow: dict[str, dict[str, object]] = {}
    nodes_by_selector: dict[tuple[str | None, str | None], str] = {}
    next_id = 1
    for binding in manifest.bindings:
        selector = binding.selector
        selector_key = (selector.node_title, selector.class_type)
        node_id = selector.node_id
        if node_id is None:
            node_id = nodes_by_selector.get(selector_key)
        if node_id is None:
            node_id = str(next_id)
            next_id += 1
            nodes_by_selector[selector_key] = node_id
        if node_id not in workflow:
            node: dict[str, object] = {
                "class_type": selector.class_type or "VSCSReferenceNode",
                "inputs": {},
            }
            if selector.node_title is not None:
                node["_meta"] = {"title": selector.node_title}
            workflow[node_id] = node
    assert manifest.workflow_file is not None
    path = root / manifest.workflow_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(workflow), encoding="utf-8")


def _discover_foundation(tmp_path: Path) -> tuple[WorkflowRegistry, ManifestDiscoveryResult]:
    registry = WorkflowRegistry()
    loader = WorkflowManifestLoader(_install_reference_manifests(tmp_path))
    result = loader.discover(registry)
    for manifest in registry.list():
        _write_api_workflow(tmp_path, manifest)
    return registry, result


def _request(
    workflow_id: str,
    quality: QualityLevel,
    *,
    continuity: ContinuityPackageReference | None = None,
    assets: AssetPackageReference | None = None,
    voice: VoicePackageReference | None = None,
    lip_sync: LipSyncPackageReference | None = None,
) -> RenderRequest:
    metadata = {
        "positive_prompt": (
            "The 145-metre Iron Horizon survey vessel crosses Xorix orbit, "
            "with four rear fusion engines producing controlled blue-white trails."
        ),
        "negative_prompt": (
            "No orange flames, smoke, additional engines, side thrusters, "
            "generic ship design, or fantasy energy effects."
        ),
        "reference_images": "references/iron-horizon-approved.png",
        "lora": "Licon-MSR",
    }
    selected_continuity = continuity or ContinuityPackageReference()
    if selected_continuity.previous_frame_id is not None:
        metadata["start_frame"] = "continuity/previous-final.png"
    if selected_continuity.next_frame_id is not None:
        metadata["end_frame"] = "continuity/next-start.png"
    return RenderRequest(
        request_id=f"REQ-{quality.value.upper()}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id=workflow_id,
        quality_level=quality,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=assets or AssetPackageReference(),
        continuity=selected_continuity,
        render=RenderSettings(
            960 if quality is QualityLevel.PREVIEW else 1920,
            400 if quality is QualityLevel.PREVIEW else 800,
            24,
            240,
            seed=42,
        ),
        output=OutputSettings(
            f"renders/{quality.value}",
            "EP-001-SCN-001-SHT-001",
        ),
        voice=voice or VoicePackageReference(),
        lip_sync=lip_sync or LipSyncPackageReference(),
        metadata=metadata,
    )


def _adapter(tmp_path: Path, registry: WorkflowRegistry) -> ComfyUIAdapter:
    return ComfyUIAdapter(
        registry,
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(tmp_path),
    )


def test_reference_manifests_discover_and_report_as_one_catalogue(tmp_path: Path) -> None:
    registry, result = _discover_foundation(tmp_path)
    report = WorkflowDiagnosticsFormatter().format_discovery(result)

    assert result.discovered_files == 2
    assert result.loaded_count == 2
    assert result.error_count == 0
    assert tuple(item.workflow_id for item in registry.list()) == (
        "ltx23_preview_v1",
        "ltx23_production_v1",
    )
    assert "Manifests loaded: 2" in report
    assert "ltx23_preview_v1" in report
    assert "ltx23_production_v1" in report


def test_preview_foundation_compiles_submits_and_cancels_dry_run(tmp_path: Path) -> None:
    registry, _result = _discover_foundation(tmp_path)
    adapter = _adapter(tmp_path, registry)
    request = _request("ltx23_preview_v1", QualityLevel.PREVIEW)

    validation = adapter.validate_request(request)
    compiled = adapter.compile_request(request)
    job = adapter.submit(compiled)

    assert validation.passed
    assert compiled.payload["extra_data"]["quality_level"] == "preview"
    assert compiled.payload["extra_data"]["shot_id"] == "SHT-001"
    assert job.status is RenderJobStatus.QUEUED
    assert adapter.monitor(job) is job
    assert adapter.fetch_outputs(job) == ()
    assert adapter.cancel(job).status is RenderJobStatus.CANCELLED


def test_production_foundation_injects_continuity_and_canonical_assets(
    tmp_path: Path,
) -> None:
    registry, _result = _discover_foundation(tmp_path)
    manifest = registry.require("ltx23_production_v1")
    continuity_reference = ContinuityPackageReference(
        package_id="CONT-001",
        previous_frame_id="FRAME-PREVIOUS",
        next_frame_id="FRAME-NEXT",
    )
    assets = AssetPackageReference(
        asset_ids=("SHP-IRON-HORIZON",),
        canonical_reference_ids=("REF-IRON-HORIZON-EXT",),
        lora_ids=("Licon-MSR",),
    )
    request = _request(
        manifest.workflow_id,
        QualityLevel.PRODUCTION,
        continuity=continuity_reference,
        assets=assets,
    )
    compiled = _adapter(tmp_path, registry).compile_request(request)
    prompt = compiled.payload["prompt"]

    start_binding = manifest.binding_for("start_frame")
    end_binding = manifest.binding_for("end_frame")
    reference_binding = manifest.binding_for("reference_images")
    lora_binding = manifest.binding_for("lora")
    assert start_binding is not None
    assert end_binding is not None
    assert reference_binding is not None
    assert lora_binding is not None

    values = json.dumps(prompt)
    assert "continuity/previous-final.png" in values
    assert "continuity/next-start.png" in values
    assert "references/iron-horizon-approved.png" in values
    assert "Licon-MSR" in values
    assert compiled.payload["extra_data"]["quality_level"] == "production"


def test_compatibility_reports_resources_continuity_voice_and_lip_sync(
    tmp_path: Path,
) -> None:
    registry, _result = _discover_foundation(tmp_path)
    manifest = registry.require("ltx23_production_v1")
    continuity = ContinuityPackage(
        package_id="CONT-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        previous_frame=ContinuityFrameReference(
            "FRAME-PREVIOUS",
            "continuity/previous-final.png",
        ),
    )
    request = _request(
        manifest.workflow_id,
        QualityLevel.PRODUCTION,
        continuity=ContinuityPackageReference(
            package_id=continuity.package_id,
            previous_frame_id="FRAME-PREVIOUS",
        ),
        voice=VoicePackageReference(request_id="VOICE-001"),
        lip_sync=LipSyncPackageReference(
            request_id="LIPSYNC-001",
            mode="single_speaker",
            required=True,
        ),
    )
    report = WorkflowCompatibilityValidator().validate(
        request,
        manifest,
        installed=InstalledWorkflowResources(
            video_models=frozenset({"ltx-2.3"}),
            custom_nodes=frozenset({"ComfyUI-LTXVideo"}),
        ),
        continuity=continuity,
    )
    codes = {item.code for item in report.diagnostics}

    assert not report.passed
    assert "workflow.capability_missing" in codes
    assert "workflow.resource_missing" in codes
    assert "workflow.lip_sync_unresolved" in codes
    assert "workflow.continuity_shot_mismatch" not in codes


def test_bootstrap_closes_phase_17_4_0_foundation(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )

    contracts = context.services.require(RenderingContracts)
    adapters = context.services.require(RenderAdapterRegistry)
    validator = context.services.require(WorkflowCompatibilityValidator)
    formatter = context.services.require(WorkflowDiagnosticsFormatter)

    assert contracts.version == "17.4.0.5"
    assert adapters.contains(RendererKind.COMFYUI)
    assert isinstance(validator, WorkflowCompatibilityValidator)
    assert isinstance(formatter, WorkflowDiagnosticsFormatter)

    context.shutdown()
