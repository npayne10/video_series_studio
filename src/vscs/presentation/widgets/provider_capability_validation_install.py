"""Install the Phase 20.17 provider capability-validation workspace."""

from __future__ import annotations

from typing import Any

from vscs.application.provider_capability_validation import (
    ProviderCapabilityValidationService,
)
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository
from vscs.infrastructure.provider_capability_validation import (
    JsonCapabilityValidationRepository,
    wan22_video_validation_pack,
)
from vscs.presentation.widgets.provider_capability_validation_workspace import (
    ProviderCapabilityValidationWorkspace,
)


def install_provider_capability_validation_workspace(window: Any) -> None:
    """Compose the provider-neutral validation workspace into the desktop shell."""

    def service_provider() -> ProviderCapabilityValidationService | None:
        project_directory = window.projects.project_directory
        if project_directory is None:
            return None
        root = project_directory / ".vscs"
        return ProviderCapabilityValidationService(
            JsonCapabilityValidationRepository(root / "provider_capability_validation"),
            JsonGeneratedMediaRepository(root / "generated_media"),
            (wan22_video_validation_pack(),),
        )

    workspace = ProviderCapabilityValidationWorkspace(service_provider)
    post_production_index = window.navigation.count() - 1
    window.navigation.insertItem(post_production_index, "Provider Validation")
    window.content_stack.insertWidget(post_production_index, workspace)

    def refresh_for_section(section: str) -> None:
        if section == "Provider Validation":
            workspace.refresh()

    window.navigation.currentTextChanged.connect(refresh_for_section)
    window.new_project_action.triggered.connect(workspace.refresh)
    window.open_project_action.triggered.connect(workspace.refresh)
    window.close_project_action.triggered.connect(workspace.refresh)
    workspace.refresh()
