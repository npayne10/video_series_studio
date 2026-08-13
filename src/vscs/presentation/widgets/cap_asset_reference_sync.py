"""Synchronize existing Asset image references when CAP views refresh."""

from __future__ import annotations

from typing import Any

from vscs.application.caps.asset_reference_bridge import ensure_asset_image_reference
from vscs.application.caps.reference_library import (
    ReferenceLibraryConflictError,
    ReferenceLibraryNotFoundError,
    ReferenceLibraryService,
)
from vscs.domain.caps.production_contract import CanonicalReferenceLifecycle
from vscs.presentation.widgets import cap_manager


def install_cap_asset_reference_sync() -> None:
    if getattr(cap_manager.CAPManagerWidget, "_asset_reference_sync_installed", False):
        return

    original_refresh = cap_manager.CAPManagerWidget.refresh

    def refresh(widget: Any) -> None:
        references = widget.references
        if references is not None:
            library = ReferenceLibraryService(references)
            for profile in widget.caps.list():
                reference = ensure_asset_image_reference(references, profile.asset_id)
                if reference is None:
                    continue
                try:
                    entry = library.get(reference.id)
                except ReferenceLibraryNotFoundError:
                    try:
                        entry = library.register_master(
                            profile.asset_id,
                            reference.id,
                            actor="VSCS Asset Reference Bridge",
                            note="Asset canonical MASTER synchronized into CAP production library.",
                        )
                    except ReferenceLibraryConflictError:
                        continue
                if entry.lifecycle is CanonicalReferenceLifecycle.CANDIDATE:
                    library.approve(
                        reference.id,
                        "VSCS Asset Reference Bridge",
                        note="Asset canonical MASTER published for downstream production use.",
                    )
        original_refresh(widget)

    widget_type: Any = cap_manager.CAPManagerWidget
    widget_type.refresh = refresh
    widget_type._asset_reference_sync_installed = True
