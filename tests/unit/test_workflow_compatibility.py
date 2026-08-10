"""Tests for workflow compatibility validation."""

from __future__ import annotations

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
    WorkflowManifest,
    WorkflowMetadata,
    WorkflowRequirement,
    WorkflowRequirementKind,
)


def _request(**overrides: object) -> RenderRequest:
    values: dict[str, object] = {
        "request_id": "REQ-001",
        "production_id": "XORIX",
        "container_id": "EP-001",
        "scene_id": "SCN-001",
        "shot_id": "SHT-001",
        "clip_id": "CLIP-001",
        "renderer": RendererKind.COMFYUI,
        "workflow_id": "ltx-preview",
        "quality_level": QualityLevel.PREVIEW,
        "prompt_package": PromptPackageReference("PROMPT-001"),
        "assets": AssetPackageReference(),
        "continuity": ContinuityPackageReference(),
        "render": RenderSettings(960, 400, 24, 120),
        "output": OutputSettings("renders/preview", "clip-001"),
    }
    values.update(overrides)
    return RenderRequest(**values)  # type: ignore[arg-type]


def _manifest(**overrides: object) -> WorkflowManifest:
    values: dict[str, object] = {
        "metadata": WorkflowMetadata(
            workflow_id="ltx-preview",
            display_name="LTX Preview",
            description="Reference preview workflow",
            renderer=RendererKind.COMFYUI,
            workflow_version="1.0",
        ),
        "quality_levels": (QualityLevel.PREVIEW,),
        "capabilities": ("text_to_video",),
    }
    values.update(overrides)
    return WorkflowManifest(**values)  # type: ignore[arg-type]


def test_compatible_request_passes() -> None:
    report = WorkflowCompatibilityValidator().validate(
        _request(),
        _manifest(),
        installed=InstalledWorkflowResources(),
    )

    assert report.passed
    assert report.errors == ()


def test_renderer_quality_and_capability_mismatches_are_errors() -> None:
    request = _request(
        renderer=RendererKind.LTX,
        quality_level=QualityLevel.PRODUCTION,
        assets=AssetPackageReference(
            canonical_reference_ids=("REF-1", "REF-2"),
            lora_ids=("LORA-1",),
        ),
        continuity=ContinuityPackageReference(previous_frame_id="FRAME-1"),
        render=RenderSettings(1920, 800, 24, 240, seed=42),
    )
    report = WorkflowCompatibilityValidator().validate(
        request,
        _manifest(),
        installed=InstalledWorkflowResources(),
    )

    codes = {item.code for item in report.errors}
    assert "workflow.renderer_mismatch" in codes
    assert "workflow.quality_unsupported" in codes
    assert "workflow.capability_missing" in codes


def test_missing_required_resource_fails_and_optional_resource_warns() -> None:
    manifest = _manifest(
        requirements=(
            WorkflowRequirement(
                WorkflowRequirementKind.VIDEO_MODEL,
                "ltx-video-2.3",
            ),
            WorkflowRequirement(
                WorkflowRequirementKind.LORA,
                "optional-style",
                optional=True,
            ),
        )
    )
    report = WorkflowCompatibilityValidator().validate(
        _request(),
        manifest,
        installed=InstalledWorkflowResources(),
    )

    assert not report.passed
    assert any(item.subject == "ltx-video-2.3" for item in report.errors)
    assert any(item.subject == "optional-style" for item in report.warnings)


def test_unresolved_continuity_is_warning_not_exception() -> None:
    request = _request(continuity=ContinuityPackageReference(package_id="CONT-001"))
    report = WorkflowCompatibilityValidator().validate(
        request,
        _manifest(),
        installed=InstalledWorkflowResources(),
    )

    assert report.passed
    assert any(item.code == "workflow.continuity_unresolved" for item in report.warnings)
