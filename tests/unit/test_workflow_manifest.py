"""Tests for immutable workflow manifest contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vscs.application.rendering import (
    LipSyncMode,
    QualityLevel,
    RendererKind,
    RenderOutputKind,
    WorkflowInputKind,
    WorkflowManifest,
    WorkflowMetadata,
    WorkflowNodeBinding,
    WorkflowNodeSelector,
    WorkflowRequirement,
    WorkflowRequirementKind,
    workflow_manifest_schema,
)


def _manifest() -> WorkflowManifest:
    return WorkflowManifest(
        metadata=WorkflowMetadata(
            workflow_id="ltx23_video_v1",
            display_name="LTX 2.3 Video",
            description="Reference renderer-neutral workflow manifest.",
            renderer=RendererKind.COMFYUI,
            workflow_version="1.0",
            author="VSCS",
        ),
        quality_levels=(QualityLevel.PREVIEW, QualityLevel.PRODUCTION),
        capabilities=("image_to_video", "start_frame", "seed_control"),
        bindings=(
            WorkflowNodeBinding(
                input_kind=WorkflowInputKind.POSITIVE_PROMPT,
                selector=WorkflowNodeSelector(
                    logical_name="positive_prompt",
                    node_title="VSCS Positive Prompt",
                ),
                field_path="inputs.text",
            ),
            WorkflowNodeBinding(
                input_kind=WorkflowInputKind.FRAME_COUNT,
                selector=WorkflowNodeSelector(
                    logical_name="video_settings",
                    class_type="LTXVConditioning",
                ),
                field_path="inputs.frame_count",
            ),
        ),
        requirements=(
            WorkflowRequirement(
                kind=WorkflowRequirementKind.VIDEO_MODEL,
                identifier="ltx-video-2.3",
                version="2.3",
            ),
            WorkflowRequirement(
                kind=WorkflowRequirementKind.CUSTOM_NODE,
                identifier="ComfyUI-LTXVideo",
            ),
        ),
        output_kinds=(RenderOutputKind.PREVIEW_VIDEO,),
        lip_sync_modes=(LipSyncMode.NONE,),
        tags=("ltx", "video"),
        workflow_file="workflows/ltx23_video_v1.json",
    )


def test_workflow_manifest_is_immutable_and_queryable() -> None:
    manifest = _manifest()

    assert manifest.workflow_id == "ltx23_video_v1"
    assert manifest.supports_quality(QualityLevel.PRODUCTION)
    assert (
        manifest.binding_for(WorkflowInputKind.FRAME_COUNT).field_path
        == "inputs.frame_count"
    )
    with pytest.raises(FrozenInstanceError):
        manifest.workflow_file = "changed.json"  # type: ignore[misc]


def test_workflow_manifest_round_trips_json_compatible_data() -> None:
    manifest = _manifest()
    raw = manifest.to_dict()
    restored = WorkflowManifest.from_dict(raw)

    assert restored == manifest
    assert raw["metadata"]["renderer"] == "comfyui"
    assert raw["quality_levels"] == ["preview", "production"]
    assert raw["bindings"][0]["input_kind"] == "positive_prompt"


def test_workflow_manifest_schema_describes_required_structure() -> None:
    schema = workflow_manifest_schema()

    assert schema["type"] == "object"
    assert schema["required"] == ["metadata", "quality_levels"]
    assert schema["properties"]["quality_levels"]["minItems"] == 1


def test_workflow_manifest_rejects_ambiguous_or_unsafe_contracts() -> None:
    binding = WorkflowNodeBinding(
        input_kind=WorkflowInputKind.POSITIVE_PROMPT,
        selector=WorkflowNodeSelector(
            logical_name="positive_prompt",
            node_id="6",
        ),
        field_path="inputs.text",
    )
    metadata = WorkflowMetadata(
        workflow_id="bad",
        display_name="Bad",
        description="",
        renderer=RendererKind.COMFYUI,
        workflow_version="1.0",
    )

    with pytest.raises(ValueError, match="bindings"):
        WorkflowManifest(
            metadata=metadata,
            quality_levels=(QualityLevel.PREVIEW,),
            bindings=(binding, binding),
        )
    with pytest.raises(ValueError, match="project-relative"):
        WorkflowManifest(
            metadata=metadata,
            quality_levels=(QualityLevel.PREVIEW,),
            workflow_file="../outside.json",
        )
    with pytest.raises(ValueError, match="node selector"):
        WorkflowNodeSelector(logical_name="missing_selector")
