"""Install Phase 19.3.8 Planning Review navigation in the governed Shot Planner."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QPushButton, QVBoxLayout

from vscs.application.story import GovernedPlanningReviewService

from .governed_planning_review import GovernedPlanningReviewDialog
from .governed_shot_planner import GovernedShotPlannerDialog


def install_planning_review_navigation() -> None:
    """Add the authoritative Planning Review action to Shot Planner exactly once."""
    if getattr(GovernedShotPlannerDialog, "_planning_review_installed", False):
        return

    original_init: Callable[..., None] = GovernedShotPlannerDialog.__init__
    original_refresh: Callable[[Any], None] = GovernedShotPlannerDialog.refresh
    original_update_actions: Callable[[Any], None] = GovernedShotPlannerDialog._update_actions

    def init_with_review(self: Any, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        button = QPushButton("Planning Review…", self)
        button.setObjectName("openGovernedPlanningReview")
        button.setToolTip(
            "Review Shot, Asset, Camera, Lighting and Environment planning; blockers remain visible"
        )
        button.clicked.connect(lambda: _open_review(self))
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(max(0, root.count() - 1), button)
        self.planning_review_button = button
        _update_review_action(self)

    def refresh_with_review(self: Any) -> None:
        original_refresh(self)
        _update_review_action(self)

    def update_actions_with_review(self: Any) -> None:
        original_update_actions(self)
        _update_review_action(self)

    setattr(GovernedShotPlannerDialog, "__init__", init_with_review)  # noqa: B010
    setattr(GovernedShotPlannerDialog, "refresh", refresh_with_review)  # noqa: B010
    setattr(GovernedShotPlannerDialog, "_update_actions", update_actions_with_review)  # noqa: B010
    setattr(GovernedShotPlannerDialog, "_planning_review_installed", True)  # noqa: B010


def _review_service(dialog: Any) -> GovernedPlanningReviewService | None:
    service = getattr(dialog.service, "planning_review_service", None)
    return service if isinstance(service, GovernedPlanningReviewService) else None


def _update_review_action(dialog: Any) -> None:
    button = getattr(dialog, "planning_review_button", None)
    if not isinstance(button, QPushButton):
        return
    shot = dialog._selected()
    button.setEnabled(_review_service(dialog) is not None and shot is not None)


def _open_review(dialog: Any) -> None:
    service = _review_service(dialog)
    shot = dialog._selected()
    if service is None or shot is None:
        return
    review = GovernedPlanningReviewDialog(service, shot, dialog)
    review.exec()
    dialog.refresh()
