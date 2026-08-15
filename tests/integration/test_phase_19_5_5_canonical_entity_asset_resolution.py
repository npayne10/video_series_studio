from __future__ import annotations

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.automation import (
    AutomationProposalService,
    AutomationProposalType,
    CanonicalEntityAssetResolutionAutomationService,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.story_analysis import (
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
)


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_canonical_entity_asset_automation_is_registered_with_story_workspace(
    tmp_path: Path,
    qtbot,
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        service = application.services.get(CanonicalEntityAssetResolutionAutomationService)
        workspace = window.story_browser

        assert isinstance(service, CanonicalEntityAssetResolutionAutomationService)
        # Phase 19.5.12A relocates these actions into hierarchical navigation.
        assert workspace.resolve_assets_button.isHidden()
        assert workspace.resolve_assets_button.text() == "Resolve Assets…"
        assert workspace.review_proposals_button.isHidden()


def test_new_story_entities_remain_proposals_and_do_not_create_assets(
    tmp_path: Path,
    qtbot,
) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        assets = application.services.require(AssetService)
        before = assets.list()
        service = application.services.require(CanonicalEntityAssetResolutionAutomationService)
        resolution = EntityResolutionResult(
            story_id="STORY-001",
            source_revision="rev-1",
            candidates=(
                EntityCandidate(
                    candidate_id="candidate:location:listening-post-17",
                    name="Listening Post 17",
                    category=EntityResolutionCategory.LOCATION,
                    description="Abandoned Guild listening station.",
                    confidence=0.95,
                    match_kind=ResolutionMatchKind.NEW,
                ),
            ),
        )

        generated = service.generate(
            story_id="STORY-001",
            source_revision="rev-1",
            entity_resolution=resolution,
        )

        assert len(generated) == 1
        assert generated[0].proposal_type is AutomationProposalType.ASSET
        assert generated[0].payload["canonical_status"] == "new_asset_required"
        assert assets.list() == before
        stored = application.services.require(AutomationProposalService).list_proposals()
        assert any(item.proposal_type is AutomationProposalType.ASSET for item in stored)
