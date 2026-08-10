"""Renderer workflow capability declarations and matching."""

from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class WorkflowCapabilities:
    """Features exposed by one renderer workflow."""

    text_to_video: bool = False
    image_to_video: bool = False
    start_frame: bool = False
    end_frame: bool = False
    reference_images: bool = False
    multiple_reference_images: bool = False
    loras: bool = False
    audio: bool = False
    lip_sync: bool = False
    seed_control: bool = False
    batch: bool = False
    resume: bool = False

    def supports(self, required: WorkflowCapabilities) -> bool:
        """Return whether all requested capabilities are available."""
        return all(
            not getattr(required, item.name) or getattr(self, item.name) for item in fields(self)
        )

    def missing(self, required: WorkflowCapabilities) -> tuple[str, ...]:
        """Return required capability names that are unavailable."""
        return tuple(
            item.name
            for item in fields(self)
            if getattr(required, item.name) and not getattr(self, item.name)
        )
