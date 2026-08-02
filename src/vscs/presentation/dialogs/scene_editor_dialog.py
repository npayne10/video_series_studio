"""Dialog for creating and editing structured SSIE scenes."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.application.ssie import Scene, SceneTransition
from vscs.domain.assets import Asset

_HEADER_ROLE = Qt.ItemDataRole.UserRole + 2
_SEARCH_ROLE = Qt.ItemDataRole.UserRole + 1


class SceneEditorDialog(QDialog):
    """Collect clear, validated scene data suitable for the SSIE planner."""

    def __init__(
        self,
        scene: Scene | None = None,
        parent: QWidget | None = None,
        *,
        default_episode_id: str = "EP-001",
        suggested_sequence: int = 1,
        scene_id_factory: Callable[[str, int], str] | None = None,
        location_assets: tuple[Asset, ...] = (),
        participant_assets: tuple[Asset, ...] = (),
        required_assets: tuple[Asset, ...] = (),
    ) -> None:
        super().__init__(parent)
        self._editing = scene is not None
        self._scene_id_factory = scene_id_factory or self._default_scene_id
        self._location_assets = location_assets
        self._participant_assets = participant_assets
        self._required_assets = required_assets
        self.setWindowTitle("Edit Scene" if self._editing else "New Scene")
        self.resize(760, 900)

        intro = QLabel(
            "Create the story-level scene information used by SSIE. "
            "Fields marked * are required."
        )
        intro.setWordWrap(True)

        self.scene_id_edit = QLineEdit()
        self.scene_id_edit.setReadOnly(True)
        self.scene_id_edit.setToolTip(
            "Internal VSCS identity. It is generated automatically and cannot be renamed."
        )
        self.scene_name_edit = QLineEdit()
        self.scene_name_edit.setPlaceholderText("Example: Emergence at Xorix")
        self.scene_name_edit.setToolTip(
            "A short human-readable name shown in the Story Browser."
        )
        self.episode_id_edit = QLineEdit(default_episode_id)
        self.episode_id_edit.setPlaceholderText("EP-001")
        self.episode_id_edit.setToolTip(
            "Episode identity containing this scene, for example EP-001."
        )
        self.sequence_spin = QSpinBox()
        self.sequence_spin.setRange(1, 9999)
        self.sequence_spin.setValue(suggested_sequence)
        self.sequence_spin.setToolTip("The scene's order within the episode.")
        self.heading_edit = QLineEdit()
        self.heading_edit.setPlaceholderText("INT. MAURITANIA BRIDGE - NIGHT")
        self.heading_edit.setToolTip(
            "Screenplay-style heading describing interior/exterior, location and time."
        )

        self.location_combo = QComboBox()
        self.location_combo.setObjectName("sceneLocationSelector")
        self.location_combo.setEditable(True)
        self.location_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.location_combo.setToolTip(
            "Search for and select a canonical location or environment asset. "
            "The scene stores the asset ID."
        )
        self._populate_locations()

        self.location_help = QLabel()
        self.location_help.setWordWrap(True)
        self.location_help.setObjectName("sceneLocationHelp")
        if location_assets:
            self.location_help.setText(
                "Choose a location by name or asset ID. Only location and environment "
                "assets are shown."
            )
        else:
            self.location_help.setText(
                "No location assets are available. Create a Location or Environment "
                "asset in Asset Manager, then reopen this dialog."
            )
            self.location_help.setStyleSheet("color: #8a5a00;")

        self.summary_edit = QPlainTextEdit()
        self.summary_edit.setPlaceholderText(
            "Describe what changes in this scene and why it matters."
        )
        self.summary_edit.setToolTip(
            "A concise narrative summary used by SSIE to infer scene purpose and shots."
        )

        self.participant_search = QLineEdit()
        self.participant_search.setObjectName("sceneParticipantSearch")
        self.participant_search.setPlaceholderText(
            "Search characters by name or asset ID..."
        )
        self.participant_search.setClearButtonEnabled(True)
        self.participant_search.setToolTip(
            "Filter the available character assets, then tick everyone present in the scene."
        )
        self.participant_list = QListWidget()
        self.participant_list.setObjectName("sceneParticipantSelector")
        self.participant_list.setAlternatingRowColors(True)
        self.participant_list.setMinimumHeight(130)
        self.participant_help = QLabel()
        self.participant_help.setObjectName("sceneParticipantHelp")
        self.participant_help.setWordWrap(True)
        self._populate_participants()

        self.dialogue_edit = QPlainTextEdit()

        self.asset_search = QLineEdit()
        self.asset_search.setObjectName("sceneRequiredAssetSearch")
        self.asset_search.setPlaceholderText("Search assets by name, ID or category...")
        self.asset_search.setClearButtonEnabled(True)
        self.asset_search.setToolTip(
            "Filter production assets, then tick everything required to stage this scene."
        )
        self.asset_list = QListWidget()
        self.asset_list.setObjectName("sceneRequiredAssetSelector")
        self.asset_list.setAlternatingRowColors(True)
        self.asset_list.setMinimumHeight(170)
        self.asset_help = QLabel()
        self.asset_help.setObjectName("sceneRequiredAssetHelp")
        self.asset_help.setWordWrap(True)
        self._populate_required_assets()

        self.time_of_day_edit = QLineEdit()
        self.transition_combo = QComboBox()
        for transition in SceneTransition:
            self.transition_combo.addItem(
                transition.value.replace("_", " ").title(),
                transition,
            )
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 36000.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setValue(30.0)

        self.validation_label = QLabel()
        self.validation_label.setObjectName("sceneValidationMessage")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("color: #b00020;")

        location_layout = QVBoxLayout()
        location_layout.setContentsMargins(0, 0, 0, 0)
        location_layout.addWidget(self.location_combo)
        location_layout.addWidget(self.location_help)

        participant_layout = QVBoxLayout()
        participant_layout.setContentsMargins(0, 0, 0, 0)
        participant_layout.addWidget(self.participant_search)
        participant_layout.addWidget(self.participant_list)
        participant_layout.addWidget(self.participant_help)

        asset_layout = QVBoxLayout()
        asset_layout.setContentsMargins(0, 0, 0, 0)
        asset_layout.addWidget(self.asset_search)
        asset_layout.addWidget(self.asset_list)
        asset_layout.addWidget(self.asset_help)

        form = QFormLayout()
        form.addRow("Scene ID", self.scene_id_edit)
        form.addRow("Scene name *", self.scene_name_edit)
        form.addRow("Episode ID *", self.episode_id_edit)
        form.addRow("Sequence *", self.sequence_spin)
        form.addRow("Heading *", self.heading_edit)
        form.addRow("Location *", location_layout)
        form.addRow("Summary *", self.summary_edit)
        form.addRow("Participants", participant_layout)
        form.addRow("Dialogue (one line per utterance)", self.dialogue_edit)
        form.addRow("Required assets", asset_layout)
        form.addRow("Time of day", self.time_of_day_edit)
        form.addRow("Transition", self.transition_combo)
        form.addRow("Estimated duration (seconds)", self.duration_spin)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setText("Save Scene")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addWidget(self.validation_label)
        layout.addWidget(self.buttons)

        self.scene_name_edit.textChanged.connect(self._validate)
        self.episode_id_edit.textChanged.connect(self._identity_changed)
        self.sequence_spin.valueChanged.connect(self._identity_changed)
        self.heading_edit.textChanged.connect(self._validate)
        self.location_combo.currentIndexChanged.connect(self._validate)
        self.location_combo.editTextChanged.connect(self._validate)
        self.summary_edit.textChanged.connect(self._validate)
        self.participant_search.textChanged.connect(self._filter_participants)
        self.participant_list.itemChanged.connect(self._participants_changed)
        self.asset_search.textChanged.connect(self._filter_required_assets)
        self.asset_list.itemChanged.connect(self._required_assets_changed)

        if scene is not None:
            self._load(scene)
        else:
            self._refresh_generated_id()
            self._update_participant_help()
            self._update_asset_help()
        self._validate()
        self.scene_name_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def scene(self) -> Scene:
        """Return the structured scene represented by the form."""
        return Scene(
            scene_id=self.scene_id_edit.text().strip(),
            episode_id=self.episode_id_edit.text().strip(),
            sequence_number=self.sequence_spin.value(),
            heading=self.heading_edit.text().strip(),
            location_asset_id=self.selected_location_id(),
            summary=self.summary_edit.toPlainText().strip(),
            participant_asset_ids=self.selected_participant_ids(),
            dialogue=self._lines(self.dialogue_edit.toPlainText()),
            required_asset_ids=self.selected_required_asset_ids(),
            time_of_day=self.time_of_day_edit.text().strip() or None,
            transition_in=self.transition_combo.currentData(),
            estimated_duration_seconds=self.duration_spin.value(),
            scene_name=self.scene_name_edit.text().strip(),
        )

    def selected_location_id(self) -> str:
        """Return the canonical ID selected by name or exact asset ID."""
        selected = self.location_combo.currentData()
        if isinstance(selected, str) and selected:
            return selected
        query = self.location_combo.currentText().strip()
        for asset in self._location_assets:
            if query.casefold() in {asset.asset_id.casefold(), asset.name.casefold()}:
                return asset.asset_id
        return ""

    def selected_participant_ids(self) -> tuple[str, ...]:
        """Return checked participant IDs in stable display order without duplicates."""
        return self._checked_ids(self.participant_list)

    def selected_required_asset_ids(self) -> tuple[str, ...]:
        """Return checked production asset IDs without category headers or duplicates."""
        return self._checked_ids(self.asset_list)

    def _populate_locations(self) -> None:
        self.location_combo.clear()
        self.location_combo.addItem("Select a location...", "")
        for asset in sorted(
            self._location_assets,
            key=lambda item: (item.name.casefold(), item.asset_id),
        ):
            self.location_combo.addItem(
                f"{asset.name}  —  {asset.asset_id}",
                asset.asset_id,
            )
        completer = self.location_combo.completer()
        if completer is not None:
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)

    def _populate_participants(self) -> None:
        self.participant_list.clear()
        for asset in sorted(
            self._participant_assets,
            key=lambda item: (item.name.casefold(), item.asset_id),
        ):
            item = self._asset_item(asset)
            self.participant_list.addItem(item)
        self._update_participant_help()

    def _populate_required_assets(self) -> None:
        self.asset_list.clear()
        grouped: dict[str, list[Asset]] = {}
        for asset in self._required_assets:
            grouped.setdefault(asset.category.value, []).append(asset)
        for category in sorted(grouped):
            header = QListWidgetItem(category.replace("_", " ").title())
            header.setData(_HEADER_ROLE, True)
            header.setData(_SEARCH_ROLE, category.casefold())
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            self.asset_list.addItem(header)
            for asset in sorted(
                grouped[category],
                key=lambda item: (item.name.casefold(), item.asset_id),
            ):
                self.asset_list.addItem(self._asset_item(asset, category))
        self._update_asset_help()

    def _load(self, scene: Scene) -> None:
        self.scene_id_edit.setText(scene.scene_id)
        self.scene_name_edit.setText(scene.scene_name or scene.heading)
        self.episode_id_edit.setText(scene.episode_id)
        self.sequence_spin.setValue(scene.sequence_number)
        self.heading_edit.setText(scene.heading)
        self._select_location(scene.location_asset_id)
        self.summary_edit.setPlainText(scene.summary)
        self._select_ids(
            self.participant_list,
            scene.participant_asset_ids,
            "Unavailable character",
        )
        self.dialogue_edit.setPlainText("\n".join(scene.dialogue))
        self._select_ids(
            self.asset_list,
            scene.required_asset_ids,
            "Unavailable asset",
        )
        self.time_of_day_edit.setText(scene.time_of_day or "")
        self.transition_combo.setCurrentIndex(
            self.transition_combo.findData(scene.transition_in)
        )
        self.duration_spin.setValue(scene.estimated_duration_seconds or 30.0)
        self._update_participant_help()
        self._update_asset_help()

    def _select_location(self, asset_id: str) -> None:
        index = self.location_combo.findData(asset_id)
        if index >= 0:
            self.location_combo.setCurrentIndex(index)
            return
        if asset_id:
            self.location_combo.addItem(f"Unavailable asset — {asset_id}", asset_id)
            self.location_combo.setCurrentIndex(self.location_combo.count() - 1)
            self.location_help.setText(
                "This scene references a location that is not currently present in Asset "
                "Manager. Select another location or restore the missing asset."
            )
            self.location_help.setStyleSheet("color: #b00020;")

    def _select_ids(
        self,
        widget: QListWidget,
        selected_ids: tuple[str, ...],
        unavailable_label: str,
    ) -> None:
        available: set[str] = set()
        for index in range(widget.count()):
            item = widget.item(index)
            asset_id = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(asset_id, str):
                continue
            available.add(asset_id)
            if asset_id in selected_ids:
                item.setCheckState(Qt.CheckState.Checked)
        for asset_id in selected_ids:
            if asset_id in available:
                continue
            item = QListWidgetItem(f"{unavailable_label} — {asset_id}")
            item.setData(Qt.ItemDataRole.UserRole, asset_id)
            item.setData(_SEARCH_ROLE, asset_id.casefold())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setToolTip(
                "This asset is referenced by the scene but is missing from Asset Manager."
            )
            widget.addItem(item)

    def _filter_participants(self, query: str) -> None:
        self._filter_asset_list(self.participant_list, query, grouped=False)

    def _filter_required_assets(self, query: str) -> None:
        self._filter_asset_list(self.asset_list, query, grouped=True)

    def _filter_asset_list(
        self,
        widget: QListWidget,
        query: str,
        *,
        grouped: bool,
    ) -> None:
        normalized = query.strip().casefold()
        visible_by_header: dict[int, bool] = {}
        current_header = -1
        for index in range(widget.count()):
            item = widget.item(index)
            if item.data(_HEADER_ROLE):
                current_header = index
                visible_by_header[index] = False
                continue
            searchable = item.data(_SEARCH_ROLE)
            matches = not normalized or (
                isinstance(searchable, str) and normalized in searchable
            )
            item.setHidden(not matches)
            if grouped and matches and current_header >= 0:
                visible_by_header[current_header] = True
        if grouped:
            for index, visible in visible_by_header.items():
                widget.item(index).setHidden(not visible)

    def _participants_changed(self, _item: QListWidgetItem) -> None:
        self._update_participant_help()

    def _required_assets_changed(self, _item: QListWidgetItem) -> None:
        self._update_asset_help()

    def _update_participant_help(self) -> None:
        count = len(self.selected_participant_ids())
        if not self._participant_assets and self.participant_list.count() == 0:
            self.participant_help.setText(
                "No character assets are available. Create Character assets in Asset "
                "Manager, then reopen this dialog."
            )
            self.participant_help.setStyleSheet("color: #8a5a00;")
            return
        label = "participant" if count == 1 else "participants"
        self.participant_help.setText(
            f"{count} {label} selected. Tick every character who appears in this scene."
        )
        self.participant_help.setStyleSheet("")

    def _update_asset_help(self) -> None:
        count = len(self.selected_required_asset_ids())
        if not self._required_assets and self.asset_list.count() == 0:
            self.asset_help.setText(
                "No production assets are available. Create assets in Asset Manager, "
                "then reopen this dialog."
            )
            self.asset_help.setStyleSheet("color: #8a5a00;")
            return
        label = "asset" if count == 1 else "assets"
        self.asset_help.setText(
            f"{count} required {label} selected. Items are grouped by asset category."
        )
        self.asset_help.setStyleSheet("")

    def _identity_changed(self) -> None:
        if not self._editing:
            self._refresh_generated_id()
        self._validate()

    def _refresh_generated_id(self) -> None:
        self.scene_id_edit.setText(
            self._scene_id_factory(
                self.episode_id_edit.text().strip(),
                self.sequence_spin.value(),
            )
        )

    def _validate(self) -> None:
        missing: list[str] = []
        if not self.scene_name_edit.text().strip():
            missing.append("scene name")
        if not self.episode_id_edit.text().strip():
            missing.append("episode ID")
        if not self.heading_edit.text().strip():
            missing.append("heading")
        if not self.selected_location_id():
            missing.append("location")
        if not self.summary_edit.toPlainText().strip():
            missing.append("summary")
        valid = not missing and bool(self.scene_id_edit.text().strip())
        self.save_button.setEnabled(valid)
        self.validation_label.setText(
            "Complete the required fields: " + ", ".join(missing) + "."
            if missing
            else ""
        )

    @staticmethod
    def _asset_item(asset: Asset, category: str = "") -> QListWidgetItem:
        item = QListWidgetItem(f"{asset.name}  —  {asset.asset_id}")
        item.setData(Qt.ItemDataRole.UserRole, asset.asset_id)
        searchable = f"{asset.name} {asset.asset_id} {category}".casefold()
        item.setData(_SEARCH_ROLE, searchable)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        return item

    @staticmethod
    def _checked_ids(widget: QListWidget) -> tuple[str, ...]:
        selected: list[str] = []
        for index in range(widget.count()):
            item = widget.item(index)
            if item.checkState() is not Qt.CheckState.Checked:
                continue
            asset_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(asset_id, str) and asset_id and asset_id not in selected:
                selected.append(asset_id)
        return tuple(selected)

    @staticmethod
    def _default_scene_id(episode_id: str, sequence_number: int) -> str:
        episode = episode_id.strip().upper() or "EP-001"
        return f"{episode}-SCN-{sequence_number:03d}"

    @staticmethod
    def _lines(value: str) -> tuple[str, ...]:
        return tuple(line.strip() for line in value.splitlines() if line.strip())
