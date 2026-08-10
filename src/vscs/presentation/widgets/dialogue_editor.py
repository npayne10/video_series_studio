"""Structured dialogue editing controls for VSCS scenes."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from vscs.domain.assets import Asset

_DIALOGUE_PATTERN = re.compile(
    r"^(?P<speaker>[A-Za-z0-9_-]+)(?:\s+\[(?P<note>[^]]+)\])?:\s*(?P<text>.+)$"
)


@dataclass(frozen=True, slots=True)
class DialogueEntry:
    """One ordered scene utterance with optional performance direction."""

    speaker_id: str | None
    text: str
    performance_note: str = ""

    def serialize(self) -> str:
        """Serialize into the backward-compatible Scene dialogue line format."""
        text = self.text.strip()
        if self.speaker_id is None:
            return text
        note = f" [{self.performance_note.strip()}]" if self.performance_note.strip() else ""
        return f"{self.speaker_id}{note}: {text}"

    @classmethod
    def parse(cls, line: str) -> DialogueEntry:
        """Parse structured dialogue while preserving legacy unstructured lines."""
        normalized = line.strip()
        match = _DIALOGUE_PATTERN.match(normalized)
        if match is None:
            return cls(speaker_id=None, text=normalized)
        return cls(
            speaker_id=match.group("speaker"),
            text=match.group("text").strip(),
            performance_note=(match.group("note") or "").strip(),
        )


class DialogueEditorWidget(QWidget):
    """Add, edit, remove and reorder dialogue tied to scene participants."""

    def __init__(
        self,
        participant_assets: tuple[Asset, ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._participant_names = {asset.asset_id: asset.name for asset in participant_assets}
        self._participant_ids: tuple[str, ...] = ()
        self._entries: list[DialogueEntry] = []
        self._editing_index: int | None = None

        self.setObjectName("sceneDialogueEditor")
        self.speaker_combo = QComboBox()
        self.speaker_combo.setObjectName("dialogueSpeakerSelector")
        self.speaker_combo.setToolTip(
            "Choose a speaker from the characters selected as scene participants."
        )
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("dialogueText")
        self.text_edit.setPlaceholderText("Enter the spoken line...")
        self.text_edit.setMaximumHeight(90)
        self.performance_edit = QLineEdit()
        self.performance_edit.setObjectName("dialoguePerformanceNote")
        self.performance_edit.setPlaceholderText(
            "Optional performance note, for example: quietly, alarmed"
        )

        self.add_button = QPushButton("Add Dialogue")
        self.cancel_edit_button = QPushButton("Cancel Edit")
        self.cancel_edit_button.hide()

        entry_buttons = QHBoxLayout()
        entry_buttons.addWidget(self.add_button)
        entry_buttons.addWidget(self.cancel_edit_button)
        entry_buttons.addStretch(1)

        self.dialogue_list = QListWidget()
        self.dialogue_list.setObjectName("dialogueEntryList")
        self.dialogue_list.setAlternatingRowColors(True)
        self.dialogue_list.setMinimumHeight(150)

        self.edit_button = QPushButton("Edit")
        self.delete_button = QPushButton("Delete")
        self.up_button = QPushButton("Move Up")
        self.down_button = QPushButton("Move Down")
        list_buttons = QHBoxLayout()
        for button in (
            self.edit_button,
            self.delete_button,
            self.up_button,
            self.down_button,
        ):
            list_buttons.addWidget(button)
        list_buttons.addStretch(1)

        self.help_label = QLabel()
        self.help_label.setObjectName("dialogueHelp")
        self.help_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Speaker"))
        layout.addWidget(self.speaker_combo)
        layout.addWidget(QLabel("Dialogue"))
        layout.addWidget(self.text_edit)
        layout.addWidget(self.performance_edit)
        layout.addLayout(entry_buttons)
        layout.addWidget(self.dialogue_list)
        layout.addLayout(list_buttons)
        layout.addWidget(self.help_label)

        self.add_button.clicked.connect(self._commit_entry)
        self.cancel_edit_button.clicked.connect(self._cancel_edit)
        self.edit_button.clicked.connect(self._begin_edit)
        self.delete_button.clicked.connect(self._delete_entry)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        self.dialogue_list.itemDoubleClicked.connect(lambda _item: self._begin_edit())
        self.dialogue_list.currentRowChanged.connect(self._update_controls)
        self.text_edit.textChanged.connect(self._update_controls)
        self._refresh()

    def set_participants(self, participant_ids: Iterable[str]) -> None:
        """Set valid speakers from the scene's currently selected participants."""
        current = self.speaker_combo.currentData()
        self._participant_ids = tuple(dict.fromkeys(participant_ids))
        known_entry_speakers = tuple(
            dict.fromkeys(
                entry.speaker_id for entry in self._entries if entry.speaker_id is not None
            )
        )
        self.speaker_combo.clear()
        self.speaker_combo.addItem("Select a speaker...", "")
        for participant_id in self._participant_ids:
            name = self._participant_names.get(participant_id, "Unavailable character")
            self.speaker_combo.addItem(f"{name}  —  {participant_id}", participant_id)
        for speaker_id in known_entry_speakers:
            if speaker_id not in self._participant_ids:
                self.speaker_combo.addItem(f"Unavailable speaker  —  {speaker_id}", speaker_id)
        index = self.speaker_combo.findData(current)
        self.speaker_combo.setCurrentIndex(max(index, 0))
        self._update_controls()

    def load_lines(self, lines: Iterable[str]) -> None:
        """Load structured or legacy dialogue lines."""
        self._entries = [DialogueEntry.parse(line) for line in lines if line.strip()]
        self._editing_index = None
        self._refresh()
        self.set_participants(self._participant_ids)

    def dialogue_lines(self) -> tuple[str, ...]:
        """Return ordered dialogue using the persistent Scene line format."""
        return tuple(entry.serialize() for entry in self._entries if entry.text.strip())

    def entries(self) -> tuple[DialogueEntry, ...]:
        """Return immutable dialogue entries for tests and future compilers."""
        return tuple(self._entries)

    def add_entry(
        self,
        speaker_id: str,
        text: str,
        performance_note: str = "",
    ) -> None:
        """Add a validated entry programmatically."""
        if speaker_id not in self._participant_ids:
            raise ValueError("Dialogue speakers must be selected scene participants")
        if not text.strip():
            raise ValueError("Dialogue text cannot be empty")
        self._entries.append(DialogueEntry(speaker_id, text.strip(), performance_note.strip()))
        self._refresh()

    def _commit_entry(self) -> None:
        speaker = self.speaker_combo.currentData()
        text = self.text_edit.toPlainText().strip()
        if not isinstance(speaker, str) or speaker not in self._participant_ids or not text:
            self._update_controls()
            return
        entry = DialogueEntry(
            speaker_id=speaker,
            text=text,
            performance_note=self.performance_edit.text().strip(),
        )
        if self._editing_index is None:
            self._entries.append(entry)
        else:
            self._entries[self._editing_index] = entry
        self._clear_editor()
        self._refresh()

    def _begin_edit(self) -> None:
        row = self.dialogue_list.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        entry = self._entries[row]
        if entry.speaker_id is None or entry.speaker_id not in self._participant_ids:
            return
        self._editing_index = row
        self.speaker_combo.setCurrentIndex(self.speaker_combo.findData(entry.speaker_id))
        self.text_edit.setPlainText(entry.text)
        self.performance_edit.setText(entry.performance_note)
        self.add_button.setText("Update Dialogue")
        self.cancel_edit_button.show()
        self._update_controls()

    def _cancel_edit(self) -> None:
        self._clear_editor()
        self._update_controls()

    def _delete_entry(self) -> None:
        row = self.dialogue_list.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        del self._entries[row]
        self._clear_editor()
        self._refresh()

    def _move_selected(self, offset: int) -> None:
        row = self.dialogue_list.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= len(self._entries):
            return
        self._entries[row], self._entries[target] = (
            self._entries[target],
            self._entries[row],
        )
        self._refresh()
        self.dialogue_list.setCurrentRow(target)

    def _clear_editor(self) -> None:
        self._editing_index = None
        self.text_edit.clear()
        self.performance_edit.clear()
        self.add_button.setText("Add Dialogue")
        self.cancel_edit_button.hide()

    def _refresh(self) -> None:
        selected = self.dialogue_list.currentRow()
        self.dialogue_list.clear()
        for entry in self._entries:
            speaker = entry.speaker_id or "Legacy dialogue"
            name = self._participant_names.get(speaker, speaker)
            note = f" [{entry.performance_note}]" if entry.performance_note else ""
            item = QListWidgetItem(f"{name}{note}: {entry.text}")
            if entry.speaker_id is None or entry.speaker_id not in self._participant_ids:
                item.setToolTip(
                    "This legacy or unavailable-speaker line is preserved. Select a valid "
                    "participant to replace it with structured dialogue."
                )
            self.dialogue_list.addItem(item)
        if self._entries:
            self.dialogue_list.setCurrentRow(min(max(selected, 0), len(self._entries) - 1))
        self._update_controls()

    def _update_controls(self, *_args: object) -> None:
        row = self.dialogue_list.currentRow()
        has_selection = 0 <= row < len(self._entries)
        speaker = self.speaker_combo.currentData()
        valid_speaker = isinstance(speaker, str) and speaker in self._participant_ids
        has_text = bool(self.text_edit.toPlainText().strip())
        self.add_button.setEnabled(valid_speaker and has_text)
        self.edit_button.setEnabled(
            has_selection and self._entries[row].speaker_id in self._participant_ids
        )
        self.delete_button.setEnabled(has_selection)
        self.up_button.setEnabled(has_selection and row > 0)
        self.down_button.setEnabled(has_selection and row < len(self._entries) - 1)
        if not self._participant_ids:
            self.help_label.setText(
                "Select scene participants before adding dialogue. Speakers are limited "
                "to characters present in the scene."
            )
            self.help_label.setStyleSheet("color: #8a5a00;")
        else:
            count = len(self._entries)
            label = "entry" if count == 1 else "entries"
            self.help_label.setText(
                f"{count} dialogue {label}. Speakers must remain selected participants."
            )
            self.help_label.setStyleSheet("")
