"""Core renderer-neutral rendering models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RendererKind(StrEnum):
    """Renderer families supported by the VSCS abstraction."""

    COMFYUI = "comfyui"
    LTX = "ltx"
    WAN = "wan"
    FLUX = "flux"
    SDXL = "sdxl"
    FUTURE = "future"


class QualityLevel(StrEnum):
    """Approved production quality levels."""

    PREVIEW = "preview"
    PRODUCTION = "production"


class AudioMode(StrEnum):
    """Audio intent associated with a render profile."""

    NONE = "none"
    DRAFT = "draft"
    FINAL = "final"


class LipSyncIntent(StrEnum):
    """High-level lip-sync intent before detailed contracts are added."""

    NONE = "none"
    DRAFT = "draft"
    FINAL = "final"


@dataclass(frozen=True, slots=True)
class RenderSettings:
    """Renderer-neutral technical render settings."""

    width: int
    height: int
    frames_per_second: int
    frame_count: int
    sampling_effort: int = 1
    reference_strength: float = 1.0
    upscale: bool = False
    seed: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("width", self.width),
            ("height", self.height),
            ("frames_per_second", self.frames_per_second),
            ("frame_count", self.frame_count),
            ("sampling_effort", self.sampling_effort),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if not 0.0 <= self.reference_strength <= 2.0:
            raise ValueError("reference_strength must be between 0.0 and 2.0")

    @property
    def duration_seconds(self) -> float:
        """Return the requested duration in seconds."""
        return self.frame_count / self.frames_per_second


@dataclass(frozen=True, slots=True)
class OutputSettings:
    """Relative renderer output requirements."""

    relative_directory: str
    filename_stem: str
    container: str = "mp4"

    def __post_init__(self) -> None:
        if not self.filename_stem.strip():
            raise ValueError("filename_stem is required")
        if not self.container.strip():
            raise ValueError("container is required")
        normalized = self.relative_directory.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("relative_directory must remain project-relative")


@dataclass(frozen=True, slots=True)
class PromptPackageReference:
    """Reference to a future renderer-neutral prompt package."""

    package_id: str
    version: str = "1.0"
    checksum: str | None = None


@dataclass(frozen=True, slots=True)
class AssetPackageReference:
    """Canonical asset IDs required by a render request."""

    asset_ids: tuple[str, ...] = ()
    canonical_reference_ids: tuple[str, ...] = ()
    lora_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContinuityPackageReference:
    """Reference to continuity state supplied by a later phase."""

    package_id: str | None = None
    previous_frame_id: str | None = None
    next_frame_id: str | None = None
    requirements: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderRequest:
    """Universal renderer-independent request submitted by VSCS."""

    request_id: str
    production_id: str
    container_id: str
    scene_id: str
    shot_id: str
    clip_id: str
    renderer: RendererKind
    workflow_id: str
    quality_level: QualityLevel
    prompt_package: PromptPackageReference
    assets: AssetPackageReference
    continuity: ContinuityPackageReference
    render: RenderSettings
    output: OutputSettings
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("production_id", self.production_id),
            ("container_id", self.container_id),
            ("scene_id", self.scene_id),
            ("shot_id", self.shot_id),
            ("clip_id", self.clip_id),
            ("workflow_id", self.workflow_id),
            ("prompt_package.package_id", self.prompt_package.package_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
