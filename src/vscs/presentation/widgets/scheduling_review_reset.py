"""Prevent review provenance from leaking between schedule revisions."""

from __future__ import annotations

from typing import Any


def _patch_workspace_class(workspace_class: type[Any]) -> None:
    """Clear reviewer inputs whenever a genuinely new schedule revision is created."""
    if getattr(workspace_class, "_scheduling_review_reset_installed", False):
        return
    original_create_revision = getattr(workspace_class, "_scheduling_create_revision", None)
    if original_create_revision is None:
        return

    def create_revision_with_fresh_review(self: Any) -> None:
        production_id = self._scheduling_production_id()
        before = self.production_scheduling.latest_schedule(production_id)
        original_create_revision(self)
        after = self.production_scheduling.latest_schedule(production_id)
        if after is None:
            return
        if before is not None and after.revision == before.revision:
            return
        self.scheduling_reviewer.clear()
        self.scheduling_review_notes.clear()

    workspace_class._scheduling_create_revision = create_revision_with_fresh_review
    workspace_class._scheduling_review_reset_installed = True


def install_scheduling_review_reset() -> None:
    """Install the review-field reset after Scheduling, regardless of import order."""
    from vscs.presentation.widgets import production_scheduling_workspace as scheduling_module
    from vscs.presentation.widgets.production_package_workspace import ProductionPackageWorkspace

    _patch_workspace_class(ProductionPackageWorkspace)

    original_install = scheduling_module.install_production_scheduling_workspace
    if getattr(original_install, "_scheduling_review_reset_wrapper", False):
        return

    def wrapped_install(workspace_class: type[Any]) -> None:
        original_install(workspace_class)
        _patch_workspace_class(workspace_class)

    wrapped_install._scheduling_review_reset_wrapper = True  # type: ignore[attr-defined]
    scheduling_module.install_production_scheduling_workspace = wrapped_install
