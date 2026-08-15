from vscs.application.automation import ProposalReviewGapDetectionService
from vscs.bootstrap import build_application_context


def test_review_gap_service_is_registered(application_options) -> None:
    with build_application_context(application_options) as application:
        assert application.services.get(ProposalReviewGapDetectionService) is not None


def test_story_workspace_exposes_review_gaps(application_options, qtbot) -> None:
    with build_application_context(application_options) as application:
        window = application.main_window
        qtbot.addWidget(window)
        assert window.story_browser.review_gaps_button.objectName() == "reviewAutomationGaps"
