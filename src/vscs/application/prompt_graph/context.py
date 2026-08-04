"""Input contracts for deterministic prompt graph construction."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.rendering import QualityLevel, RendererKind


@dataclass(frozen=True, slots=True)
class PromptGraphBuildContext:
    """Stable ownership and profile data required to build one graph."""

    graph_id: str
    production_id: str
    container_id: str
    scene_id: str
    shot_id: str
    clip_id: str | None = None
    renderer: RendererKind = RendererKind.COMFYUI
    quality_level: QualityLevel = QualityLevel.PREVIEW
    workflow_id: str = ""

    def __post_init__(self) -> None:
        for name, value in (
            ("graph_id", self.graph_id),
            ("production_id", self.production_id),
            ("container_id", self.container_id),
            ("scene_id", self.scene_id),
            ("shot_id", self.shot_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
