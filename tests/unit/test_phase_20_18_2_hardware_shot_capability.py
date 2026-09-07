from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.application.production_execution import CompiledProductionPackage
from vscs.infrastructure.production_execution.hardware_shot_capability import (
    HardwareShotCapabilityError,
    LocalComfyUIHardwareCapabilityResolver,
    capability_for_vram,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)
from vscs.infrastructure.production_execution.segmented_backend import (
    SegmentedLTX23V721ProductionPackageCompilationService,
)


def _compiled(frame_count: int) -> CompiledProductionPackage:
    return CompiledProductionPackage(
        task_id="PT-HARDWARE-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        profile="production",
        authority_id="UPD-SHT-001",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="reviewer",
        source_package_id="PP-SHT-001",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="A short governed cinematic shot.",
        positive_prompt="A short governed cinematic shot.",
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


def test_eight_gb_ltx_capability_uses_validated_seven_second_governed_shot() -> None:
    capability = capability_for_vram(
        8 * 1024**3,
        gpu_name="NVIDIA GeForce RTX 4060",
    )

    assert capability.vram_class_gb == 8
    assert capability.validation_status == "validated"
    assert capability.validated_maximum_shot_seconds == 7.0
    assert capability.frames_per_second == 24
    assert capability.governed_maximum_frame_count == 168
    assert capability.provider_maximum_frame_count == 169
    assert (capability.provider_maximum_frame_count - 1) % 8 == 0


def test_unvalidated_higher_vram_class_remains_conservative_until_live_acceptance() -> None:
    capability = capability_for_vram(16 * 1024**3, gpu_name="Future 16 GB GPU")

    assert capability.vram_class_gb == 16
    assert capability.validation_status == "conservative-until-validated"
    assert capability.validated_maximum_shot_seconds == 7.0
    assert capability.governed_maximum_frame_count == 168


def test_hardware_capability_rejects_invalid_vram() -> None:
    with pytest.raises(HardwareShotCapabilityError, match="greater than zero"):
        capability_for_vram(0)


def test_resolver_extracts_comfyui_vram_and_persists_project_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "devices": [
            {
                "name": "NVIDIA GeForce RTX 4060",
                "vram_total": 8 * 1024**3,
            }
        ]
    }

    class _Response:
        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(),
    )

    resolver = LocalComfyUIHardwareCapabilityResolver(
        tmp_path,
        "http://127.0.0.1:8188",
    )
    capability = resolver.resolve()

    assert capability.vram_class_gb == 8
    snapshot = tmp_path / ".vscs" / "provider_executions" / "hardware_capability.json"
    stored = json.loads(snapshot.read_text(encoding="utf-8"))
    assert stored["capability"]["gpu_name"] == "NVIDIA GeForce RTX 4060"
    assert stored["capability"]["validated_maximum_shot_seconds"] == 7.0


def test_hardware_aware_compiler_rejects_long_governed_shot(tmp_path: Path) -> None:
    service = SegmentedLTX23V721ProductionPackageCompilationService(tmp_path)
    service.set_hardware_capability(
        capability_for_vram(8 * 1024**3, gpu_name="NVIDIA GeForce RTX 4060")
    )

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="Re-plan the scene as multiple independent cinematic Shots",
    ):
        service._comfyui_payload(_compiled(169))


def test_hardware_aware_compiler_emits_monolithic_one_shot_plan(tmp_path: Path) -> None:
    service = SegmentedLTX23V721ProductionPackageCompilationService(tmp_path)
    service.set_hardware_capability(
        capability_for_vram(8 * 1024**3, gpu_name="NVIDIA GeForce RTX 4060")
    )

    payload = service._comfyui_payload(_compiled(168))

    assert payload["hardware_shot_policy"]["mode"] == "one_shot_per_provider_job"
    assert payload["provider_execution_plan"]["mode"] == "monolithic"
    assert payload["provider_execution_plan"]["hidden_segmentation"] is False
    assert payload["provider_execution_plan"]["governed_frame_count"] == 168
    assert payload["provider_execution_plan"]["provider_frame_count"] == 169
    assert payload["provider_execution_plan"]["assembly"]["required"] is False
