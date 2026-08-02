"""Reusable context-help button for VKF topics."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton, QWidget


class KnowledgeHelpButton(QPushButton):
    """Small accessible button that requests one knowledge topic."""

    topic_requested = Signal(str)

    def __init__(
        self,
        topic_id: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("?", parent)
        self.topic_id = topic_id
        self.setObjectName("knowledgeHelpButton")
        self.setFixedSize(22, 22)
        self.setToolTip("Show context-sensitive help (F1)")
        self.setAccessibleName(f"Help for {topic_id}")
        self.clicked.connect(self._request_topic)

    def _request_topic(self) -> None:
        self.topic_requested.emit(self.topic_id)
