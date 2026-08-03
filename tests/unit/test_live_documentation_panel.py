"""Tests for Phase 16.2a.8.3 live documentation panel."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QApplication, QWidget

from vscs.presentation.dialogs.live_documentation_scene_editor_dialog import (
    LiveDocumentationSceneEditorDialog,
)
from vscs.presentation.help import KnowledgeDocumentationPanel


def _focus(widget: QWidget, qapp: QApplication) -> None:
    QApplication.sendEvent(widget, QFocusEvent(QEvent.Type.FocusIn))
    qapp.processEvents()


def test_live_panel_replaces_scroll_area_with_splitter(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = LiveDocumentationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.editor_splitter.indexOf(dialog.scroll_area) == 0
    assert dialog.editor_splitter.indexOf(dialog.documentation_panel) == 1
    assert isinstance(dialog.documentation_panel, KnowledgeDocumentationPanel)
    assert dialog.validation_label.parentWidget() is dialog
    assert dialog.buttons.parentWidget() is dialog


def test_live_panel_starts_with_scene_name_guidance(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = LiveDocumentationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.documentation_panel.topic_id == "scene.name"
    assert "Scene Name" in dialog.documentation_panel.content_label.text()
    assert "Purpose" in dialog.documentation_panel.content_label.text()


def test_focus_updates_live_documentation_topic(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = LiveDocumentationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    _focus(dialog.heading_edit, qapp)
    assert dialog.documentation_panel.topic_id == "scene.heading"
    assert "Scene Heading" in dialog.documentation_panel.content_label.text()

    _focus(dialog.duration_spin, qapp)
    assert dialog.documentation_panel.topic_id == "scene.duration"


def test_nested_dialogue_control_routes_to_dialogue_topic(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = LiveDocumentationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    _focus(dialog.dialogue_editor.text_edit.viewport(), qapp)

    assert dialog.documentation_panel.topic_id == "scene.dialogue"
    assert "Dialogue" in dialog.documentation_panel.content_label.text()


def test_help_button_updates_live_panel_and_keeps_popup_help(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = LiveDocumentationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    binding = next(
        item
        for item in dialog.knowledge_provider.bindings()
        if item.topic_id == "scene.location"
    )

    binding.button.click()
    qapp.processEvents()

    assert dialog.documentation_panel.topic_id == "scene.location"
    assert dialog.knowledge_provider.popup.topic_id == "scene.location"
    dialog.knowledge_provider.popup.close()


def test_unknown_live_topic_returns_to_welcome_guidance(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = LiveDocumentationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.show_live_topic("scene.not_registered")

    assert dialog.documentation_panel.topic_id is None
    content = dialog.documentation_panel.content_label.text()
    assert "Select or tab into any field" in content
