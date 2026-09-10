"""Regression coverage for schedule review-field provenance isolation."""

from __future__ import annotations

from types import SimpleNamespace

from vscs.presentation.widgets.scheduling_review_reset import _patch_workspace_class


class _Editor:
    def __init__(self, value: str) -> None:
        self.value = value

    def clear(self) -> None:
        self.value = ""


class _Scheduling:
    def __init__(self) -> None:
        self.revision = 5

    def latest_schedule(self, _production_id: str) -> SimpleNamespace:
        return SimpleNamespace(revision=self.revision)


class _Workspace:
    def __init__(self) -> None:
        self.production_scheduling = _Scheduling()
        self.scheduling_reviewer = _Editor("Neill Payne")
        self.scheduling_review_notes = _Editor("stale revision 5 notes")

    def _scheduling_production_id(self) -> str:
        return "VSCS TSR2"

    def _scheduling_create_revision(self) -> None:
        self.production_scheduling.revision += 1


def test_new_schedule_revision_clears_previous_review_inputs() -> None:
    _patch_workspace_class(_Workspace)
    workspace = _Workspace()

    workspace._scheduling_create_revision()

    assert workspace.production_scheduling.revision == 6
    assert workspace.scheduling_reviewer.value == ""
    assert workspace.scheduling_review_notes.value == ""
