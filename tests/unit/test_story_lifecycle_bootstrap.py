"""Bootstrap helper coverage for the Phase 18.1.2 Story lifecycle."""

from __future__ import annotations

from unittest.mock import Mock

from vscs.application.projects import ProjectService
from vscs.application.story import StoryLifecycleService, register_story_lifecycle
from vscs.infrastructure.services import ApplicationServices


def test_register_story_lifecycle_uses_shared_project_service() -> None:
    services = ApplicationServices()
    projects = Mock(spec=ProjectService)
    services.register(ProjectService, projects)

    lifecycle = register_story_lifecycle(services)

    assert services.require(StoryLifecycleService) is lifecycle
    assert lifecycle.projects is projects
    assert register_story_lifecycle(services) is lifecycle
