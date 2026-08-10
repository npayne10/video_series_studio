"""Dependency registration for first-class Story application services."""

from __future__ import annotations

from vscs.application.asset_resolution import AssetBrowserService, AssetResolutionService
from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService
from vscs.infrastructure.services import ApplicationServices

from .approval import StoryApprovalService
from .asset_resolver import GovernedAssetResolutionService
from .episode_planning import EpisodePlanningService
from .iterative_scene_planning import IterativeScenePlanningService
from .lifecycle import StoryLifecycleService
from .metadata import StoryMetadataService
from .service import StoryService
from .shot_planning import GovernedShotPlanningService
from .status import StoryStatusService


def register_story_lifecycle(services: ApplicationServices) -> StoryLifecycleService:
    """Register the shared project-backed Story lifecycle service."""
    existing = services.get(StoryLifecycleService)
    if existing is not None:
        return existing
    lifecycle = StoryLifecycleService(services.require(ProjectService))
    return services.register(StoryLifecycleService, lifecycle)


def register_story_metadata(services: ApplicationServices) -> StoryMetadataService:
    """Register Story metadata using the shared lifecycle dependency."""
    existing = services.get(StoryMetadataService)
    if existing is not None:
        return existing
    lifecycle = register_story_lifecycle(services)
    metadata = StoryMetadataService(
        services.require(ProjectService),
        lifecycle,
    )
    return services.register(StoryMetadataService, metadata)


def register_story_status(services: ApplicationServices) -> StoryStatusService:
    """Register Story status using the shared lifecycle dependency."""
    existing = services.get(StoryStatusService)
    if existing is not None:
        return existing
    lifecycle = register_story_lifecycle(services)
    status = StoryStatusService(
        services.require(ProjectService),
        lifecycle,
    )
    return services.register(StoryStatusService, status)


def register_story_approval(services: ApplicationServices) -> StoryApprovalService:
    """Register approval governance using shared Story services."""
    existing = services.get(StoryApprovalService)
    if existing is not None:
        return existing
    lifecycle = register_story_lifecycle(services)
    metadata = register_story_metadata(services)
    status = register_story_status(services)
    approval = StoryApprovalService(
        services.require(ProjectService),
        lifecycle,
        metadata,
        status,
    )
    return services.register(StoryApprovalService, approval)


def register_episode_planning(services: ApplicationServices) -> EpisodePlanningService:
    """Register the project-backed Episode Planner service."""
    existing = services.get(EpisodePlanningService)
    if existing is not None:
        return existing
    planner = EpisodePlanningService(
        services.require(ProjectService),
        register_story_lifecycle(services),
    )
    return services.register(EpisodePlanningService, planner)


def register_scene_planning(services: ApplicationServices) -> IterativeScenePlanningService:
    """Register iterative Scene Planning beneath authoritative Episode Planning."""
    existing = services.get(IterativeScenePlanningService)
    if existing is not None:
        return existing
    planner = IterativeScenePlanningService(
        services.require(ProjectService),
        register_episode_planning(services),
        services.require(StoryService),
    )
    return services.register(IterativeScenePlanningService, planner)


def register_governed_shot_planning(
    services: ApplicationServices,
) -> GovernedShotPlanningService:
    """Register authoritative Shot Planning beneath governed Scene Planning."""
    existing = services.get(GovernedShotPlanningService)
    if existing is not None:
        return existing
    planner = GovernedShotPlanningService(
        services.require(ProjectService),
        register_scene_planning(services),
        services.require(ShotPlanningService),
    )
    return services.register(GovernedShotPlanningService, planner)


def register_governed_asset_resolution(
    services: ApplicationServices,
) -> GovernedAssetResolutionService:
    """Register authoritative asset binding beneath governed Shot Planning."""
    existing = services.get(GovernedAssetResolutionService)
    if existing is not None:
        return existing
    resolver = GovernedAssetResolutionService(
        services.require(ProjectService),
        register_governed_shot_planning(services),
        services.require(AssetResolutionService),
        services.require(AssetBrowserService),
    )
    return services.register(GovernedAssetResolutionService, resolver)
