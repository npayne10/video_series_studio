"""Synchronize existing Asset image references when CAP views refresh."""

from __future__ import annotations

from typing import Any

from vscs.application.caps.asset_reference_bridge import ensure_asset_image_reference
from vscs.presentation.widgets import cap_manager


def install_cap_asset_reference_sync() -> None:
    if getattr(cap_manager.CAPManagerWidget, "_asset_reference_sync_installed", False):
        return

    original_refresh = cap_manager.CAPManagerWidget.refresh

    def refresh(widget: Any) -> None:
        references = widget.references
        if references is not None:
            for profile in widget.caps.list():
                ensure_asset_image_reference(references, profile.asset_id)
        original_refresh(widget)

    widget_type: Any = cap_manager.CAPManagerWidget
    widget_type.refresh = refresh
    widget_type._asset_reference_sync_installed = True
