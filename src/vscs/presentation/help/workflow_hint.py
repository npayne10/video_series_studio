"""Reusable concise workflow guidance for VKF-enabled interfaces."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget


class WorkflowHint(QLabel):
    """Small reusable hint label linked conceptually to VKF guidance."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("knowledgeWorkflowHint")
        self.setWordWrap(True)
        self.setStyleSheet("color: palette(mid); font-style: italic;")
