from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.production_execution import CompiledProductionPackage
from vscs.infrastructure.production_execution.hardware_shot_capability import (
    HardwareShotCapability,
    capability_for_vram,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)
from vscs.infrastructure.production_execution.segmented_backend import (
    SegmentedLTX23V721ProductionPackageCompilationService,
)


def _compiled(frame_count: int, *, profile: str = "production") -> CompiledProductionPackage:
    return CompiledProductionPackage(
        task_id="PT-HARDWARE-5060TI",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        profile=profile,
        authority_id="UPD-SHT-001",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="reviewer",
        source_package_id="PP-SHT-001",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="A governed hardware revalidation shot.",
        positive_prompt="A governed hardware revalidation shot.",
        negative_prompt="identity drift",
        previous_approved_final_frame=None,
        filename_prefix="VSCS/Production/SHT-001",
        width=1280,
        height=720,
        frame_count=frame_count,
        frames_per_second=24,
        cfg=1.25,
        ic_lora_strength=0.46,
        seed=42,
        composition_plan={"mode": "single_shot"},
        production_authority={"approved": True},
        package_fingerprint="neutral",
        reference_plan=None,
    )


def _rtx_5060_ti_capability() -> HardwareShotCapability:
    return capability_for_vram(
        16 * 1024**3,
        gpu_name="NVIDIA GeForce RTX 5060 Ti",
    )


def test_rtx5060ti_16gb_is_detected_as_controlled_revalidation_target() -> None:
    capability = _rtx_5060_ti_capability()

    assert capability.vram_class_gb == 16
    assert capability.validation_status == "revalidation-required"
    assert capability.validated_maximum_shot_seconds == 7.0
    assert capability.governed_maximum_frame_count == 168
    assert capability.revalidation_maximum_shot_seconds == 16.0
    assert capability.revalidation_candidate_shot_seconds == (
        8.0,
        10.0,
        12.0,
        14.0,
        16.0,
    )
    assert capability.source == "phase-20.18.2.2b-rtx5060ti-16gb-revalidation"


def test_other_16gb_gpu_remains_conservative_until_separately_validated() -> None:
    capability = capability_for_vram(
        16 * 1024**3,
        gpu_name="Different 16 GB GPU",
    )

    assert capability.validation_status == "conservative-until-validated"
    assert capability.validated_maximum_shot_seconds == 7.0
    assert capability.revalidation_maximum_shot_seconds is None
    assert capability.revalidation_candidate_shot_seconds == ()


def test_production_profile_keeps_seven_second_ceiling_on_rtx5060ti(tmp_path: Path) -> None:
    service = SegmentedLTX23V721ProductionPackageCompilationService(tmp_path)
    service.set_hardware_capability(_rtx_5060_ti_capability())

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match=r"validated production 7\.0s",
    ):
        service._comfyui_payload(_compiled(192, profile="production"))


@pytest.mark.parametrize(
    ("seconds", "frames", "provider_frames"),
    (
        (8, 192, 193),
        (10, 240, 241),
        (12, 288, 289),
        (14, 336, 337),
        (16, 384, 385),
    ),
)
def test_preview_profile_allows_only_staged_rtx5060ti_revalidation_candidates(
    tmp_path: Path,
    seconds: int,
    frames: int,
    provider_frames: int,
) -> None:
    service = SegmentedLTX23V721ProductionPackageCompilationService(tmp_path)
    service.set_hardware_capability(_rtx_5060_ti_capability())

    payload = service._comfyui_payload(_compiled(frames, profile="preview"))
    policy = payload["hardware_shot_policy"]

    assert payload["provider_execution_plan"]["provider_frame_count"] == provider_frames
    assert policy["validation_status"] == "revalidation-required"
    assert policy["validated_maximum_shot_seconds"] == 7.0
    assert policy["active_maximum_shot_seconds"] == 16.0
    assert policy["active_maximum_frame_count"] == 384
    assert policy["revalidation_active"] is True
    assert policy["production_approved"] is False
    assert seconds in policy["revalidation_candidate_shot_seconds"]


def test_preview_profile_rejects_non_staged_duration_above_production_ceiling(
    tmp_path: Path,
) -> None:
    service = SegmentedLTX23V721ProductionPackageCompilationService(tmp_path)
    service.set_hardware_capability(_rtx_5060_ti_capability())

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="must use one staged candidate duration",
    ):
        service._comfyui_payload(_compiled(216, profile="preview"))


def test_preview_profile_rejects_duration_above_revalidation_ceiling(
    tmp_path: Path,
) -> None:
    service = SegmentedLTX23V721ProductionPackageCompilationService(tmp_path)
    service.set_hardware_capability(_rtx_5060_ti_capability())

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match=r"controlled revalidation 16\.0s",
    ):
        service._comfyui_payload(_compiled(408, profile="preview"))
