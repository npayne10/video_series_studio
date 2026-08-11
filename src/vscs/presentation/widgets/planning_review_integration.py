"""Install Phase 19.3.8 Planning Review navigation after Environment Planning."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QPushButton, QVBoxLayout

from vscs.application.story import GovernedPlanningReviewService

from .governed_environment_planner import GovernedEnvironmentPlannerDialog
from .governed_planning_review import GovernedPlanningReviewDialog


def install_planning_review_navigation() -> None:
    """Add the authoritative Planning Review action exactly once."""
    if getattr(GovernedEnvironmentPlannerDialog, "_planning_review_installed", False):
        return

    original_init: Callable[..., None] = GovernedEnvironmentPlannerDialog.__init__
    original_refresh: Callable[[Any], None] = GovernedEnvironmentPlannerDialog.refresh

    def init_with_review(self: Any, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        button = QPushButton("Planning Review…", self)
        button.setObjectName("openGovernedPlanningReview")
        button.setToolTip("Review and approve the complete governed Shot planning package")
        button.clicked.connect(lambda: _open_review(self))
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(max(0, root.count() - 1), button)
        self.planning_review_button = button
        _update_review_action(self)

    def refresh_with_review(self: Any) -> None:
        original_refresh(self)
        _update_review_action(self)

    setattr(GovernedEnvironmentPlannerDialog, "__init__", init_with_review)  # noqa: B010
    setattr(GovernedEnvironmentPlannerDialog, "refresh", refresh_with_review)  # noqa: B010
    setattr(GovernedEnvironmentPlannerDialog, "_planning_review_installed", True)  # noqa: B010


def _review_service(dialog: Any) -> GovernedPlanningReviewService | None:
    service = getattr(dialog.service, "planning_review_service", None)
    return service if isinstance(service, GovernedPlanningReviewService) else None


def _update_review_action(dialog: Any) -> None:
    button = getattr(dialog, "planning_review_button", None)
    if not isinstance(button, QPushButton):
        return
    service = _review_service(dialog)
    environment = dialog.service.plan(dialog.shot_id)
    button.setEnabled(
        service is not None
        and environment is not None
        and dialog.service.is_production_ready(environment)
    )


def _open_review(dialog: Any) -> None:
    service = _review_service(dialog)
    environment = dialog.service.plan(dialog.shot_id)
    shot = dialog.service.shots.plan(dialog.shot_id)
    if (
        service is None
        or shot is None
        or environment is None
        or not dialog.service.is_production_ready(environment)
    ):
        return
    review = GovernedPlanningReviewDialog(service, shot, dialog)
    review.exec()
    dialog.refresh()
