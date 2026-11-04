"""Shared non-cancellable progress surface for provider-backed Story proposal tasks.

The caller must ensure the submitted operation does not use Qt widgets or a
thread-bound database connection. A modal dialog protects the active project
from normal operator navigation while the proposal call runs.
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Generic, TypeVar, cast

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import QDialog, QProgressBar, QVBoxLayout, QLabel, QWidget

ResultT = TypeVar("ResultT")


class AutomationOperationError(RuntimeError):
    """Task failed; the UI must not display a success notification."""


class _OperationWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], object], parent: QWidget) -> None:
        super().__init__(parent)
        self.operation = operation

    def run(self) -> None:
        try:
            result = self.operation()
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.succeeded.emit(result)


class _OperationDialog(QDialog):
    def __init__(self, title: str, story_id: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("automationOperationProgress")
        self.setWindowTitle(f"{title} — Running")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        self.status_label = QLabel(
            f"{title} for {story_id} is running.\n"
            "The configured provider may incur a charge. Please do not repeat this operation.",
            self,
        )
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.progress = QProgressBar(self)
        self.progress.setObjectName("automationIndeterminateProgress")
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)
        self.elapsed_label = QLabel("Elapsed: 0 seconds", self)
        self.elapsed_label.setObjectName("automationElapsedTime")
        layout.addWidget(self.elapsed_label)

    def reject(self) -> None:
        """No fake cancellation of an in-flight provider call."""


class AutomationProgressRunner:
    """Run one proposal operation at a time with truthful progress and cleanup."""

    def __init__(self, parent: QWidget) -> None:
        self.parent = parent
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def run(self, title: str, story_id: str, operation: Callable[[], ResultT]) -> ResultT:
        if self._active:
            raise AutomationOperationError(
                "An Automation operation is already running; wait for its outcome."
            )
        self._active = True
        dialog = _OperationDialog(title, story_id, self.parent)
        worker = _OperationWorker(operation, dialog)
        timer = QTimer(dialog)
        timer.setInterval(1000)
        started = perf_counter()
        timer.timeout.connect(
            lambda: dialog.elapsed_label.setText(
                f"Elapsed: {int(perf_counter() - started)} seconds"
            )
        )
        outcome: dict[str, object] = {}
        worker.succeeded.connect(lambda result: outcome.update(result=result))
        worker.failed.connect(lambda error: outcome.update(error=error))
        worker.finished.connect(dialog.accept)
        try:
            timer.start()
            # Starting inside the nested event loop avoids the fast-result race.
            QTimer.singleShot(0, worker.start)
            dialog.exec()
            worker.wait()
            if "error" in outcome:
                raise AutomationOperationError(str(outcome["error"]))
            if "result" not in outcome:
                raise AutomationOperationError(
                    "Automation finished without a result. Check the proposal repository."
                )
            return cast(ResultT, outcome["result"])
        finally:
            timer.stop()
            if worker.isRunning():
                worker.wait()
            self._active = False
