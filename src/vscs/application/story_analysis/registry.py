"""Registration and discovery for story-analysis stage plugins."""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from vscs.application.story_analysis.contracts import StoryAnalysisStage


class StoryAnalysisStageRegistry:
    """Owns the ordered set of story-analysis stage plugins."""

    def __init__(self, stages: Iterable[StoryAnalysisStage] = ()) -> None:
        self._stages: dict[str, StoryAnalysisStage] = {}
        for stage in stages:
            self.register(stage)

    def register(self, stage: StoryAnalysisStage) -> StoryAnalysisStage:
        stage_id = stage.stage_id.strip()
        if not stage_id:
            raise ValueError("analysis stage_id must not be blank")
        if stage_id in self._stages:
            raise ValueError(f"analysis stage already registered: {stage_id}")
        self._stages[stage_id] = stage
        return stage

    def replace(self, stage: StoryAnalysisStage) -> StoryAnalysisStage:
        stage_id = stage.stage_id.strip()
        if not stage_id:
            raise ValueError("analysis stage_id must not be blank")
        self._stages[stage_id] = stage
        return stage

    def remove(self, stage_id: str) -> StoryAnalysisStage:
        try:
            return self._stages.pop(stage_id)
        except KeyError as error:
            raise KeyError(f"analysis stage is not registered: {stage_id}") from error

    def get(self, stage_id: str) -> StoryAnalysisStage:
        try:
            return self._stages[stage_id]
        except KeyError as error:
            raise KeyError(f"analysis stage is not registered: {stage_id}") from error

    def contains(self, stage_id: str) -> bool:
        return stage_id in self._stages

    def enabled_stages(self) -> tuple[StoryAnalysisStage, ...]:
        return tuple(
            sorted(
                (stage for stage in self._stages.values() if stage.enabled),
                key=lambda stage: (stage.order, stage.stage_id),
            )
        )

    def __len__(self) -> int:
        return len(self._stages)

    def __iter__(self) -> Iterator[StoryAnalysisStage]:
        return iter(self.enabled_stages())
