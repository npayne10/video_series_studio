"""Tests for Phase 16.2a.8.1 VSCS Knowledge Framework."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from vscs.presentation.dialogs.workflow_scene_editor_dialog import (
    WorkflowSceneEditorDialog,
)
from vscs.presentation.help import (
    KnowledgeProvider,
    KnowledgeRegistry,
    KnowledgeTopic,
    KnowledgeTopicNotFoundError,
    build_default_knowledge_registry,
)


def test_default_registry_contains_all_scene_topics() -> None:
    registry = build_default_knowledge_registry()

    expected = {
        "scene.name",
        "scene.episode",
        "scene.sequence",
        "scene.heading",
        "scene.location",
        "scene.summary",
        "scene.participants",
        "scene.dialogue",
        "scene.required_assets",
        "scene.time",
        "scene.transition",
        "scene.duration",
        "scene.production_type",
        "scene.container_id",
    }

    assert {topic.topic_id for topic in registry.all_topics()} == expected
    assert registry.topic("scene.location").title == "Primary Location"


def test_registry_reports_missing_topic() -> None:
    registry = KnowledgeRegistry()

    try:
        registry.topic("missing.topic")
    except KnowledgeTopicNotFoundError as exc:
        assert "missing.topic" in str(exc)
    else:
        raise AssertionError("Missing topic should raise KnowledgeTopicNotFoundError")


def test_registry_replaces_topic_by_canonical_id() -> None:
    registry = KnowledgeRegistry()
    first = KnowledgeTopic("test.topic", "First", "Purpose", "Description")
    second = KnowledgeTopic("test.topic", "Second", "Purpose", "Description")

    registry.register(first)
    registry.register(second)

    assert registry.topic("test.topic") is second


def test_provider_reuses_popup_and_routes_help_button(
    qtbot: object,
    qapp: QApplication,
) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)  # type: ignore[attr-defined]
    widget = QLineEdit(parent)
    registry = build_default_knowledge_registry()
    provider = KnowledgeProvider(registry, parent)

    button = provider.install(widget, "scene.name")
    popup = provider.popup
    button.click()

    assert provider.popup is popup
    assert popup.topic_id == "scene.name"
    assert "Scene Name" in popup.content_label.text()

    provider.show_topic("scene.location")

    assert provider.popup is popup
    assert popup.topic_id == "scene.location"


def test_provider_handles_unknown_topic_gracefully(
    qtbot: object,
    qapp: QApplication,
) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)  # type: ignore[attr-defined]
    provider = KnowledgeProvider(KnowledgeRegistry(), parent)

    provider.show_topic("unpublished.topic")

    assert provider.popup.topic_id == "unpublished.topic"
    assert "Help topic unavailable" in provider.popup.content_label.text()


def test_f1_opens_topic_for_focused_control(
    qtbot: object,
    qapp: QApplication,
) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)  # type: ignore[attr-defined]
    widget = QLineEdit(parent)
    provider = KnowledgeProvider(build_default_knowledge_registry(), parent)
    provider.install(widget, "scene.heading")
    parent.show()
    widget.setFocus()

    QTest.keyClick(widget, Qt.Key.Key_F1)

    assert provider.popup.topic_id == "scene.heading"
    assert provider.popup.isVisible()


def test_scene_editor_installs_help_for_all_completed_controls(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = WorkflowSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    topics = {binding.topic_id for binding in dialog.knowledge_provider.bindings()}

    assert topics == {
        "scene.name",
        "scene.episode",
        "scene.sequence",
        "scene.heading",
        "scene.location",
        "scene.summary",
        "scene.participants",
        "scene.dialogue",
        "scene.required_assets",
        "scene.time",
        "scene.transition",
        "scene.duration",
    }
    assert len(dialog.knowledge_provider.bindings()) == 18


def test_scene_editor_f1_routes_from_dialogue_text_control(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = WorkflowSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    dialog.dialogue_editor.text_edit.setFocus()

    QTest.keyClick(dialog.dialogue_editor.text_edit, Qt.Key.Key_F1)

    assert dialog.knowledge_provider.popup.topic_id == "scene.dialogue"
