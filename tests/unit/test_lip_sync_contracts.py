"""Tests for renderer-neutral lip-sync contracts."""

from __future__ import annotations

import pytest

from vscs.application.rendering import (
    DialogueCue,
    DialogueTiming,
    LipSyncContractValidator,
    LipSyncMode,
    LipSyncRequest,
    LipSyncTarget,
)


def _cue(
    cue_id: str,
    character_id: str,
    start: float,
    end: float,
    target_id: str | None,
) -> DialogueCue:
    return DialogueCue(
        cue_id=cue_id,
        character_asset_id=character_id,
        voice_profile_id=f"VOI-{character_id}",
        text="Dialogue",
        timing=DialogueTiming(start, end),
        face_target_id=target_id,
    )


def test_single_speaker_lip_sync_requires_matching_face_target() -> None:
    request = LipSyncRequest(
        request_id="LIP-SHT-001",
        production_id="XORIX",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        mode=LipSyncMode.SINGLE_SPEAKER,
        source_video_path="renders/SCN-001/CLIP-001.mp4",
        output_directory="renders/SCN-001/lipsync",
        dialogue_cues=(
            _cue("CUE-001", "CHR-JAMES", 0.5, 2.0, "FACE-JAMES"),
        ),
        targets=(
            LipSyncTarget(
                target_id="FACE-JAMES",
                character_asset_id="CHR-JAMES",
                face_reference_ids=("REF-JAMES-FRONT",),
            ),
        ),
        audio_reference_ids=("AUD-CUE-001",),
    )

    assert request.requires_lip_sync


def test_lip_sync_modes_validate_off_screen_and_precision_rules() -> None:
    off_screen_cue = DialogueCue(
        cue_id="CUE-OFF",
        character_asset_id="CHR-SANDRA",
        voice_profile_id="VOI-SANDRA",
        text="Course confirmed.",
        timing=DialogueTiming(0.0, 1.5),
        off_screen=True,
    )
    request = LipSyncRequest(
        request_id="LIP-OFF",
        production_id="XORIX",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        mode=LipSyncMode.OFF_SCREEN,
        source_video_path="renders/clip.mp4",
        output_directory="renders/lipsync",
        dialogue_cues=(off_screen_cue,),
        audio_reference_ids=("AUD-OFF",),
    )
    assert not request.requires_lip_sync

    with pytest.raises(ValueError, match="precision_required"):
        LipSyncRequest(
            request_id="LIP-PRECISION",
            production_id="XORIX",
            scene_id="SCN-001",
            shot_id="SHT-001",
            clip_id="CLIP-001",
            mode=LipSyncMode.PRECISION_CLOSE_UP,
            source_video_path="renders/clip.mp4",
            output_directory="renders/lipsync",
            dialogue_cues=(
                _cue("CUE-001", "CHR-JAMES", 0.0, 1.0, "FACE-JAMES"),
            ),
            targets=(
                LipSyncTarget("FACE-JAMES", "CHR-JAMES"),
            ),
        )


def test_multi_speaker_capability_validation_reports_incompatibility() -> None:
    request = LipSyncRequest(
        request_id="LIP-MULTI",
        production_id="XORIX",
        scene_id="SCN-001",
        shot_id="SHT-001",
        clip_id="CLIP-001",
        mode=LipSyncMode.MULTIPLE_SPEAKERS,
        source_video_path="renders/clip.mp4",
        output_directory="renders/lipsync",
        dialogue_cues=(
            _cue("CUE-A", "CHR-A", 0.0, 1.0, "FACE-A"),
            _cue("CUE-B", "CHR-B", 1.1, 2.0, "FACE-B"),
        ),
        targets=(
            LipSyncTarget("FACE-A", "CHR-A"),
            LipSyncTarget("FACE-B", "CHR-B"),
        ),
    )
    result = LipSyncContractValidator().validate_capabilities(
        request,
        supports_lip_sync=True,
        supports_multiple_speakers=False,
        supports_precision_close_up=False,
    )

    assert not result.passed
    assert result.issues == ("workflow does not support multiple speakers",)
