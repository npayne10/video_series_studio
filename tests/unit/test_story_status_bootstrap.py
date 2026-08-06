"""Bootstrap coverage for Phase 18.1.4 Story status services."""

from __future__ import annotations

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryLifecycleService,
    StoryStatusService,
    register_story_lifecycle,
    register_story_status,
)
from vscs.infrastructure.services import ApplicationServices


def test_register_story_status_reuses_shared_lifecycle() -> None:
    services = ApplicationServices()
    projects = ProjectService.__new__(ProjectService)
    services.register(ProjectService, projects)

    lifecycle = register_story_lifecycle(services)
    status = register_story_status(services)

    assert services.require(StoryLifecycleService) is lifecycle
    assert services.require(StoryStatusService) is status
    assert status.projects is projects
    assert status.stories is lifecycle
    assert register_story_status(services) is status
