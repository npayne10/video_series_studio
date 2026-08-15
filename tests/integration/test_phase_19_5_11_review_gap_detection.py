from pathlib import Path

from vscs.application.automation import ProposalReviewGapDetectionService
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


def test_review_gap_service_is_registered(tmp_path: Path) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        window.close()
        assert application.services.get(ProposalReviewGapDetectionService) is not None


def test_story_workspace_exposes_review_gaps(tmp_path: Path, qtbot) -> None:
    with build_application_context(_options(tmp_path)) as application:
        application.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
        window = application.create_main_window()
        qtbot.addWidget(window)
        assert window.story_browser.review_gaps_button.objectName() == "reviewAutomationGaps"
