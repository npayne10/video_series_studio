"""Install Phase 19.3.4 Asset Resolver navigation into the governed Shot Planner."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from PySide6.QtWidgets import QPushButton, QVBoxLayout

from vscs.application.story import GovernedAssetResolutionService

from .governed_asset_resolver import GovernedAssetResolverDialog
from .governed_shot_planner import GovernedShotPlannerDialog


def install_asset_resolver_navigation() -> None:
    """Add one authoritative Asset Resolver action to governed Shot Planner dialogs."""
    if getattr(GovernedShotPlannerDialog, "_asset_resolver_installed", False):
        return

    original_init = GovernedShotPlannerDialog.__init__
    original_update_actions = GovernedShotPlannerDialog._update_actions

    def init_with_asset_resolver(self: Any, *args: object, **kwargs: object) -> None:
        original_init(self, *args, **kwargs)
        button = QPushButton("Asset Resolver…", self)
        button.setObjectName("openGovernedAssetResolver")
        button.setToolTip(
            "Resolve approved project assets for the selected current Ready governed Shot"
        )
        button.clicked.connect(lambda: _open_asset_resolver(self))
        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertWidget(max(0, root.count() - 1), button)
        self.asset_resolver_button = button
        with suppress(RuntimeError, TypeError):
            self.table.itemSelectionChanged.connect(lambda: _update_asset_action(self))
        _update_asset_action(self)

    def update_actions_with_assets(self: Any) -> None:
        original_update_actions(self)
        _update_asset_action(self)

    setattr(GovernedShotPlannerDialog, "__init__", init_with_asset_resolver)
    setattr(GovernedShotPlannerDialog, "_update_actions", update_actions_with_assets)
    setattr(GovernedShotPlannerDialog, "_asset_resolver_installed", True)


def _asset_service(dialog: Any) -> GovernedAssetResolutionService | None:
    service = getattr(dialog.service, "asset_resolution_service", None)
    return service if isinstance(service, GovernedAssetResolutionService) else None


def _update_asset_action(dialog: Any) -> None:
    button = getattr(dialog, "asset_resolver_button", None)
    if not isinstance(button, QPushButton):
        return
    shot = dialog._selected()
    service = _asset_service(dialog)
    button.setEnabled(
        service is not None
        and shot is not None
        and dialog.service.is_production_ready(shot)
    )


def _open_asset_resolver(dialog: Any) -> None:
    shot = dialog._selected()
    service = _asset_service(dialog)
    if shot is None or service is None or not dialog.service.is_production_ready(shot):
        return
    resolver = GovernedAssetResolverDialog(service, shot, dialog)
    resolver.exec()
    dialog.refresh()
