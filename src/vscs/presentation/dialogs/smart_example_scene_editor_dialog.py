"""Scene Editor variant with reusable smart field examples."""

from __future__ import annotations

from PySide6.QtCore import QStringListModel, Qt
from PySide6.QtWidgets import QCompleter, QLabel, QWidget

from vscs.application.ssie import Scene
from vscs.domain.assets import Asset
from vscs.presentation.dialogs.workflow_scene_editor_dialog import (
    WorkflowSceneEditorDialog,
)
from vscs.presentation.examples import ExampleContext, ExampleProvider


class SmartExampleSceneEditorDialog(WorkflowSceneEditorDialog):
    """Add practical examples, empty states and adaptive suggestions."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        **kwargs: object,
    ) -> None:
        location_assets = self._asset_tuple(kwargs.get("location_assets"))
        participant_assets = self._asset_tuple(kwargs.get("participant_assets"))
        required_assets = self._asset_tuple(kwargs.get("required_assets"))
        self.example_provider = ExampleProvider(
            context=ExampleContext(
                locations=tuple(asset.name for asset in location_assets),
                characters=tuple(asset.name for asset in participant_assets),
                assets=tuple(asset.name for asset in required_assets),
            )
        )
        super().__init__(scene, parent, **kwargs)
        self._install_smart_examples()

    @staticmethod
    def _asset_tuple(value: object) -> tuple[Asset, ...]:
        if not isinstance(value, tuple):
            return ()
        return tuple(asset for asset in value if isinstance(asset, Asset))

    def _install_smart_examples(self) -> None:
        self.scene_name_edit.setPlaceholderText(self.example_provider.placeholder("scene.name"))
        self.heading_edit.setPlaceholderText(self.example_provider.placeholder("scene.heading"))
        self.summary_edit.setPlaceholderText(self.example_provider.placeholder("scene.summary"))
        self.dialogue_editor.text_edit.setPlaceholderText(
            self.example_provider.placeholder("scene.dialogue")
        )

        if not self._participant_assets:
            self.participant_help.setText(self.example_provider.empty_state("scene.participants"))
        if not self._required_assets:
            self.asset_help.setText(self.example_provider.empty_state("scene.required_assets"))
        if not self.selected_participant_ids():
            self.dialogue_editor.help_label.setText(
                self.example_provider.empty_state("scene.dialogue")
            )

        form = self._find_form_layout()
        if form is not None:
            tips = (
                (self.production_estimate_label, "scene.duration"),
                (self.summary_edit, "scene.summary"),
                (self.heading_edit, "scene.heading"),
                (self.scene_name_edit, "scene.name"),
            )
            for widget, topic_id in tips:
                row = self._row_for_widget(form, widget)
                if row >= 0:
                    form.insertRow(row + 1, self._tip_label(topic_id))

        self.heading_completion_model = QStringListModel(self)
        self.heading_completer = QCompleter(self.heading_completion_model, self)
        self.heading_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.heading_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.heading_edit.setCompleter(self.heading_completer)
        self.heading_edit.textEdited.connect(self._update_heading_suggestions)

    def _tip_label(self, topic_id: str) -> QLabel:
        label = QLabel(self.example_provider.inline_tip(topic_id), self)
        label.setObjectName(f"smartExampleTip_{topic_id.replace('.', '_')}")
        label.setWordWrap(True)
        label.setStyleSheet("font-style: italic; color: palette(mid);")
        label.setAccessibleName(f"Entry guidance for {topic_id}")
        return label

    def _update_heading_suggestions(self, text: str) -> None:
        suggestions = self.example_provider.adaptive("scene.heading", text)
        self.heading_completion_model.setStringList(list(suggestions))
        if suggestions:
            self.heading_completer.complete()
