"""Bootstrap coverage for Phase 18.1.5 Story approval governance."""

from __future__ import annotations

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryApprovalService,
    StoryLifecycleService,
    StoryMetadataService,
    StoryStatusService,
    register_story_approval,
)
from vscs.infrastructure.services import ApplicationServices


def test_register_story_approval_reuses_shared_dependencies() -> None:
    services = ApplicationServices()
    projects = ProjectService.__new__(ProjectService)
    services.register(ProjectService, projects)

    approval = register_story_approval(services)

    assert services.require(StoryLifecycleService) is approval.stories
    assert services.require(StoryMetadataService) is approval.metadata
    assert services.require(StoryStatusService) is approval.statuses
    assert services.require(StoryApprovalService) is approval
    assert approval.projects is projects
    assert register_story_approval(services) is approval
