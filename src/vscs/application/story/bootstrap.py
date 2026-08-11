"""Dependency registration for first-class Story application services."""

from __future__ import annotations

from vscs.application.asset_resolution import AssetBrowserService, AssetResolutionService
from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService
from vscs.infrastructure.services import ApplicationServices

from .approval import StoryApprovalService
from .asset_resolver import GovernedAssetResolutionService
from .camera_planning import GovernedCameraPlanningService
from .environment_planning import GovernedEnvironmentPlanningService
from .episode_planning import EpisodePlanningService
from .iterative_scene_planning import IterativeScenePlanningService
from .lifecycle import StoryLifecycleService
from .lighting_planning import GovernedLightingPlanningService
from .metadata import StoryMetadataService
from .planning_review import GovernedPlanningReviewService
from .service import StoryService
from .shot_planning import GovernedShotPlanningService
from .status import StoryStatusService


def register_story_lifecycle(services: ApplicationServices) -> StoryLifecycleService:
    existing = services.get(StoryLifecycleService)
    if existing is not None:
        return existing
    lifecycle = StoryLifecycleService(services.require(ProjectService))
    return services.register(StoryLifecycleService, lifecycle)


def register_story_metadata(services: ApplicationServices) -> StoryMetadataService:
    existing = services.get(StoryMetadataService)
    if existing is not None:
        return existing
    lifecycle = register_story_lifecycle(services)
    metadata = StoryMetadataService(services.require(ProjectService), lifecycle)
    return services.register(StoryMetadataService, metadata)


def register_story_status(services: ApplicationServices) -> StoryStatusService:
    existing = services.get(StoryStatusService)
    if existing is not None:
        return existing
    lifecycle = register_story_lifecycle(services)
    status = StoryStatusService(services.require(ProjectService), lifecycle)
    return services.register(StoryStatusService, status)


def register_story_approval(services: ApplicationServices) -> StoryApprovalService:
    existing = services.get(StoryApprovalService)
    if existing is not None:
        return existing
    approval = StoryApprovalService(
        services.require(ProjectService),
        register_story_lifecycle(services),
        register_story_metadata(services),
        register_story_status(services),
    )
    return services.register(StoryApprovalService, approval)


def register_episode_planning(services: ApplicationServices) -> EpisodePlanningService:
    existing = services.get(EpisodePlanningService)
    if existing is not None:
        return existing
    planner = EpisodePlanningService(
        services.require(ProjectService),
        register_story_lifecycle(services),
    )
    return services.register(EpisodePlanningService, planner)


def register_scene_planning(services: ApplicationServices) -> IterativeScenePlanningService:
    existing = services.get(IterativeScenePlanningService)
    if existing is not None:
        return existing
    planner = IterativeScenePlanningService(
        services.require(ProjectService),
        register_episode_planning(services),
        services.require(StoryService),
    )
    return services.register(IterativeScenePlanningService, planner)


def register_governed_shot_planning(services: ApplicationServices) -> GovernedShotPlanningService:
    existing = services.get(GovernedShotPlanningService)
    if existing is not None:
        return existing
    planner = GovernedShotPlanningService(
        services.require(ProjectService),
        register_scene_planning(services),
        services.require(ShotPlanningService),
    )
    return services.register(GovernedShotPlanningService, planner)


def register_governed_asset_resolution(services: ApplicationServices) -> GovernedAssetResolutionService:
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


def register_governed_camera_planning(services: ApplicationServices) -> GovernedCameraPlanningService:
    existing = services.get(GovernedCameraPlanningService)
    if existing is not None:
        return existing
    planner = GovernedCameraPlanningService(
        services.require(ProjectService),
        register_governed_shot_planning(services),
        register_governed_asset_resolution(services),
        services.require(AssetResolutionService),
        services.require(AssetBrowserService),
    )
    return services.register(GovernedCameraPlanningService, planner)


def register_governed_lighting_planning(services: ApplicationServices) -> GovernedLightingPlanningService:
    existing = services.get(GovernedLightingPlanningService)
    if existing is not None:
        return existing
    planner = GovernedLightingPlanningService(
        services.require(ProjectService),
        register_governed_shot_planning(services),
        register_governed_asset_resolution(services),
        register_governed_camera_planning(services),
        services.require(AssetResolutionService),
        services.require(AssetBrowserService),
    )
    return services.register(GovernedLightingPlanningService, planner)


def register_governed_environment_planning(
    services: ApplicationServices,
) -> GovernedEnvironmentPlanningService:
    existing = services.get(GovernedEnvironmentPlanningService)
    if existing is not None:
        return existing
    planner = GovernedEnvironmentPlanningService(
        services.require(ProjectService),
        register_scene_planning(services),
        register_governed_shot_planning(services),
        register_governed_asset_resolution(services),
        register_governed_camera_planning(services),
        register_governed_lighting_planning(services),
    )
    return services.register(GovernedEnvironmentPlanningService, planner)


def register_governed_planning_review(
    services: ApplicationServices,
) -> GovernedPlanningReviewService:
    """Register the human review gate over the complete governed Shot plan."""
    existing = services.get(GovernedPlanningReviewService)
    if existing is not None:
        return existing
    review = GovernedPlanningReviewService(
        services.require(ProjectService),
        register_governed_shot_planning(services),
        register_governed_asset_resolution(services),
        register_governed_camera_planning(services),
        register_governed_lighting_planning(services),
        register_governed_environment_planning(services),
    )
    return services.register(GovernedPlanningReviewService, review)
