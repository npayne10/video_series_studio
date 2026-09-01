"""Deterministic provider-execution segmentation for constrained video renderers.

The governed Production Package remains authoritative for the complete Shot.  This
module derives a provider-only execution plan that may split the governed frame
range into smaller execution units without changing Shot duration, FPS, references,
or ProductionTask authority.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderSegmentationPolicy:
    """Provider-specific frame ceiling used only for execution adaptation."""

    provider: str = "ltx-2.3"
    max_frames_per_segment: int = 192

    def __post_init__(self) -> None:
        if self.max_frames_per_segment <= 0:
            raise ValueError("max_frames_per_segment must be greater than zero")


class GovernedProviderSegmentationPlanner:
    """Build a deterministic segmentation plan while preserving governed runtime."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, policy: ProviderSegmentationPolicy | None = None) -> None:
        self.policy = policy or ProviderSegmentationPolicy()

    def plan(self, *, frame_count: int, frames_per_second: int, seed: int) -> dict[str, object]:
        if frame_count <= 0:
            raise ValueError("frame_count must be greater than zero")
        if frames_per_second <= 0:
            raise ValueError("frames_per_second must be greater than zero")

        segment_count = max(
            1,
            (frame_count + self.policy.max_frames_per_segment - 1)
            // self.policy.max_frames_per_segment,
        )
        base_frames, remainder = divmod(frame_count, segment_count)

        segments: list[dict[str, object]] = []
        start_frame = 0
        for index in range(segment_count):
            segment_frames = base_frames + (1 if index < remainder else 0)
            end_frame = start_frame + segment_frames - 1
            segments.append(
                {
                    "segment_id": f"SEG-{index + 1:03d}",
                    "index": index + 1,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "frame_count": segment_frames,
                    "start_seconds": start_frame / frames_per_second,
                    "end_seconds": (end_frame + 1) / frames_per_second,
                    "seed": seed + index,
                    "continuity_input": (
                        "governed_initial_reference"
                        if index == 0
                        else "previous_segment_final_frame"
                    ),
                }
            )
            start_frame = end_frame + 1

        segmented = segment_count > 1
        return {
            "schema_version": self.SCHEMA_VERSION,
            "provider": self.policy.provider,
            "mode": "segmented" if segmented else "monolithic",
            "reason": (
                "governed_frame_count_exceeds_provider_segment_limit"
                if segmented
                else "within_provider_segment_limit"
            ),
            "governed_frame_count": frame_count,
            "frames_per_second": frames_per_second,
            "governed_duration_seconds": frame_count / frames_per_second,
            "max_frames_per_segment": self.policy.max_frames_per_segment,
            "segment_count": segment_count,
            "segments": segments,
            "assembly": {
                "required": segmented,
                "mode": "ordered_lossless_concatenation" if segmented else "none",
                "preserve_governed_frame_count": True,
                "preserve_governed_fps": True,
            },
        }
