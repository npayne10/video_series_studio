"""Tests for renderer-neutral request models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RenderRequest,
    RendererKind,
    RenderSettings,
)


def _request() -> RenderRequest:
    return RenderRequest(
        request_id="REQ-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="EP-001-SCN-001",
        shot_id="EP-001-SCN-001-SHT-001",
        clip_id="EP-001-SC001-SH001-CL001",
        renderer=RendererKind.COMFYUI,
        workflow_id="ltx23-i2v-preview-v1",
        quality_level=QualityLevel.PREVIEW,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=AssetPackageReference(asset_ids=("SHP-IRON-HORIZON",)),
        continuity=ContinuityPackageReference(previous_frame_id="FRAME-0001"),
        render=RenderSettings(960, 400, 24, 120),
        output=OutputSettings("renders/EP-001", "clip-001"),
    )


def test_render_request_is_immutable_and_complete() -> None:
    request = _request()
    assert request.render.duration_seconds == 5.0
    assert request.assets.asset_ids == ("SHP-IRON-HORIZON",)
    with pytest.raises(FrozenInstanceError):
        request.request_id = "OTHER"  # type: ignore[misc]


def test_render_models_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="width"):
        RenderSettings(0, 400, 24, 120)
    with pytest.raises(ValueError, match="project-relative"):
        OutputSettings("../outside", "clip")
    with pytest.raises(ValueError, match="request_id"):
        RenderRequest(
            request_id="",
            production_id="XORIX",
            container_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            clip_id="CLIP-001",
            renderer=RendererKind.COMFYUI,
            workflow_id="workflow",
            quality_level=QualityLevel.PREVIEW,
            prompt_package=PromptPackageReference("PROMPT-001"),
            assets=AssetPackageReference(),
            continuity=ContinuityPackageReference(),
            render=RenderSettings(960, 400, 24, 120),
            output=OutputSettings("renders", "clip"),
        )
