"""Story Analysis must visibly run without freezing the Qt event loop."""

from threading import Event
from time import perf_counter
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

from vscs.application.story.lifecycle import StoryRecord
from vscs.presentation.widgets.browseable_story_workspace import (
    BrowseableStoryWorkspaceWidget,
)


class _AnalysisHost(QWidget):
    def __init__(self, cache):
        super().__init__()
        self.analysis_cache = cache
        self.errors = []

    def _error(self, message):
        self.errors.append(message)


def test_story_analysis_progress_keeps_ui_responsive(qtbot):
    release = Event()
    started = Event()
    seen = []

    class Cache:
        def analyze(self, story, source):
            started.set()
            assert release.wait(8), "GUI event loop stalled during Story Analysis"
            return SimpleNamespace(status=SimpleNamespace(value="completed"), diagnostics=())

    host = _AnalysisHost(Cache())
    qtbot.addWidget(host)

    deadline = perf_counter() + 5.0
    observer = QTimer(host)
    observer.setInterval(10)

    def check_running():
        active = QApplication.activeModalWidget()
        visible = (
            active is not None
            and active.objectName() == "storyAnalysisProgress"
            and active.isVisible()
        )
        # Avoid assuming the worker starts within a fixed 70 ms under full-suite load.
        if started.is_set() and visible:
            seen.append(True)
            observer.stop()
            release.set()
        elif perf_counter() >= deadline:
            seen.append(False)
            observer.stop()
            release.set()

    observer.timeout.connect(check_running)
    observer.start()
    succeeded = BrowseableStoryWorkspaceWidget._run_analysis(
        host, StoryRecord(story_id="STORY-001", title="Disposable"), "Test story"
    )
    assert succeeded
    assert seen == [True]
    assert host.errors == []


def test_story_analysis_provider_error_is_reported(qtbot):
    class FailingCache:
        def analyze(self, story, source):
            raise RuntimeError("Controlled provider failure")

    host = _AnalysisHost(FailingCache())
    qtbot.addWidget(host)
    succeeded = BrowseableStoryWorkspaceWidget._run_analysis(
        host, StoryRecord(story_id="STORY-001", title="Disposable"), "Test story"
    )
    assert not succeeded
    assert any("Controlled provider failure" in message for message in host.errors)
