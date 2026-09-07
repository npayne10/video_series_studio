from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.hardware_shot_capability import (
    HardwareShotCapabilityError,
    LocalComfyUIHardwareCapabilityResolver,
    capability_for_vram,
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
        def __enter__(self) -> "_Response":
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
    snapshot = (
        tmp_path
        / ".vscs"
        / "provider_executions"
        / "hardware_capability.json"
    )
    stored = json.loads(snapshot.read_text(encoding="utf-8"))
    assert stored["capability"]["gpu_name"] == "NVIDIA GeForce RTX 4060"
    assert stored["capability"]["validated_maximum_shot_seconds"] == 7.0
