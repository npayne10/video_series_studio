"""Reusable guided navigation for VSCS workflow steps."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QAbstractScrollArea, QWidget


class WorkflowNavigator(QObject):
    """Focus, reveal, document and briefly highlight workflow targets."""

    navigation_started = Signal(str)
    navigation_finished = Signal(str)

    def __init__(
        self,
        scroll_area: QAbstractScrollArea,
        show_topic: Callable[[str], None],
        parent: QObject | None = None,
        *,
        highlight_milliseconds: int = 1200,
    ) -> None:
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.show_topic = show_topic
        self.highlight_milliseconds = highlight_milliseconds
        self._targets: dict[str, QWidget] = {}
        self._topics: dict[str, str] = {}
        self._original_styles: dict[QWidget, str] = {}
        self._highlighted: QWidget | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear_highlight)

    def configure(
        self,
        targets: Mapping[str, QWidget],
        topics: Mapping[str, str],
    ) -> None:
        """Replace the canonical workflow target and topic mappings."""
        self._targets = dict(targets)
        self._topics = dict(topics)

    def target(self, step_id: str) -> QWidget | None:
        """Return the configured widget for a workflow step."""
        return self._targets.get(step_id)

    def navigate(self, step_id: str) -> bool:
        """Navigate to a configured step and return whether it was found."""
        target = self.target(step_id)
        if target is None:
            return False
        self.navigation_started.emit(step_id)
        self.clear_highlight()
        self._reveal(target)
        if target.focusPolicy() is not Qt.FocusPolicy.NoFocus and target.isEnabled():
            target.setFocus(Qt.FocusReason.ShortcutFocusReason)
        topic_id = self._topics.get(step_id)
        if topic_id:
            self.show_topic(topic_id)
        self._highlight(target)
        self.navigation_finished.emit(step_id)
        return True

    def clear_highlight(self) -> None:
        """Restore the style of the currently highlighted widget."""
        target = self._highlighted
        if target is None:
            return
        target.setStyleSheet(self._original_styles.pop(target, ""))
        target.setProperty("workflowGuidedTarget", False)
        target.style().unpolish(target)
        target.style().polish(target)
        self._highlighted = None

    def _reveal(self, target: QWidget) -> None:
        ensure_visible = getattr(self.scroll_area, "ensureWidgetVisible", None)
        if callable(ensure_visible):
            ensure_visible(target, 24, 24)

    def _highlight(self, target: QWidget) -> None:
        self._original_styles[target] = target.styleSheet()
        target.setProperty("workflowGuidedTarget", True)
        target.setStyleSheet(
            target.styleSheet()
            + "\n*[workflowGuidedTarget='true'] {"
            "border: 2px solid palette(highlight);"
            "border-radius: 4px;"
            "background-color: palette(alternate-base);"
            "}"
        )
        target.style().unpolish(target)
        target.style().polish(target)
        self._highlighted = target
        self._timer.start(self.highlight_milliseconds)
