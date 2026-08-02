"""Tests for structured dialogue and the responsive scene editor layout."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from vscs.application.ssie import Scene
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.structured_scene_editor_dialog import (
    StructuredSceneEditorDialog,
)
from vscs.presentation.widgets.dialogue_editor import (
    DialogueEditorWidget,
    DialogueEntry,
)


def _character(asset_id: str, name: str) -> Asset:
    now = datetime.now(UTC)
    return Asset(
        id=1,
        asset_id=asset_id,
        name=name,
        category=AssetCategory.CHARACTER,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
        created_at=now,
        updated_at=now,
    )


def _participants() -> tuple[Asset, ...]:
    return (
        _character("CHR-JAMES", "Commander James Spence"),
        _character("CHR-SANDRA", "Sandra Crawford"),
    )


def test_dialogue_entry_round_trips_structured_and_legacy_lines() -> None:
    structured = DialogueEntry.parse("CHR-JAMES [quietly]: We should leave.")
    legacy = DialogueEntry.parse("A legacy line without a speaker")

    assert structured == DialogueEntry("CHR-JAMES", "We should leave.", "quietly")
    assert structured.serialize() == "CHR-JAMES [quietly]: We should leave."
    assert legacy == DialogueEntry(None, "A legacy line without a speaker")
    assert legacy.serialize() == "A legacy line without a speaker"


def test_dialogue_editor_limits_new_speakers_to_selected_participants(
    qtbot: object,
    qapp: QApplication,
) -> None:
    editor = DialogueEditorWidget(_participants())
    qtbot.addWidget(editor)  # type: ignore[attr-defined]
    editor.set_participants(("CHR-JAMES",))

    editor.add_entry("CHR-JAMES", "That signal should not be there.")

    assert editor.dialogue_lines() == (
        "CHR-JAMES: That signal should not be there.",
    )
    with pytest.raises(ValueError, match="selected scene participants"):
        editor.add_entry("CHR-SANDRA", "I agree.")


def test_dialogue_editor_preserves_order_and_performance_notes(
    qtbot: object,
    qapp: QApplication,
) -> None:
    editor = DialogueEditorWidget(_participants())
    qtbot.addWidget(editor)  # type: ignore[attr-defined]
    editor.set_participants(("CHR-JAMES", "CHR-SANDRA"))
    editor.add_entry("CHR-JAMES", "Look at the display.", "controlled")
    editor.add_entry("CHR-SANDRA", "The reading is impossible.", "alarmed")

    editor.dialogue_list.setCurrentRow(1)
    editor._move_selected(-1)

    assert editor.dialogue_lines() == (
        "CHR-SANDRA [alarmed]: The reading is impossible.",
        "CHR-JAMES [controlled]: Look at the display.",
    )


def test_dialogue_editor_loads_and_deletes_legacy_lines(
    qtbot: object,
    qapp: QApplication,
) -> None:
    editor = DialogueEditorWidget(_participants())
    qtbot.addWidget(editor)  # type: ignore[attr-defined]
    editor.set_participants(("CHR-JAMES",))
    editor.load_lines(
        (
            "CHR-JAMES: Hold position.",
            "An unstructured legacy utterance",
        )
    )

    assert len(editor.entries()) == 2
    assert editor.entries()[1].speaker_id is None

    editor.dialogue_list.setCurrentRow(1)
    editor._delete_entry()

    assert editor.dialogue_lines() == ("CHR-JAMES: Hold position.",)


def test_structured_scene_dialogue_round_trips_through_scene_contract(
    qtbot: object,
    qapp: QApplication,
) -> None:
    scene = Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The crew studies an impossible signal.",
        participant_asset_ids=("CHR-JAMES", "CHR-SANDRA"),
        dialogue=(
            "CHR-JAMES [quietly]: That signal should not be there.",
            "CHR-SANDRA: But it is.",
        ),
        scene_name="The Signal",
    )
    dialog = StructuredSceneEditorDialog(
        scene,
        participant_assets=_participants(),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    result = dialog.scene()

    assert result.dialogue == scene.dialogue
    assert result.participant_asset_ids == scene.participant_asset_ids


def test_deselecting_participant_prevents_new_dialogue_for_that_speaker(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = StructuredSceneEditorDialog(participant_assets=_participants())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    james_item = next(
        dialog.participant_list.item(index)
        for index in range(dialog.participant_list.count())
        if dialog.participant_list.item(index).data(Qt.ItemDataRole.UserRole)
        == "CHR-JAMES"
    )
    james_item.setCheckState(Qt.CheckState.Checked)
    dialog.dialogue_editor.add_entry("CHR-JAMES", "We proceed.")

    james_item.setCheckState(Qt.CheckState.Unchecked)

    with pytest.raises(ValueError, match="selected scene participants"):
        dialog.dialogue_editor.add_entry("CHR-JAMES", "Another line.")
    assert dialog.dialogue_editor.dialogue_lines() == (
        "CHR-JAMES: We proceed.",
    )


def test_scene_editor_places_long_form_inside_scroll_area(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = StructuredSceneEditorDialog(participant_assets=_participants())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.scroll_area.widget() is dialog.scroll_content
    assert _is_descendant(dialog.scene_name_edit, dialog.scroll_content)
    assert _is_descendant(dialog.dialogue_editor, dialog.scroll_content)
    assert _is_descendant(dialog.asset_list, dialog.scroll_content)


def test_validation_and_actions_remain_outside_scrolling_content(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = StructuredSceneEditorDialog(participant_assets=_participants())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert not _is_descendant(dialog.validation_label, dialog.scroll_content)
    assert not _is_descendant(dialog.buttons, dialog.scroll_content)
    assert not _is_descendant(dialog.save_button, dialog.scroll_content)


def test_scene_editor_exposes_logical_section_landmarks(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = StructuredSceneEditorDialog(participant_assets=_participants())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    for object_name in (
        "sceneSectionGeneral",
        "sceneSectionStoryContext",
        "sceneSectionCast&Dialogue",
        "sceneSectionAssets",
        "sceneSectionProduction",
    ):
        assert dialog.findChild(QWidget, object_name) is not None


def test_scene_editor_remains_usable_at_laptop_sized_viewport(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = StructuredSceneEditorDialog(participant_assets=_participants())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.resize(700, 520)
    dialog.show()
    qapp.processEvents()

    assert dialog.scroll_area.isVisible()
    assert dialog.buttons.isVisible()
    assert dialog.height() == 520
    assert dialog.scroll_area.verticalScrollBar().maximum() > 0


def _is_descendant(widget: QWidget, ancestor: QWidget) -> bool:
    parent = widget.parentWidget()
    while parent is not None:
        if parent is ancestor:
            return True
        parent = parent.parentWidget()
    return False
