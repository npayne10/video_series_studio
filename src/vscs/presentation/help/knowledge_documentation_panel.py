"""Reusable live documentation panel for VSCS knowledge topics."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from .knowledge_topics import KnowledgeTopic


class KnowledgeDocumentationPanel(QWidget):
    """Display the active VKF topic alongside an editor workflow."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("knowledgeDocumentationPanel")
        self.setMinimumWidth(280)
        self.setAccessibleName("Live VSCS documentation")

        self.heading_label = QLabel("Live documentation", self)
        self.heading_label.setObjectName("knowledgeDocumentationHeading")
        self.heading_label.setStyleSheet("font-size: 15px; font-weight: 600;")

        self.content_label = QLabel(self)
        self.content_label.setObjectName("knowledgeDocumentationContent")
        self.content_label.setWordWrap(True)
        self.content_label.setTextFormat(Qt.TextFormat.RichText)
        self.content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
        )
        self.content_label.setOpenExternalLinks(False)
        self.content_label.setMargin(12)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("knowledgeDocumentationScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.StyledPanel)
        self.scroll_area.setWidget(self.content_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.heading_label)
        layout.addWidget(self.scroll_area, 1)

        self._topic_id: str | None = None
        self.show_welcome()

    @property
    def topic_id(self) -> str | None:
        """Return the topic currently displayed."""
        return self._topic_id

    def show_welcome(self) -> None:
        """Show the initial guidance before a field receives focus."""
        self._topic_id = None
        self.content_label.setText(
            "<h2>Scene Editor guidance</h2>"
            "<p>Select or tab into any field to see its purpose, usage guidance, "
            "examples and common mistakes here.</p>"
            "<p>Press <b>F1</b> or click a <b>?</b> button for the full help popup.</p>"
        )

    def show_topic(self, topic: KnowledgeTopic) -> None:
        """Render one knowledge topic in the live panel."""
        self._topic_id = topic.topic_id
        self.content_label.setText(self._topic_html(topic))
        self.scroll_area.verticalScrollBar().setValue(0)

    @staticmethod
    def _topic_html(topic: KnowledgeTopic) -> str:
        sections = [
            f"<h2>{escape(topic.title)}</h2>",
            f"<p><b>Purpose:</b> {escape(topic.purpose)}</p>",
            f"<p>{escape(topic.description)}</p>",
        ]
        if topic.examples:
            examples = "".join(
                f"<li><code>{escape(example)}</code></li>"
                for example in topic.examples
            )
            sections.append(f"<h3>Examples</h3><ul>{examples}</ul>")
        if topic.common_mistakes:
            mistakes = "".join(
                f"<li>{escape(mistake)}</li>"
                for mistake in topic.common_mistakes
            )
            sections.append(f"<h3>Common mistakes</h3><ul>{mistakes}</ul>")
        if topic.related_topics:
            related = "".join(
                f"<li><code>{escape(topic_id)}</code></li>"
                for topic_id in topic.related_topics
            )
            sections.append(f"<h3>Related topics</h3><ul>{related}</ul>")
        return "".join(sections)
