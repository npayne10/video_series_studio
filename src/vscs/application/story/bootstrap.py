"""Dependency registration for first-class Story application services."""

from __future__ import annotations

from vscs.application.projects import ProjectService
from vscs.infrastructure.services import ApplicationServices

from .approval import StoryApprovalService
from .lifecycle import StoryLifecycleService
from .metadata import StoryMetadataService
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
