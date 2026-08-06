"""Dependency registration for first-class Story application services."""

from __future__ import annotations

from vscs.application.projects import ProjectService
from vscs.infrastructure.services import ApplicationServices

from .lifecycle import StoryLifecycleService
from .metadata import StoryMetadataService


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
