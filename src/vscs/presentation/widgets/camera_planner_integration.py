"""Install Phase 19.3.5 Camera Planner navigation into governed Shot Planner."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import Any

from PySide6.QtWidgets import QPushButton, QVBoxLayout

from vscs.application.story import GovernedCameraPlanningService

from .governed_camera_planner import GovernedCameraPlannerDialog
from .governed_shot_planner import GovernedShotPlannerDialog


def install_camera_planner_navigation() -> None:
    """Add the authoritative Camera Planner action exactly once."""
    if getattr(GovernedShotPlannerDialog, "_camera_planner_installed", False):
        return

    original_init: Callable[..., None] = GovernedShotPlannerDialog.__init__
    original_update_actions: Callable[[Any], None] = GovernedShotPlannerDialog._update_actions

    def init_with_camera_planner(self: Any, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        button = QPushButton("Camera Planner…", self)
        button.setObjectName("openGovernedCameraPlanner")
        button.setToolTip("Plan governed camera intent for the selected current Ready Shot")
        button.clicked.connect(lambda: _open_camera_planner(self))
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(max(0, root.count() - 1), button)
        self.camera_planner_button = button
        with suppress(RuntimeError, TypeError):
            self.table.itemSelectionChanged.connect(lambda: _update_camera_action(self))
        _update_camera_action(self)

    def update_actions_with_camera(self: Any) -> None:
        original_update_actions(self)
        _update_camera_action(self)

    setattr(GovernedShotPlannerDialog, "__init__", init_with_camera_planner)  # noqa: B010
    setattr(GovernedShotPlannerDialog, "_update_actions", update_actions_with_camera)  # noqa: B010
    setattr(GovernedShotPlannerDialog, "_camera_planner_installed", True)  # noqa: B010


def _camera_service(dialog: Any) -> GovernedCameraPlanningService | None:
    service = getattr(dialog.service, "camera_planning_service", None)
    return service if isinstance(service, GovernedCameraPlanningService) else None


def _update_camera_action(dialog: Any) -> None:
    button = getattr(dialog, "camera_planner_button", None)
    if not isinstance(button, QPushButton):
        return
    shot = dialog._selected()
    service = _camera_service(dialog)
    button.setEnabled(
        service is not None and shot is not None and dialog.service.is_production_ready(shot)
    )


def _open_camera_planner(dialog: Any) -> None:
    shot = dialog._selected()
    service = _camera_service(dialog)
    if shot is None or service is None or not dialog.service.is_production_ready(shot):
        return
    planner = GovernedCameraPlannerDialog(service, shot, dialog)
    planner.exec()
    dialog.refresh()
