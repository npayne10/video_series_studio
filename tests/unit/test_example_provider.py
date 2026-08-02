"""Tests for Phase 16.2a.8.2 Smart Field Examples."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QApplication

from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.smart_example_scene_editor_dialog import (
    SmartExampleSceneEditorDialog,
)
from vscs.presentation.examples import ExampleContext, ExampleProvider


def _asset(asset_id: str, name: str, category: AssetCategory) -> Asset:
    now = datetime.now(UTC)
    return Asset(
        id=1,
        asset_id=asset_id,
        name=name,
        category=category,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
        created_at=now,
        updated_at=now,
    )


def test_provider_returns_placeholders_tips_and_empty_states() -> None:
    provider = ExampleProvider()

    assert "Arrival at Xorix" in provider.placeholder("scene.name")
    assert "INT./EXT." in provider.inline_tip("scene.heading")
    assert "Asset Manager" in provider.empty_state("scene.participants")
    assert provider.placeholder("unknown.topic") == ""


def test_provider_prefers_project_aware_examples() -> None:
    provider = ExampleProvider(
        context=ExampleContext(
            locations=("Iron Horizon",),
            characters=("James", "Cheryl"),
        )
    )

    assert provider.placeholder("scene.name") == "Example: Arrival at Iron Horizon"
    examples = provider.examples("scene.name")
    assert examples[0] == "Arrival at Iron Horizon"
    assert "James Briefs Cheryl" in examples


def test_provider_supplies_adaptive_heading_suggestions() -> None:
    provider = ExampleProvider(
        context=ExampleContext(locations=("Xorix Spaceport",))
    )

    interior = provider.adaptive("scene.heading", "INT")
    exterior = provider.adaptive("scene.heading", "EXT.")
    unrelated = provider.adaptive("scene.heading", "Bridge")

    assert any(value.startswith("INT.") for value in interior)
    assert any(value.startswith("EXT. XORIX SPACEPORT") for value in exterior)
    assert unrelated == ()


def test_scene_editor_installs_smart_placeholders_and_inline_tips(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SmartExampleSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.scene_name_edit.placeholderText().startswith("Example:")
    assert "EXT." in dialog.heading_edit.placeholderText()
    assert "story event" in dialog.summary_edit.placeholderText().lower()
    assert "unexpected signal" in dialog.dialogue_editor.text_edit.placeholderText()
    assert dialog.findChild(type(dialog.summary_label), "smartExampleTip_scene_name")
    assert dialog.findChild(type(dialog.summary_label), "smartExampleTip_scene_duration")


def test_scene_editor_uses_project_assets_for_examples(
    qtbot: object,
    qapp: QApplication,
) -> None:
    locations = (
        _asset("LOC-IRON-HORIZON", "Iron Horizon", AssetCategory.LOCATION),
    )
    characters = (
        _asset("CHR-JAMES", "James", AssetCategory.CHARACTER),
        _asset("CHR-CHERYL", "Cheryl", AssetCategory.CHARACTER),
    )
    dialog = SmartExampleSceneEditorDialog(
        location_assets=locations,
        participant_assets=characters,
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.scene_name_edit.placeholderText() == "Example: Arrival at Iron Horizon"
    dialog._update_heading_suggestions("EXT")
    suggestions = dialog.heading_completion_model.stringList()
    assert any(value.startswith("EXT. IRON HORIZON") for value in suggestions)


def test_empty_catalog_guidance_and_vkf_coexist(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SmartExampleSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert "Asset Manager" in dialog.participant_help.text()
    assert "Asset Manager" in dialog.asset_help.text()
    assert "participants" in dialog.dialogue_editor.help_label.text().lower()
    assert dialog.knowledge_provider.topic_for(dialog.heading_edit) == "scene.heading"
    assert dialog.heading_edit.completer() is dialog.heading_completer
