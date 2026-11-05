"""Shared Story proposal progress must be responsive, truthful and single-flight."""

from threading import Event, get_ident
from time import perf_counter

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

from vscs.presentation.widgets.automation_progress import (
    AutomationOperationError,
    AutomationProgressRunner,
)


def test_progress_modal_is_visible_and_worker_is_off_gui_thread(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    runner = AutomationProgressRunner(host)
    gate = Event()
    started = Event()
    seen = []
    ui_thread = get_ident()
    calls = []

    def operation():
        calls.append(get_ident())
        started.set()
        assert gate.wait(8), "The Qt event loop failed to release the worker"
        return ("EP-001", "EP-001-SCN-001")

    deadline = perf_counter() + 5
    timer = QTimer(host)
    timer.setInterval(10)

    def inspect():
        active = QApplication.activeModalWidget()
        if (
            started.is_set()
            and active is not None
            and active.objectName() == "automationOperationProgress"
            and active.findChild(QWidget, "automationIndeterminateProgress") is not None
        ):
            seen.append(active.windowTitle())
            assert runner.active
            timer.stop()
            gate.set()
        elif perf_counter() > deadline:
            seen.append("timed out")
            timer.stop()
            gate.set()

    timer.timeout.connect(inspect)
    timer.start()
    assert runner.run("Planning Proposals", "STORY-001", operation) == (
        "EP-001",
        "EP-001-SCN-001",
    )
    assert seen == ["Planning Proposals — Running"]
    assert calls and calls[0] != ui_thread
    assert not runner.active


def test_provider_error_surfaces_without_success(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    runner = AutomationProgressRunner(host)

    def failing():
        raise ValueError("Controlled Shot provider failure")

    with pytest.raises(AutomationOperationError, match="Controlled Shot provider failure"):
        runner.run("Shot Proposals", "STORY-001", failing)
    assert not runner.active


def test_fast_result_closes_progress_without_hanging(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    runner = AutomationProgressRunner(host)
    assert runner.run("Shot Proposals", "STORY-001", lambda: ("SHT-001",)) == ("SHT-001",)
    assert not runner.active


def test_running_operation_rejects_duplicate_without_second_call(qtbot):
    host = QWidget()
    qtbot.addWidget(host)
    runner = AutomationProgressRunner(host)
    gate = Event()
    calls = []
    blocked = []

    def operation():
        calls.append("original")
        assert gate.wait(8)
        return "done"

    def try_duplicate():
        try:
            runner.run("Shot Proposals", "STORY-001", lambda: calls.append("duplicate"))
        except AutomationOperationError as exc:
            blocked.append(str(exc))
        gate.set()

    QTimer.singleShot(50, try_duplicate)
    assert runner.run("Shot Proposals", "STORY-001", operation) == "done"
    assert calls == ["original"]
    assert len(blocked) == 1
    assert not runner.active


def test_cap_provider_work_uses_shared_progress_off_gui_thread(qtbot):
    """B.5.24: the only background work is an immutable asset snapshot and provider."""
    from types import SimpleNamespace

    from vscs.application.caps.story_specification import StoryCAPSpecificationService
    from vscs.domain.assets.models import AssetCategory
    from vscs.domain.caps.generation import GeneratedCAPDraft

    host = QWidget()
    qtbot.addWidget(host)
    runner = AutomationProgressRunner(host)
    started = Event()
    release = Event()
    seen = []
    gui_thread = get_ident()

    class Provider:
        def generate_cap(self, request):
            seen.append((get_ident(), request.asset_id, request.story_context))
            started.set()
            assert release.wait(8)
            return GeneratedCAPDraft(
                title="Engineering room",
                canonical_description="An empty engineering control room.",
                visual_identity="An empty engineering control room contains a console.",
            )

    asset = SimpleNamespace(
        asset_id="STORY-LOC-001",
        name="Engineering room",
        category=AssetCategory.LOCATION,
        description="A fixed location.",
    )
    QTimer.singleShot(100, release.set)
    proposal = runner.run(
        "CAP Proposal Generation",
        "STORY-001",
        lambda: StoryCAPSpecificationService.generate_from_snapshot(
            asset, "An empty engineering control room.", Provider()
        ),
    )
    assert started.is_set()
    assert len(seen) == 1
    assert seen[0][1:] == ("STORY-LOC-001", "An empty engineering control room.")
    assert seen[0][0] != gui_thread
    assert proposal.specification.asset_id == "STORY-LOC-001"
    assert proposal.specification.origin == "story_intelligence_proposal"
    assert not runner.active


def test_cap_provider_failure_resets_shared_progress(qtbot):
    """B.5.24: failed paid call must not display a success result or create a CAP."""
    from types import SimpleNamespace

    from vscs.application.caps.story_specification import StoryCAPSpecificationService
    from vscs.domain.assets.models import AssetCategory

    host = QWidget()
    qtbot.addWidget(host)
    runner = AutomationProgressRunner(host)

    class FailingProvider:
        def generate_cap(self, _request):
            raise RuntimeError("Injected Terra API failure")

    asset = SimpleNamespace(
        asset_id="STORY-LOC-001",
        name="Engineering room",
        category=AssetCategory.LOCATION,
        description="",
    )
    with pytest.raises(AutomationOperationError, match="Injected Terra API failure"):
        runner.run(
            "CAP Proposal Generation",
            "STORY-001",
            lambda: StoryCAPSpecificationService.generate_from_snapshot(
                asset, "Approved source.", FailingProvider()
            ),
        )
    assert not runner.active


def test_cap_paid_confirmation_controls_exactly_one_call(monkeypatch):
    """B.5.24: declining consent never invokes paid generation."""
    from types import SimpleNamespace

    from PySide6.QtWidgets import QMessageBox

    from vscs.presentation.dialogs import story_cap_batch_dialog
    from vscs.presentation.dialogs.story_cap_batch_dialog import StoryCAPBatchDialog

    calls = []
    host = SimpleNamespace(
        generator=SimpleNamespace(provider=SimpleNamespace(_model="gpt-6.1-terra")),
        review_one=lambda **kw: calls.append(kw),
    )
    monkeypatch.setattr(
        story_cap_batch_dialog.QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.No,
    )
    StoryCAPBatchDialog.regenerate_one(host)
    assert calls == []
    monkeypatch.setattr(
        story_cap_batch_dialog.QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    StoryCAPBatchDialog.regenerate_one(host)
    assert calls == [{"force_regenerate": True}]


def test_cap_design_expansion_runs_under_same_progress(qtbot):
    """B.5.24: secondary paid design-expansion call is also off the UI thread."""
    from types import SimpleNamespace

    from vscs.application.caps.provider_design_expansion import (
        DesignExpansionResponse,
        ProposedDesignField,
    )
    from vscs.application.caps.story_specification import StoryCAPSpecificationService
    from vscs.domain.assets.models import AssetCategory
    from vscs.domain.caps.generation import GeneratedCAPDraft

    host = QWidget()
    qtbot.addWidget(host)
    calls = []
    gui_thread = get_ident()

    class Provider:
        def generate_cap(self, _request):
            calls.append(("generate", get_ident()))
            return GeneratedCAPDraft(
                title="Engineering control room",
                canonical_description="A fixed interior.",
                visual_identity="The engineering control room contains a diagnostic console beside the workstation.",
            )

        def expand_cap_design(self, _spec, _story_context):
            calls.append(("expand", get_ident()))
            return DesignExpansionResponse(
                fields=(
                    ProposedDesignField(
                        field="layout",
                        proposed_value="Proposed room layout.",
                        rationale="For repeatable continuity.",
                    ),
                )
            )

    asset = SimpleNamespace(
        asset_id="STORY-LOC-001",
        name="Engineering control room",
        category=AssetCategory.LOCATION,
        description="",
    )
    proposal = AutomationProgressRunner(host).run(
        "CAP Proposal Generation",
        "STORY-001",
        lambda: StoryCAPSpecificationService.generate_from_snapshot(
            asset, "An engineering control room contains a console.", Provider()
        ),
    )
    assert [stage for stage, _thread in calls] == ["generate", "expand"]
    assert all(thread != gui_thread for _stage, thread in calls)
    assert proposal.design_suggestions
    assert proposal.design_suggestions[0].field == "layout"
