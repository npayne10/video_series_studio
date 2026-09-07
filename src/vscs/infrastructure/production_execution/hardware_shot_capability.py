"""Hardware-aware governed Shot limits for Phase 20.18.2.

The provider backend no longer hides long governed Shots behind sequential provider
segments. A Shot must fit the validated capability of the active GPU/provider pair and
is executed as one normal provider job. Hardware observations are persisted so the
project can explain which capability constrained planning and compilation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class HardwareShotCapabilityError(RuntimeError):
    """Raised when provider hardware capability cannot be resolved safely."""


@dataclass(frozen=True, slots=True)
class HardwareShotCapability:
    provider: str
    gpu_name: str
    total_vram_bytes: int
    vram_class_gb: int
    validated_maximum_shot_seconds: float
    governed_maximum_frame_count: int
    provider_maximum_frame_count: int
    frames_per_second: int
    validation_status: str
    source: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def capability_for_vram(
    total_vram_bytes: int,
    *,
    gpu_name: str = "unknown",
    provider: str = "ltx-2.3",
    frames_per_second: int = 24,
) -> HardwareShotCapability:
    """Resolve the conservative validated capability for an observed GPU."""
    if total_vram_bytes <= 0:
        raise HardwareShotCapabilityError("GPU total VRAM must be greater than zero")
    gib = total_vram_bytes / (1024**3)
    if gib <= 8.5:
        vram_class = 8
        maximum_seconds = 7.0
        status = "validated"
        source = "phase-20.18.2-live-rtx4060-8gb"
    else:
        vram_class = max(9, round(gib))
        maximum_seconds = 7.0
        status = "conservative-until-validated"
        source = "phase-20.18.2-safe-fallback"

    governed_frames = int(maximum_seconds * frames_per_second)
    provider_frames = governed_frames
    while (provider_frames - 1) % 8 != 0:
        provider_frames += 1

    return HardwareShotCapability(
        provider=provider,
        gpu_name=gpu_name,
        total_vram_bytes=total_vram_bytes,
        vram_class_gb=vram_class,
        validated_maximum_shot_seconds=maximum_seconds,
        governed_maximum_frame_count=governed_frames,
        provider_maximum_frame_count=provider_frames,
        frames_per_second=frames_per_second,
        validation_status=status,
        source=source,
    )


class LocalComfyUIHardwareCapabilityResolver:
    """Read ComfyUI GPU VRAM and persist one project-local capability snapshot."""

    SNAPSHOT = Path(".vscs") / "provider_executions" / "hardware_capability.json"

    def __init__(
        self,
        project_directory: Path,
        endpoint: str,
        *,
        request_timeout_seconds: float = 10.0,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.endpoint = endpoint.strip().rstrip("/")
        self.request_timeout_seconds = request_timeout_seconds

    def resolve(self) -> HardwareShotCapability:
        raw = self._system_stats()
        devices = raw.get("devices")
        if not isinstance(devices, list) or not devices:
            raise HardwareShotCapabilityError("ComfyUI system_stats reported no GPU devices")
        device = next((item for item in devices if isinstance(item, dict)), None)
        if device is None:
            raise HardwareShotCapabilityError("ComfyUI GPU device record is invalid")
        total = self._total_vram(device)
        name = str(device.get("name") or device.get("device_name") or "unknown")
        capability = capability_for_vram(total, gpu_name=name)
        self._persist(capability)
        return capability

    def _system_stats(self) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.endpoint}/system_stats",
            method="GET",
            headers={"Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HardwareShotCapabilityError(
                f"Unable to read ComfyUI hardware capability at {self.endpoint}: {exc}"
            ) from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HardwareShotCapabilityError(
                "ComfyUI system_stats did not return valid JSON"
            ) from exc
        if not isinstance(value, dict):
            raise HardwareShotCapabilityError("ComfyUI system_stats root must be an object")
        return value

    @staticmethod
    def _total_vram(device: dict[str, Any]) -> int:
        for key in ("vram_total", "total_vram", "torch_vram_total"):
            raw = device.get(key)
            if isinstance(raw, (int, float)) and raw > 0:
                return int(raw)
        raise HardwareShotCapabilityError("ComfyUI device record has no total VRAM value")

    def _persist(self, capability: HardwareShotCapability) -> None:
        path = self.project_directory / self.SNAPSHOT
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "observed_at": datetime.now(UTC).isoformat(),
            "capability": capability.to_dict(),
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
