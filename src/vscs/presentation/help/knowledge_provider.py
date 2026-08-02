"""Widget binding and keyboard routing for the VSCS Knowledge Framework."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from .help_button import KnowledgeHelpButton
from .help_popup import KnowledgeHelpPopup
from .knowledge_registry import KnowledgeRegistry
from .knowledge_topics import KnowledgeTopic


@dataclass(slots=True)
class KnowledgeBinding:
    """One widget-to-topic binding and its visible help button."""

    widget: QWidget
    topic_id: str
    button: KnowledgeHelpButton


class KnowledgeProvider(QObject):
    """Install topic help on widgets and route buttons and F1 to one popup."""

    def __init__(
        self,
        registry: KnowledgeRegistry,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.registry = registry
        self.parent_widget = parent
        self.popup = KnowledgeHelpPopup(parent)
        self._bindings: dict[QWidget, KnowledgeBinding] = {}

    def install(self, widget: QWidget, topic: str) -> KnowledgeHelpButton:
        """Bind a topic to a widget and return its visible context-help button."""
        existing = self._bindings.get(widget)
        if existing is not None:
            existing.topic_id = topic
            existing.button.topic_id = topic
            existing.button.setAccessibleName(f"Help for {topic}")
            return existing.button

        button = KnowledgeHelpButton(topic, widget)
        button.topic_requested.connect(self.show_topic)
        binding = KnowledgeBinding(widget=widget, topic_id=topic, button=button)
        self._bindings[widget] = binding
        widget.installEventFilter(self)
        self._position_button(binding)
        button.show()
        return button

    def show_topic(self, topic_id: str) -> None:
        """Show a registered topic or a graceful missing-topic explanation."""
        topic = self.registry.get(topic_id)
        if topic is None:
            topic = KnowledgeTopic(
                topic_id=topic_id or "unknown",
                title="Help topic unavailable",
                purpose="This control does not yet have published VSCS guidance.",
                description=(
                    "The requested knowledge topic is not registered. The control remains "
                    "usable, and this topic can be added to the VKF registry later."
                ),
            )
        self.popup.show_topic(topic)

    def topic_for(self, widget: QWidget) -> str | None:
        """Return the topic bound to a widget."""
        binding = self._bindings.get(widget)
        return binding.topic_id if binding is not None else None

    def bindings(self) -> tuple[KnowledgeBinding, ...]:
        """Return all bindings in installation order."""
        return tuple(self._bindings.values())

    def eventFilter(  # noqa: N802
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        """Route F1 and keep overlay buttons aligned when controls resize."""
        if isinstance(watched, QWidget):
            binding = self._bindings.get(watched)
            if binding is not None:
                if event.type() in {
                    QEvent.Type.Resize,
                    QEvent.Type.Show,
                    QEvent.Type.Move,
                }:
                    self._position_button(binding)
                is_f1 = (
                    event.type() == QEvent.Type.KeyPress
                    and isinstance(event, QKeyEvent)
                    and event.key() == Qt.Key.Key_F1
                )
                if is_f1:
                    self.show_topic(binding.topic_id)
                    return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _position_button(binding: KnowledgeBinding) -> None:
        margin = 3
        x = max(margin, binding.widget.width() - binding.button.width() - margin)
        binding.button.move(QPoint(x, margin))
        binding.button.raise_()
