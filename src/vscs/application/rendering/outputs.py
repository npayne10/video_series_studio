"""Render output and provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .models import QualityLevel, RendererKind


class RenderOutputKind(StrEnum):
    """Artifacts produced by renderer and post-production stages."""

    PREVIEW_VIDEO = "preview_video"
    PRODUCTION_VIDEO = "production_video"
    IMAGE_SEQUENCE = "image_sequence"
    DIALOGUE_AUDIO = "dialogue_audio"
    MUSIC = "music"
    EFFECTS = "effects"
    LIP_SYNC_VIDEO = "lip_sync_video"
    QC_REPORT = "qc_report"
    REFERENCE_FRAME = "reference_frame"
    METADATA = "metadata"


@dataclass(frozen=True, slots=True)
class RenderOutput:
    """One produced artifact with complete production provenance."""

    output_id: str
    kind: RenderOutputKind
    relative_path: str
    request_id: str
    renderer: RendererKind
    workflow_id: str
    quality_level: QualityLevel
    version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    checksum: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("output_id", self.output_id),
            ("relative_path", self.relative_path),
            ("request_id", self.request_id),
            ("workflow_id", self.workflow_id),
            ("version", self.version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        normalized = self.relative_path.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("relative_path must remain project-relative")
