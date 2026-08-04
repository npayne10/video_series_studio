"""Tests for canonical voice profiles and timed dialogue contracts."""

from __future__ import annotations

import pytest

from vscs.application.rendering import (
    DialogueCue,
    DialogueTiming,
    VoiceEmotion,
    VoiceGenerationRequest,
    VoiceProfile,
    VoiceProfileRegistry,
)


def _profile() -> VoiceProfile:
    return VoiceProfile(
        profile_id="VOI-JAMES-SPENCE",
        character_asset_id="CHR-JAMES-SPENCE",
        provider="kokoro",
        voice_id="am_liam",
        language="en",
        accent="American",
        speaking_rate=0.9,
        default_emotion=VoiceEmotion.AUTHORITATIVE,
        pronunciation_overrides=(("Xorix", "ZOR-iks"),),
    )


def test_voice_profile_registry_preserves_character_identity() -> None:
    profile = _profile()
    registry = VoiceProfileRegistry()
    registry.register(profile)

    assert registry.get(profile.profile_id) is profile
    assert registry.for_character("CHR-JAMES-SPENCE") == (profile,)
    assert registry.list() == (profile,)


def test_voice_generation_request_accepts_timed_and_overlapping_cues() -> None:
    cues = (
        DialogueCue(
            cue_id="CUE-001",
            character_asset_id="CHR-JAMES-SPENCE",
            voice_profile_id="VOI-JAMES-SPENCE",
            text="Take us into orbit.",
            timing=DialogueTiming(1.0, 2.5),
            emotion=VoiceEmotion.AUTHORITATIVE,
            face_target_id="FACE-JAMES",
        ),
        DialogueCue(
            cue_id="CUE-002",
            character_asset_id="CHR-SANDRA-CRAWFORD",
            voice_profile_id="VOI-SANDRA-CRAWFORD",
            text="Course confirmed.",
            timing=DialogueTiming(2.0, 3.2),
            off_screen=True,
        ),
    )
    request = VoiceGenerationRequest(
        request_id="VOICE-SHT-001",
        production_id="XORIX",
        scene_id="SCN-001",
        shot_id="SHT-001",
        cues=cues,
        output_directory="audio/dialogue/SCN-001",
    )

    assert request.cues[0].timing.duration_seconds == 1.5
    assert request.cues[1].off_screen


def test_voice_contracts_reject_invalid_timing_and_identity() -> None:
    with pytest.raises(ValueError, match="greater"):
        DialogueTiming(2.0, 2.0)
    with pytest.raises(ValueError, match="face target"):
        DialogueCue(
            cue_id="CUE-BAD",
            character_asset_id="CHR-JAMES-SPENCE",
            voice_profile_id="VOI-JAMES-SPENCE",
            text="Bad cue",
            timing=DialogueTiming(0.0, 1.0),
            off_screen=True,
            face_target_id="FACE-JAMES",
        )
    duplicate = DialogueCue(
        cue_id="CUE-DUPLICATE",
        character_asset_id="CHR-A",
        voice_profile_id="VOI-A",
        text="Duplicate",
        timing=DialogueTiming(0.0, 1.0),
    )
    with pytest.raises(ValueError, match="unique"):
        VoiceGenerationRequest(
            request_id="VOICE-BAD",
            production_id="XORIX",
            scene_id="SCN-001",
            shot_id="SHT-001",
            cues=(duplicate, duplicate),
            output_directory="audio/dialogue",
        )
