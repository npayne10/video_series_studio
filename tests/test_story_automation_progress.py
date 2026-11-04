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
