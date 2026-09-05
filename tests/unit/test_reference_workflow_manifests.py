"""Tests for the approved LTX 2.3 reference workflow manifests."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    InstalledWorkflowResources,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderRequest,
    RenderSettings,
    WorkflowCompatibilityValidator,
    WorkflowInputKind,
    WorkflowManifestLoader,
)

REFERENCE_ROOT = Path(__file__).resolve().parents[2] / "resources" / "workflows" / "manifests"


def _request(
    workflow_id: str,
    quality_level: QualityLevel,
    *,
    previous_frame_id: str | None = None,
    next_frame_id: str | None = None,
) -> RenderRequest:
    return RenderRequest(
        request_id=f"REQ-{workflow_id}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="EP-001-SCN-001",
        shot_id="EP-001-SCN-001-SHT-001",
        clip_id="EP-001-SC001-SH001-CL001",
        renderer=RendererKind.COMFYUI,
        workflow_id=workflow_id,
        quality_level=quality_level,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(
            previous_frame_id=previous_frame_id,
            next_frame_id=next_frame_id,
        ),
        render=RenderSettings(
            width=960 if quality_level is QualityLevel.PREVIEW else 1920,
            height=400 if quality_level is QualityLevel.PREVIEW else 800,
            frames_per_second=24,
            frame_count=240,
            seed=42,
        ),
        output=OutputSettings(
            relative_directory="renders",
            filename_stem=workflow_id,
        ),
    )


def test_reference_manifests_load_and_declare_expected_profiles() -> None:
    loader = WorkflowManifestLoader(REFERENCE_ROOT)
    preview = loader.parse_file(REFERENCE_ROOT / "ltx23_preview_v1.json")
    production = loader.parse_file(REFERENCE_ROOT / "ltx23_production_v1.json")

    assert preview.quality_levels == (QualityLevel.PREVIEW,)
    assert production.quality_levels == (QualityLevel.PRODUCTION,)
    assert preview.metadata.renderer is RendererKind.COMFYUI
    assert production.metadata.renderer is RendererKind.COMFYUI
    assert preview.binding_for(WorkflowInputKind.POSITIVE_PROMPT) is not None
    assert production.bindings == ()
    assert dict(production.extra)["binding_mode"] == "production_package_v7_2_1"
    assert (
        dict(production.extra)["governed_reference_resolution"] == "VSCSMultiReferenceResolverV721"
    )


def test_reference_manifests_pass_compatibility_with_declared_resources() -> None:
    loader = WorkflowManifestLoader(REFERENCE_ROOT)
    validator = WorkflowCompatibilityValidator()
    installed = InstalledWorkflowResources(
        video_models=frozenset({"ltx-2.3"}),
        loras=frozenset({"LTX-2.3 Ingredients IC-LoRA"}),
        custom_nodes=frozenset(
            {
                "ComfyUI-LTXVideo",
                "Licon-MSR",
                "VSCS-Temporal-Refinement",
                "ComfyUI-VSCS-Production-v721",
            }
        ),
    )
    preview = loader.parse_file(REFERENCE_ROOT / "ltx23_preview_v1.json")
    production = loader.parse_file(REFERENCE_ROOT / "ltx23_production_v1.json")

    preview_report = validator.validate(
        _request("ltx23_preview_v1", QualityLevel.PREVIEW),
        preview,
        installed=installed,
    )
    production_report = validator.validate(
        _request(
            "ltx23_production_v1",
            QualityLevel.PRODUCTION,
            previous_frame_id="FRAME-PREVIOUS",
        ),
        production,
        installed=installed,
    )

    assert preview_report.passed
    assert production_report.passed
