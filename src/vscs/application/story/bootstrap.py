"""Dependency registration for first-class story lifecycle services."""

from __future__ import annotations

from vscs.application.projects import ProjectService
from vscs.infrastructure.services import ApplicationServices

from .lifecycle import StoryLifecycleService


def register_story_lifecycle(services: ApplicationServices) -> StoryLifecycleService:
    """Register the shared project-backed Story lifecycle service."""
    existing = services.get(StoryLifecycleService)
    if existing is not None:
        return existing
    lifecycle = StoryLifecycleService(services.require(ProjectService))
    return services.register(StoryLifecycleService, lifecycle)
