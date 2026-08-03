"""Scene Editor with a focus-driven live VKF documentation panel."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.smart_example_scene_editor_dialog import (
    SmartExampleSceneEditorDialog,
)
from vscs.presentation.help import KnowledgeDocumentationPanel


class LiveDocumentationSceneEditorDialog(SmartExampleSceneEditorDialog):
    """Show relevant VKF guidance beside the field currently being edited."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scene, parent, **kwargs)
        self._live_topic_widgets: dict[QObject, str] = {}
        self._install_live_documentation_panel()
        self._install_live_topic_routing()
        self.show_live_topic("scene.name")

    def show_live_topic(self, topic_id: str) -> None:
        """Display one registered VKF topic in the live panel."""
        topic = self.knowledge_provider.registry.get(topic_id)
        if topic is None:
            self.documentation_panel.show_welcome()
            return
        self.documentation_panel.show_topic(topic)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        """Update live documentation when a bound control gains focus."""
        if event.type() == QEvent.Type.FocusIn:
            topic_id = self._live_topic_widgets.get(watched)
            if topic_id is not None:
                self.show_live_topic(topic_id)
        return super().eventFilter(watched, event)

    def _install_live_documentation_panel(self) -> None:
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            raise RuntimeError("Scene Editor root layout must be a QVBoxLayout.")

        scroll_index = root.indexOf(self.scroll_area)
        if scroll_index < 0:
            raise RuntimeError("Scene Editor scroll area is not present in its root layout.")

        root.removeWidget(self.scroll_area)
        self.editor_splitter = QSplitter(self)
        self.editor_splitter.setObjectName("sceneEditorDocumentationSplitter")
        self.editor_splitter.addWidget(self.scroll_area)

        self.documentation_panel = KnowledgeDocumentationPanel(self.editor_splitter)
        self.editor_splitter.addWidget(self.documentation_panel)
        self.editor_splitter.setStretchFactor(0, 3)
        self.editor_splitter.setStretchFactor(1, 2)
        self.editor_splitter.setCollapsible(0, False)
        self.editor_splitter.setCollapsible(1, True)
        self.editor_splitter.setSizes([560, 320])

        root.insertWidget(scroll_index, self.editor_splitter, 1)
        self.resize(max(self.width(), 1040), max(self.height(), 720))

    def _install_live_topic_routing(self) -> None:
        for binding in self.knowledge_provider.bindings():
            self._bind_live_topic(binding.widget, binding.topic_id)
            for child in binding.widget.findChildren(QWidget):
                self._bind_live_topic(child, binding.topic_id)
            binding.button.topic_requested.connect(self.show_live_topic)

    def _bind_live_topic(self, widget: QWidget, topic_id: str) -> None:
        self._live_topic_widgets[widget] = topic_id
        widget.installEventFilter(self)
