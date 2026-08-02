"""Accessible rich popup for VSCS knowledge topics."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .knowledge_topics import KnowledgeTopic


class KnowledgeHelpPopup(QDialog):
    """Render one knowledge topic in a reusable scrollable dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("VSCS Help")
        self.setModal(False)
        self.setMinimumSize(420, 320)
        self.resize(520, 560)
        self.setWindowFlag(Qt.WindowType.Tool, True)

        self.content_label = QLabel()
        self.content_label.setObjectName("knowledgeHelpContent")
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.TextFormat.RichText)
        self.content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        self.content_label.setOpenExternalLinks(False)
        self.content_label.setMargin(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.content_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_button = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setAccessibleName("Close VSCS help")
        buttons.rejected.connect(self.close)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)

        self._topic_id: str | None = None

    @property
    def topic_id(self) -> str | None:
        """Return the topic currently displayed."""
        return self._topic_id

    def show_topic(self, topic: KnowledgeTopic) -> None:
        """Render and show one topic."""
        self._topic_id = topic.topic_id
        self.setWindowTitle(f"VSCS Help — {topic.title}")
        self.content_label.setText(self._topic_html(topic))
        self.show()
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _topic_html(topic: KnowledgeTopic) -> str:
        sections = [
            f"<h2>{escape(topic.title)}</h2>",
            f"<h3>Purpose</h3><p>{escape(topic.purpose)}</p>",
            f"<h3>Description</h3><p>{escape(topic.description)}</p>",
        ]
        if topic.examples:
            examples = "".join(
                f"<li><code>{escape(value)}</code></li>"
                for value in topic.examples
            )
            sections.append(f"<h3>Examples</h3><ul>{examples}</ul>")
        if topic.common_mistakes:
            mistakes = "".join(
                f"<li>{escape(value)}</li>" for value in topic.common_mistakes
            )
            sections.append(f"<h3>Common mistakes</h3><ul>{mistakes}</ul>")
        if topic.related_topics:
            related = "".join(
                f"<li><code>{escape(value)}</code></li>"
                for value in topic.related_topics
            )
            sections.append(f"<h3>Related topics</h3><ul>{related}</ul>")
        if topic.documentation_page:
            sections.append(
                "<h3>Documentation</h3>"
                f"<p><code>{escape(topic.documentation_page)}</code></p>"
            )
        return "".join(sections)
