"""Tests for Phase 16.2a.5 structured dialogue editing."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from PySide6.QtWidgets import QApplication

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
        if dialog.participant_list.item(index).data(256) == "CHR-JAMES"
    )
    james_item.setCheckState(2)
    dialog.dialogue_editor.add_entry("CHR-JAMES", "We proceed.")

    james_item.setCheckState(0)

    with pytest.raises(ValueError, match="selected scene participants"):
        dialog.dialogue_editor.add_entry("CHR-JAMES", "Another line.")
    assert dialog.dialogue_editor.dialogue_lines() == (
        "CHR-JAMES: We proceed.",
    )
