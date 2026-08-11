"""Install Phase 19.3.7 Environment Planner navigation into governed Lighting Planner."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QPushButton, QVBoxLayout

from vscs.application.story import GovernedEnvironmentPlanningService

from .governed_environment_planner import GovernedEnvironmentPlannerDialog
from .governed_lighting_planner import GovernedLightingPlannerDialog


def install_environment_planner_navigation() -> None:
    """Add the authoritative Environment Planner action exactly once."""
    if getattr(GovernedLightingPlannerDialog, "_environment_planner_installed", False):
        return

    original_init: Callable[..., None] = GovernedLightingPlannerDialog.__init__
    original_refresh: Callable[[Any], None] = GovernedLightingPlannerDialog.refresh

    def init_with_environment_planner(self: Any, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        button = QPushButton("Environment Planner…", self)
        button.setObjectName("openGovernedEnvironmentPlanner")
        button.setToolTip(
            "Plan governed physical environment state for the current Ready Lighting Plan"
        )
        button.clicked.connect(lambda: _open_environment_planner(self))
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(max(0, root.count() - 1), button)
        self.environment_planner_button = button
        _update_environment_action(self)

    def refresh_with_environment(self: Any) -> None:
        original_refresh(self)
        _update_environment_action(self)

    setattr(GovernedLightingPlannerDialog, "__init__", init_with_environment_planner)  # noqa: B010
    setattr(GovernedLightingPlannerDialog, "refresh", refresh_with_environment)  # noqa: B010
    setattr(GovernedLightingPlannerDialog, "_environment_planner_installed", True)  # noqa: B010


def _environment_service(dialog: Any) -> GovernedEnvironmentPlanningService | None:
    service = getattr(dialog.service, "environment_planning_service", None)
    return service if isinstance(service, GovernedEnvironmentPlanningService) else None


def _update_environment_action(dialog: Any) -> None:
    button = getattr(dialog, "environment_planner_button", None)
    if not isinstance(button, QPushButton):
        return
    service = _environment_service(dialog)
    lighting_plan = dialog.service.plan(dialog.shot_id)
    button.setEnabled(
        service is not None
        and lighting_plan is not None
        and dialog.service.is_production_ready(lighting_plan)
    )


def _open_environment_planner(dialog: Any) -> None:
    service = _environment_service(dialog)
    lighting_plan = dialog.service.plan(dialog.shot_id)
    shot = dialog.service.shots.plan(dialog.shot_id)
    if (
        service is None
        or shot is None
        or lighting_plan is None
        or not dialog.service.is_production_ready(lighting_plan)
    ):
        return
    planner = GovernedEnvironmentPlannerDialog(service, shot, dialog)
    planner.exec()
    dialog.refresh()
