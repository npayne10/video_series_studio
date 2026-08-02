"""Responsive scene editor with structured participant-aware dialogue controls."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.scene_editor_dialog import SceneEditorDialog
from vscs.presentation.widgets.dialogue_editor import DialogueEditorWidget


class StructuredSceneEditorDialog(SceneEditorDialog):
    """Provide structured dialogue in a responsive, sectioned scene editor."""

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

        self._make_responsive()
        self._configure_tab_order()

    def scene(self) -> Scene:
        """Return the scene with ordered structured dialogue serialized compatibly."""
        return replace(
            super().scene(),
            dialogue=self.dialogue_editor.dialogue_lines(),
        )

    def _make_responsive(self) -> None:
        """Place the long editor body in a scroll area with fixed actions below it."""
        root = self.layout()
        if not isinstance(root, QVBoxLayout):
            return

        intro_item = root.takeAt(0)
        form_item = root.takeAt(0)
        intro = intro_item.widget() if intro_item is not None else None
        form = form_item.layout() if form_item is not None else None
        if intro is None or not isinstance(form, QFormLayout):
            self._restore_layout_item(root, intro_item)
            self._restore_layout_item(root, form_item)
            return

        self._insert_section_headers(form)

        self.scroll_content = QWidget(self)
        self.scroll_content.setObjectName("sceneEditorScrollContent")
        content_layout = QVBoxLayout(self.scroll_content)
        content_layout.setContentsMargins(18, 14, 18, 18)
        content_layout.setSpacing(12)
        content_layout.addWidget(intro)
        content_layout.addLayout(form)
        content_layout.addStretch(1)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("sceneEditorScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setWidget(self.scroll_content)
        self.scroll_area.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        root.insertWidget(0, self.scroll_area, 1)

        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
        self.setMinimumSize(640, 480)
        self.resize(820, 720)

    def _insert_section_headers(self, form: QFormLayout) -> None:
        """Insert visual landmarks while preserving the existing field order."""
        sections = (
            (10, "Production", "Timing, transition and production estimates."),
            (9, "Assets", "Select every production asset required by the scene."),
            (7, "Cast & Dialogue", "Choose participants and structure their dialogue."),
            (4, "Story Context", "Describe where the scene occurs and what changes."),
            (0, "General", "Scene identity and ordering within the episode."),
        )
        for row, title, description in sections:
            form.insertRow(row, self._section_header(title, description))
        form.setVerticalSpacing(10)
        form.setHorizontalSpacing(16)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    @staticmethod
    def _section_header(title: str, description: str) -> QWidget:
        container = QWidget()
        container.setObjectName(f"sceneSection{title.replace(' ', '')}")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 14, 0, 4)
        layout.setSpacing(2)

        heading = QLabel(title)
        heading.setStyleSheet("font-size: 15px; font-weight: 600;")
        details = QLabel(description)
        details.setWordWrap(True)
        details.setStyleSheet("color: palette(mid);")

        layout.addWidget(heading)
        layout.addWidget(details)
        return container

    def _configure_tab_order(self) -> None:
        """Keep keyboard navigation aligned with the visual workflow."""
        ordered = (
            self.scene_name_edit,
            self.episode_id_edit,
            self.sequence_spin,
            self.heading_edit,
            self.location_combo,
            self.summary_edit,
            self.participant_search,
            self.participant_list,
            self.dialogue_editor,
            self.asset_search,
            self.asset_list,
            self.time_of_day_edit,
            self.transition_combo,
            self.duration_spin,
            self.save_button,
        )
        for current, following in zip(ordered, ordered[1:], strict=True):
            self.setTabOrder(current, following)

    @staticmethod
    def _restore_layout_item(root: QVBoxLayout, item: object) -> None:
        if item is None:
            return
        widget = item.widget() if hasattr(item, "widget") else None
        layout = item.layout() if hasattr(item, "layout") else None
        if widget is not None:
            root.insertWidget(0, widget)
        elif isinstance(layout, QLayout):
            root.insertLayout(0, layout)

    def _sync_dialogue_participants(self, _item: object) -> None:
        self.dialogue_editor.set_participants(self.selected_participant_ids())
