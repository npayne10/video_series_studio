"""Tests for Phase 17.4.0.2 rendering-media contract integration."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    ContinuityStateRegistry,
    LipSyncPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderRequest,
    RenderSettings,
    VoicePackageReference,
    VoiceProfileRegistry,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_bootstrap_registers_continuity_and_voice_registries(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))

    assert context.services.contains(ContinuityStateRegistry)
    assert context.services.contains(VoiceProfileRegistry)
    assert context.services.require(ContinuityStateRegistry).list() == ()
    assert context.services.require(VoiceProfileRegistry).list() == ()
    context.shutdown()


def test_render_request_accepts_voice_and_lip_sync_references() -> None:
    request = RenderRequest(
        request_id="REQ-001",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        renderer=RendererKind.COMFYUI,
        workflow_id="LTX-I2V-PREVIEW",
        quality_level=QualityLevel.PREVIEW,
        prompt_package=PromptPackageReference("PROMPT-001"),
        assets=AssetPackageReference(asset_ids=("CHR-JAMES",)),
        continuity=ContinuityPackageReference(
            package_id="CONT-001",
            previous_frame_id="FRAME-0001",
        ),
        render=RenderSettings(
            width=960,
            height=400,
            frames_per_second=24,
            frame_count=240,
        ),
        output=OutputSettings("renders/preview", "CLIP-001"),
        voice=VoicePackageReference(
            request_id="VOICE-001",
            voice_profile_ids=("VOI-JAMES",),
            dialogue_cue_ids=("CUE-001",),
            audio_reference_ids=("AUD-001",),
        ),
        lip_sync=LipSyncPackageReference(
            request_id="LIP-001",
            mode="single_speaker",
            required=True,
        ),
    )

    assert request.voice.voice_profile_ids == ("VOI-JAMES",)
    assert request.lip_sync.required
