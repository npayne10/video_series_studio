from __future__ import annotations

from pathlib import Path

from vscs.application.automation import EpisodeSceneProposalAutomationService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_episode_scene_automation_is_registered_with_story_workspace(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)

        service = application.services.get(EpisodeSceneProposalAutomationService)

        assert isinstance(service, EpisodeSceneProposalAutomationService)
