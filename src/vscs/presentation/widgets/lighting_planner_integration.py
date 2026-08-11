"""Install Phase 19.3.6 Lighting Planner navigation into governed Camera Planner."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QPushButton, QVBoxLayout

from vscs.application.story import GovernedLightingPlanningService

from .governed_camera_planner import GovernedCameraPlannerDialog
from .governed_lighting_planner import GovernedLightingPlannerDialog


def install_lighting_planner_navigation() -> None:
    """Add the authoritative Lighting Planner action exactly once."""
    if getattr(GovernedCameraPlannerDialog, "_lighting_planner_installed", False):
        return

    original_init: Callable[..., None] = GovernedCameraPlannerDialog.__init__
    original_refresh: Callable[[Any], None] = GovernedCameraPlannerDialog.refresh

    def init_with_lighting_planner(self: Any, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        button = QPushButton("Lighting Planner…", self)
        button.setObjectName("openGovernedLightingPlanner")
        button.setToolTip("Plan governed lighting intent for the current Ready Camera Plan")
        button.clicked.connect(lambda: _open_lighting_planner(self))
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(max(0, root.count() - 1), button)
        self.lighting_planner_button = button
        _update_lighting_action(self)

    def refresh_with_lighting(self: Any) -> None:
        original_refresh(self)
        _update_lighting_action(self)

    setattr(GovernedCameraPlannerDialog, "__init__", init_with_lighting_planner)  # noqa: B010
    setattr(GovernedCameraPlannerDialog, "refresh", refresh_with_lighting)  # noqa: B010
    setattr(GovernedCameraPlannerDialog, "_lighting_planner_installed", True)  # noqa: B010


def _lighting_service(dialog: Any) -> GovernedLightingPlanningService | None:
    service = getattr(dialog.service, "lighting_planning_service", None)
    return service if isinstance(service, GovernedLightingPlanningService) else None


def _update_lighting_action(dialog: Any) -> None:
    button = getattr(dialog, "lighting_planner_button", None)
    if not isinstance(button, QPushButton):
        return
    service = _lighting_service(dialog)
    camera_plan = dialog.service.plan(dialog.shot_id)
    button.setEnabled(
        service is not None
        and camera_plan is not None
        and dialog.service.is_production_ready(camera_plan)
    )


def _open_lighting_planner(dialog: Any) -> None:
    service = _lighting_service(dialog)
    camera_plan = dialog.service.plan(dialog.shot_id)
    shot = dialog.service.shots.plan(dialog.shot_id)
    if (
        service is None
        or shot is None
        or camera_plan is None
        or not dialog.service.is_production_ready(camera_plan)
    ):
        return
    planner = GovernedLightingPlannerDialog(service, shot, dialog)
    planner.exec()
    dialog.refresh()
