"""Deterministic provider-execution segmentation for constrained video renderers.

The governed Production Package remains authoritative for the complete Shot. LTX
provider segments use frame counts of 8n+1 and dimensions aligned to 32 pixels. The
assembly contract removes continuity overlap, trims only provider surplus frames, and
restores governed output geometry without changing Shot duration, FPS, references, or
ProductionTask authority.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderSegmentationPolicy:
    """Provider-specific execution limits and alignment rules."""

    provider: str = "ltx-2.3"
    max_frames_per_segment: int = 192
    frame_modulus: int = 8
    frame_offset: int = 1
    dimension_alignment: int = 32

    def __post_init__(self) -> None:
        if self.max_frames_per_segment <= 0:
            raise ValueError("max_frames_per_segment must be greater than zero")
        if self.frame_modulus <= 0:
            raise ValueError("frame_modulus must be greater than zero")
        if self.dimension_alignment <= 0:
            raise ValueError("dimension_alignment must be greater than zero")


class GovernedProviderSegmentationPlanner:
    """Build an LTX-valid segmentation plan while preserving governed runtime."""

    SCHEMA_VERSION = "1.1"

    def __init__(self, policy: ProviderSegmentationPolicy | None = None) -> None:
        self.policy = policy or ProviderSegmentationPolicy()

    def plan(
        self,
        *,
        frame_count: int,
        frames_per_second: int,
        seed: int,
        width: int | None = None,
        height: int | None = None,
    ) -> dict[str, object]:
        if frame_count <= 0:
            raise ValueError("frame_count must be greater than zero")
        if frames_per_second <= 0:
            raise ValueError("frames_per_second must be greater than zero")
        if width is not None and width <= 0:
            raise ValueError("width must be greater than zero")
        if height is not None and height <= 0:
            raise ValueError("height must be greater than zero")

        if self._valid_provider_frame_count(frame_count):
            provider_frames = (frame_count,)
            segment_count = 1
            overlap_trim_frames = 0
            tail_trim_frames = 0
        else:
            segment_count, provider_frames, tail_trim_frames = self._segmented_frames(frame_count)
            overlap_trim_frames = segment_count - 1

        governed_frames = self._balanced(frame_count, segment_count)
        segments: list[dict[str, object]] = []
        governed_start = 0
        for index, (governed_count, provider_count) in enumerate(
            zip(governed_frames, provider_frames, strict=True)
        ):
            governed_end = governed_start + governed_count - 1
            segments.append(
                {
                    "segment_id": f"SEG-{index + 1:03d}",
                    "index": index + 1,
                    "start_frame": governed_start,
                    "end_frame": governed_end,
                    "governed_frame_count": governed_count,
                    "frame_count": provider_count,
                    "provider_frame_count": provider_count,
                    "start_seconds": governed_start / frames_per_second,
                    "end_seconds": (governed_end + 1) / frames_per_second,
                    "seed": seed + index,
                    "continuity_input": (
                        "governed_initial_reference"
                        if index == 0
                        else "previous_segment_final_frame"
                    ),
                    "assembly_trim_start_frames": 0 if index == 0 else 1,
                }
            )
            governed_start = governed_end + 1

        segmented = segment_count > 1
        provider_width = self._aligned_dimension(width) if width is not None else None
        provider_height = self._aligned_dimension(height) if height is not None else None
        geometry_changed = (width is not None and provider_width != width) or (
            height is not None and provider_height != height
        )
        return {
            "schema_version": self.SCHEMA_VERSION,
            "provider": self.policy.provider,
            "mode": "segmented" if segmented else "monolithic",
            "reason": (
                "ltx_frame_alignment_or_segment_limit"
                if segmented
                else "within_provider_constraints"
            ),
            "governed_frame_count": frame_count,
            "frames_per_second": frames_per_second,
            "governed_duration_seconds": frame_count / frames_per_second,
            "max_frames_per_segment": self.policy.max_frames_per_segment,
            "provider_frame_rule": {
                "modulus": self.policy.frame_modulus,
                "offset": self.policy.frame_offset,
                "expression": "8n+1",
            },
            "provider_geometry": {
                "width": provider_width,
                "height": provider_height,
                "alignment": self.policy.dimension_alignment,
            },
            "segment_count": segment_count,
            "segments": segments,
            "assembly": {
                "required": segmented or geometry_changed,
                "mode": (
                    "normalized_continuity_aware_concatenation"
                    if segmented or geometry_changed
                    else "none"
                ),
                "continuity_overlap_trim_frames": overlap_trim_frames,
                "tail_trim_frames": tail_trim_frames,
                "preserve_governed_frame_count": True,
                "preserve_governed_fps": True,
                "restore_width": width,
                "restore_height": height,
                "strip_provider_audio": True,
            },
        }

    def _segmented_frames(self, governed_frame_count: int) -> tuple[int, tuple[int, ...], int]:
        largest = self._largest_valid_provider_frame_count()
        minimum_segments = max(
            2,
            (governed_frame_count + largest - 1) // largest,
        )
        segment_count = minimum_segments
        while True:
            minimum_total = governed_frame_count + (segment_count - 1)
            remainder = (
                segment_count * self.policy.frame_offset - minimum_total
            ) % self.policy.frame_modulus
            provider_total = minimum_total + remainder
            if provider_total <= segment_count * largest:
                units = (
                    provider_total - segment_count * self.policy.frame_offset
                ) // self.policy.frame_modulus
                base_units, extra_units = divmod(units, segment_count)
                provider_frames = tuple(
                    self.policy.frame_offset
                    + self.policy.frame_modulus * (base_units + (1 if index < extra_units else 0))
                    for index in range(segment_count)
                )
                if all(
                    0 < item <= self.policy.max_frames_per_segment
                    and self._valid_provider_frame_count(item)
                    for item in provider_frames
                ):
                    tail_trim = provider_total - governed_frame_count - (segment_count - 1)
                    return segment_count, provider_frames, tail_trim
            segment_count += 1

    def _valid_provider_frame_count(self, value: int) -> bool:
        return (
            0 < value <= self.policy.max_frames_per_segment
            and (value - self.policy.frame_offset) % self.policy.frame_modulus == 0
        )

    def _largest_valid_provider_frame_count(self) -> int:
        candidate = self.policy.max_frames_per_segment
        while candidate > 0 and not self._valid_provider_frame_count(candidate):
            candidate -= 1
        if candidate <= 0:
            raise ValueError("provider frame policy has no valid frame count")
        return candidate

    @staticmethod
    def _balanced(total: int, count: int) -> tuple[int, ...]:
        base, remainder = divmod(total, count)
        return tuple(base + (1 if index < remainder else 0) for index in range(count))

    def _aligned_dimension(self, value: int) -> int:
        aligned = value - (value % self.policy.dimension_alignment)
        if aligned <= 0:
            raise ValueError("provider-aligned dimension must be greater than zero")
        return aligned
