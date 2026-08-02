"""Scene editor variant with structured participant-aware dialogue controls."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QWidget

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.scene_editor_dialog import SceneEditorDialog
from vscs.presentation.widgets.dialogue_editor import DialogueEditorWidget


class StructuredSceneEditorDialog(SceneEditorDialog):
    """Extend the scene editor with structured dialogue management."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        participant_assets = kwargs.get("participant_assets", ())
        if not isinstance(participant_assets, tuple):
            participant_assets = ()
        super().__init__(scene, parent, **kwargs)

        legacy_lines = tuple(
            line.strip()
            for line in self.dialogue_edit.toPlainText().splitlines()
            if line.strip()
        )
        self.dialogue_editor = DialogueEditorWidget(participant_assets, self)
        root_layout = self.layout()
        if root_layout is not None:
            root_layout.replaceWidget(self.dialogue_edit, self.dialogue_editor)
        self.dialogue_edit.hide()
        self.dialogue_edit.deleteLater()

        self.dialogue_editor.set_participants(self.selected_participant_ids())
        self.dialogue_editor.load_lines(legacy_lines)
        self.participant_list.itemChanged.connect(self._sync_dialogue_participants)

    def scene(self) -> Scene:
        """Return the scene with ordered structured dialogue serialized compatibly."""
        return replace(
            super().scene(),
            dialogue=self.dialogue_editor.dialogue_lines(),
        )

    def _sync_dialogue_participants(self, _item: object) -> None:
        self.dialogue_editor.set_participants(self.selected_participant_ids())
