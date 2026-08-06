"""Bootstrap coverage for the Phase 18.1.3 Story metadata service."""

from __future__ import annotations

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryLifecycleService,
    StoryMetadataService,
    register_story_lifecycle,
    register_story_metadata,
)
from vscs.infrastructure.services import ApplicationServices


def test_register_story_metadata_reuses_shared_dependencies() -> None:
    services = ApplicationServices()
    projects = ProjectService.__new__(ProjectService)
    services.register(ProjectService, projects)

    lifecycle = register_story_lifecycle(services)
    metadata = register_story_metadata(services)

    assert services.require(StoryLifecycleService) is lifecycle
    assert services.require(StoryMetadataService) is metadata
    assert metadata.projects is projects
    assert metadata.stories is lifecycle
    assert register_story_metadata(services) is metadata
