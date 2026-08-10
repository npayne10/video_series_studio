"""Production hierarchy projections for Story Browser v2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.ssie import Scene, ScenePlan

from .containers import ProductionContainerType, infer_container_type


class StoryNodeKind(StrEnum):
    """Kinds displayed in the production hierarchy."""

    PRODUCTION = "production"
    SEASON = "season"
    COLLECTION = "collection"
    CONTAINER = "container"
    ACT = "act"
    SCENE = "scene"
    SHOT = "shot"


class StoryItemStatus(StrEnum):
    """Production readiness states used by Story Browser v2."""

    DRAFT = "draft"
    READY = "ready"
    PLANNED = "planned"
    COMPLETE = "complete"

    @property
    def label(self) -> str:
        """Return a human-readable status label."""
        return self.value.title()


@dataclass(frozen=True, slots=True)
class StoryNode:
    """One immutable node in the projected production hierarchy."""

    kind: StoryNodeKind
    node_id: str
    label: str
    status: StoryItemStatus
    duration_seconds: float = 0.0
    asset_count: int = 0
    scene_id: str | None = None
    shot_id: str | None = None
    children: tuple[StoryNode, ...] = ()


@dataclass(frozen=True, slots=True)
class StoryStatistics:
    """Summary values displayed by the production dashboard."""

    containers: int
    scenes: int
    shots: int
    planned_scenes: int
    ready_scenes: int
    draft_scenes: int
    duration_seconds: float
    referenced_assets: int


@dataclass(frozen=True, slots=True)
class StoryHierarchy:
    """Complete Story Browser v2 hierarchy and dashboard statistics."""

    roots: tuple[StoryNode, ...]
    statistics: StoryStatistics


def scene_status(scene: Scene, plan: ScenePlan | None) -> StoryItemStatus:
    """Derive a stable status without changing the existing scene schema."""
    if plan is not None:
        return StoryItemStatus.PLANNED
    required_complete = all(
        (
            scene.scene_name.strip(),
            scene.heading.strip(),
            scene.location_asset_id.strip(),
            scene.summary.strip(),
        )
    )
    return StoryItemStatus.READY if required_complete else StoryItemStatus.DRAFT


def build_story_hierarchy(
    scenes: tuple[Scene, ...],
    plans: dict[str, ScenePlan],
    *,
    production_name: str = "Current Production",
) -> StoryHierarchy:
    """Project legacy scenes into a production-first navigation hierarchy."""
    by_container: dict[str, list[Scene]] = {}
    for scene in scenes:
        by_container.setdefault(scene.episode_id, []).append(scene)

    episodic: list[StoryNode] = []
    promotional: list[StoryNode] = []
    total_shots = 0
    planned_scenes = 0
    ready_scenes = 0
    draft_scenes = 0
    duration = 0.0
    referenced_assets: set[str] = set()

    for container_id in sorted(by_container):
        container_scenes = sorted(
            by_container[container_id],
            key=lambda item: (item.sequence_number, item.scene_id),
        )
        scene_nodes: list[StoryNode] = []
        container_status = StoryItemStatus.COMPLETE
        container_duration = 0.0

        for scene in container_scenes:
            plan = plans.get(scene.scene_id)
            status = scene_status(scene, plan)
            if status is StoryItemStatus.PLANNED:
                planned_scenes += 1
            elif status is StoryItemStatus.READY:
                ready_scenes += 1
            else:
                draft_scenes += 1
            if status is StoryItemStatus.DRAFT:
                container_status = StoryItemStatus.DRAFT
            elif container_status is StoryItemStatus.COMPLETE:
                container_status = status

            referenced_assets.add(scene.location_asset_id)
            referenced_assets.update(scene.participant_asset_ids)
            referenced_assets.update(scene.required_asset_ids)
            scene_duration = scene.estimated_duration_seconds or 0.0
            container_duration += scene_duration
            duration += scene_duration

            shot_nodes: list[StoryNode] = []
            if plan is not None:
                for shot in plan.shots:
                    shot_nodes.append(
                        StoryNode(
                            StoryNodeKind.SHOT,
                            shot.shot_id,
                            shot.description,
                            StoryItemStatus.PLANNED,
                            shot.estimated_duration_seconds,
                            shot_id=shot.shot_id,
                            scene_id=scene.scene_id,
                        )
                    )
                total_shots += len(shot_nodes)

            scene_nodes.append(
                StoryNode(
                    StoryNodeKind.SCENE,
                    scene.scene_id,
                    scene.scene_name or scene.heading,
                    status,
                    scene_duration,
                    1 + len(scene.participant_asset_ids) + len(scene.required_asset_ids),
                    scene_id=scene.scene_id,
                    children=tuple(shot_nodes),
                )
            )

        act = StoryNode(
            StoryNodeKind.ACT,
            f"{container_id}-ACT-001",
            "Act 1",
            container_status,
            container_duration,
            children=tuple(scene_nodes),
        )
        container_type = infer_container_type(container_id)
        container = StoryNode(
            StoryNodeKind.CONTAINER,
            container_id,
            container_id,
            container_status,
            container_duration,
            children=(act,),
        )
        if container_type is ProductionContainerType.EPISODE:
            episodic.append(container)
        else:
            promotional.append(container)

    production_children: list[StoryNode] = []
    if episodic:
        production_children.append(
            StoryNode(
                StoryNodeKind.SEASON,
                "SEASON-001",
                "Season 1",
                _aggregate_status(tuple(episodic)),
                sum(node.duration_seconds for node in episodic),
                children=tuple(episodic),
            )
        )
    if promotional:
        production_children.append(
            StoryNode(
                StoryNodeKind.COLLECTION,
                "PROMOTIONAL-CONTENT",
                "Promotional Content",
                _aggregate_status(tuple(promotional)),
                sum(node.duration_seconds for node in promotional),
                children=tuple(promotional),
            )
        )

    root = StoryNode(
        StoryNodeKind.PRODUCTION,
        "CURRENT-PRODUCTION",
        production_name,
        _aggregate_status(tuple(production_children)),
        duration,
        len(referenced_assets),
        children=tuple(production_children),
    )
    statistics = StoryStatistics(
        containers=len(by_container),
        scenes=len(scenes),
        shots=total_shots,
        planned_scenes=planned_scenes,
        ready_scenes=ready_scenes,
        draft_scenes=draft_scenes,
        duration_seconds=duration,
        referenced_assets=len(referenced_assets),
    )
    return StoryHierarchy((root,), statistics)


def _aggregate_status(nodes: tuple[StoryNode, ...]) -> StoryItemStatus:
    if not nodes:
        return StoryItemStatus.DRAFT
    statuses = {node.status for node in nodes}
    if StoryItemStatus.DRAFT in statuses:
        return StoryItemStatus.DRAFT
    if StoryItemStatus.READY in statuses:
        return StoryItemStatus.READY
    if StoryItemStatus.PLANNED in statuses:
        return StoryItemStatus.PLANNED
    return StoryItemStatus.COMPLETE
