"""Tests for the Advanced Clip Production Package foundation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.acpp import (
    ACPPBuildError,
    ACPPSerializer,
    ACPPValidator,
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ClipProductionPackageBuilder,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderQualityMode,
    RenderSpecification,
    SeedPolicy,
    build_clip_id,
)


def _package() -> ClipProductionPackage:
    clip_id = build_clip_id("PROD-XORIX-S01E01", 2, 4)
    return ClipProductionPackage(
        identity=ClipIdentity(
            clip_id=clip_id,
            production_id="PROD-XORIX-S01E01",
            episode_id="EP-001",
            scene_id="SCN-002",
            shot_id="SCN-002-S004",
        ),
        render=RenderSpecification(
            width=1920,
            height=800,
            frames_per_second=24,
            frame_count=240,
            quality_mode=RenderQualityMode.PRODUCTION,
            seed_policy=SeedPolicy.FIXED,
            fixed_seed=1442,
        ),
        assets=(
            AssetBinding(
                asset_id="LOC-MAURITANIA-BRIDGE",
                role=AssetBindingRole.LOCATION,
                canonical_reference_ids=("REF-BRIDGE-001",),
            ),
            AssetBinding(
                asset_id="CHR-JAMES",
                role=AssetBindingRole.SUBJECT,
                canonical_reference_ids=("REF-JAMES-001",),
            ),
        ),
        prompt=PromptSpecification(
            positive_visual_intent="James studies the bridge display in disciplined silence.",
            negative_constraints=("No exaggerated holographic glow.",),
            camera_language="Restrained medium close coverage.",
            lighting_intent="Maintain approved night bridge lighting.",
            environment_intent="Operational Mauritania bridge.",
            continuity_intent="Preserve James's screen position and wardrobe.",
        ),
        continuity=ContinuityBinding(
            incoming_clip_id="PROD-XORIX-S01E01-SC002-SH003-CL001",
            start_reference_id="FRAME-S003-END",
            requirements=("Maintain established screen direction.",),
            outgoing_state=("James remains at the command console.",),
        ),
        audio=AudioSpecification(
            dialogue_lines=("The signal is still there.",),
            voice_profile_ids=("VOICE-JAMES",),
            ambience_profile_id="AUDIO-BRIDGE-AMBIENCE",
        ),
        output=OutputSpecification(
            relative_directory="production/EP-001/SCN-002",
            filename_stem=clip_id,
        ),
        dependencies=("PROD-XORIX-S01E01-SC002-SH003-CL001",),
        metadata={"source": "ssie"},
    )


def test_build_clip_id_is_stable() -> None:
    assert build_clip_id(" PROD:XORIX ", 2, 4) == (
        "PROD-XORIX-SC002-SH004-CL001"
    )


def test_validator_accepts_complete_package() -> None:
    result = ACPPValidator().validate(_package())

    assert result.passed is True
    assert result.issues == []


def test_builder_rejects_invalid_package() -> None:
    package = _package()
    invalid = replace(
        package,
        render=replace(package.render, width=1919),
        prompt=replace(package.prompt, positive_visual_intent=""),
    )

    with pytest.raises(ACPPBuildError) as error:
        ClipProductionPackageBuilder().build(invalid)

    codes = {issue.code for issue in error.value.issues}
    assert "ODD_RENDER_DIMENSION" in codes
    assert "EMPTY_VISUAL_INTENT" in codes


def test_validator_reports_non_fatal_seed_warning() -> None:
    package = _package()
    package = replace(
        package,
        render=replace(
            package.render,
            seed_policy=SeedPolicy.DERIVED,
            fixed_seed=1442,
        ),
    )

    result = ACPPValidator().validate(package)

    assert result.passed is True
    assert [issue.code for issue in result.issues] == ["UNUSED_FIXED_SEED"]


def test_serializer_round_trips_package() -> None:
    serializer = ACPPSerializer()
    package = _package()

    restored = serializer.loads(serializer.dumps(package))

    assert restored == package
    assert restored.output.relative_path.endswith(".mp4")
    assert restored.render.duration_seconds == 10.0


def test_checksum_is_deterministic_and_content_sensitive() -> None:
    serializer = ACPPSerializer()
    package = _package()

    first = serializer.checksum(package)
    second = serializer.checksum(package)
    changed = serializer.checksum(
        replace(package, metadata={"source": "manual"})
    )

    assert first == second
    assert first != changed
    assert len(first) == 64
