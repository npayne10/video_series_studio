"""Explicit Timed Asset Presence authoring controls for Production Planning."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.governed_reference_plan_source import PersistedGovernedReferencePlanSource
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    AssetPresenceRemoval,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)
from vscs.application.timed_asset_presence_authoring import (
    TimedAssetPresenceAuthoringContext,
    TimedAssetPresenceAuthoringError,
    TimedAssetPresenceAuthoringService,
)


def install_timed_asset_presence_workspace(workspace_class: type[Any]) -> None:
    """Install explicit Phase 20.18.2.3.1 authoring into Production Planning."""
    if getattr(workspace_class, "_timed_asset_presence_workspace_installed", False):
        return

    original_init = workspace_class.__init__
    original_refresh = workspace_class.refresh
    original_selection_changed = workspace_class._selection_changed

    def timed_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.timed_asset_presence_authoring = TimedAssetPresenceAuthoringService(
            self.packages,
            PersistedGovernedReferencePlanSource(self.projects),
        )
        self._build_timed_asset_presence_tab()
        self._load_timed_asset_presence()

    def timed_refresh(self: Any, *args: Any, **kwargs: Any) -> None:
        original_refresh(self, *args, **kwargs)
        if hasattr(self, "timed_presence_table"):
            self._load_timed_asset_presence()

    def timed_selection_changed(self: Any, *args: Any, **kwargs: Any) -> None:
        original_selection_changed(self, *args, **kwargs)
        if hasattr(self, "timed_presence_table"):
            self._load_timed_asset_presence()

    def _build_timed_asset_presence_tab(self: Any) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Timed Asset Presence Authority", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Author exact frame intervals for governed assets. This authority is explicit: "
            "VSCS does not infer entrances, exits, reveals or appearances from Shot prose. "
            "Saving this plan changes governed production authority and makes downstream "
            "Universal/Provider/ProductionTask authority stale until rebuilt.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)

        self.timed_presence_status = QLabel("", group)
        self.timed_presence_status.setWordWrap(True)
        group_layout.addWidget(self.timed_presence_status)

        timing = QHBoxLayout()
        timing.addWidget(QLabel("FPS", group))
        self.timed_presence_fps = QSpinBox(group)
        self.timed_presence_fps.setRange(1, 240)
        self.timed_presence_fps.setValue(24)
        timing.addWidget(self.timed_presence_fps)
        timing.addWidget(QLabel("Frame count", group))
        self.timed_presence_frame_count = QSpinBox(group)
        self.timed_presence_frame_count.setRange(1, 1_000_000)
        self.timed_presence_frame_count.setValue(144)
        timing.addWidget(self.timed_presence_frame_count)
        self.timed_presence_change_frames = QLabel("Change frames: —", group)
        timing.addWidget(self.timed_presence_change_frames)
        timing.addStretch(1)
        group_layout.addLayout(timing)

        self.timed_presence_table = QTableWidget(0, 10, group)
        self.timed_presence_table.setHorizontalHeaderLabels(
            (
                "Use",
                "Asset",
                "Kind",
                "From",
                "Through",
                "Introduction",
                "Removal",
                "Canonical Reference IDs",
                "Required",
                "Notes",
            )
        )
        self.timed_presence_table.horizontalHeader().setStretchLastSection(True)
        self.timed_presence_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        group_layout.addWidget(self.timed_presence_table, 1)

        self.timed_presence_notes = QTextEdit(group)
        self.timed_presence_notes.setMaximumHeight(75)
        self.timed_presence_notes.setPlaceholderText(
            "Optional production note explaining the explicit timing decision."
        )
        group_layout.addWidget(QLabel("Authority review note", group))
        group_layout.addWidget(self.timed_presence_notes)

        actions = QHBoxLayout()
        self.timed_presence_reset_button = QPushButton("Reset from Governed Assets", group)
        self.timed_presence_save_button = QPushButton("Save Timed Presence Authority", group)
        actions.addWidget(self.timed_presence_reset_button)
        actions.addWidget(self.timed_presence_save_button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.insertTab(2, tab, "Timed Asset Presence")

        self.timed_presence_reset_button.clicked.connect(self._reset_timed_asset_presence)
        self.timed_presence_save_button.clicked.connect(self._save_timed_asset_presence)
        self.timed_presence_frame_count.valueChanged.connect(
            self._timed_presence_frame_count_changed
        )
        self.timed_presence_table.itemChanged.connect(
            lambda _item: self._refresh_timed_presence_change_preview()
        )

    def _load_timed_asset_presence(self: Any) -> None:
        shot_id = getattr(self, "_selected_shot_id", None)
        if not shot_id:
            self.timed_presence_table.setRowCount(0)
            self.timed_presence_status.setText("Select a governed Shot.")
            self.timed_presence_save_button.setEnabled(False)
            self.timed_presence_reset_button.setEnabled(False)
            return
        try:
            context = self.timed_asset_presence_authoring.context(
                shot_id,
                frames_per_second=self.timed_presence_fps.value(),
            )
        except TimedAssetPresenceAuthoringError as exc:
            self.timed_presence_table.setRowCount(0)
            self.timed_presence_status.setText(str(exc))
            self.timed_presence_save_button.setEnabled(False)
            self.timed_presence_reset_button.setEnabled(False)
            return
        self._populate_timed_presence_context(context)
        self.timed_presence_reset_button.setEnabled(True)
        self.timed_presence_save_button.setEnabled(True)
        if context.persisted:
            changes = ", ".join(str(value) for value in context.plan.change_frames) or "none"
            self.timed_presence_status.setText(
                "Timed Asset Presence authority is persisted and current for this Production "
                f"Package: {len(context.plan.presences)} presence interval(s); change frames: "
                f"{changes}. Edit only when an explicit human timing decision changes."
            )
        else:
            self.timed_presence_status.setText(
                "No Timed Asset Presence authority is persisted. Full-shot governed-asset "
                "defaults are shown for review only and are NOT authority until you explicitly "
                "save them. Set any governed entrance/reveal/appearance frame before saving."
            )

    def _populate_timed_presence_context(
        self: Any,
        context: TimedAssetPresenceAuthoringContext,
    ) -> None:
        self.timed_presence_table.blockSignals(True)
        try:
            self.timed_presence_fps.setValue(context.frames_per_second)
            self.timed_presence_frame_count.setValue(context.frame_count)
            self.timed_presence_table.setRowCount(len(context.plan.presences))
            maximum = max(0, context.frame_count - 1)
            for row, presence in enumerate(context.plan.presences):
                use_item = QTableWidgetItem()
                use_item.setFlags(use_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                use_item.setCheckState(Qt.CheckState.Checked)
                self.timed_presence_table.setItem(row, 0, use_item)

                asset_item = QTableWidgetItem(presence.asset_id)
                asset_item.setFlags(asset_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.timed_presence_table.setItem(row, 1, asset_item)

                kind_item = QTableWidgetItem(presence.asset_kind.value)
                kind_item.setFlags(kind_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.timed_presence_table.setItem(row, 2, kind_item)

                from_spin = QSpinBox(self.timed_presence_table)
                from_spin.setRange(0, maximum)
                from_spin.setValue(presence.from_frame)
                from_spin.valueChanged.connect(
                    lambda _value: self._refresh_timed_presence_change_preview()
                )
                self.timed_presence_table.setCellWidget(row, 3, from_spin)

                through_spin = QSpinBox(self.timed_presence_table)
                through_spin.setRange(0, maximum)
                through_spin.setValue(presence.through_frame)
                through_spin.valueChanged.connect(
                    lambda _value: self._refresh_timed_presence_change_preview()
                )
                self.timed_presence_table.setCellWidget(row, 4, through_spin)

                introduction = QComboBox(self.timed_presence_table)
                for introduction_value in AssetPresenceIntroduction:
                    introduction.addItem(introduction_value.value, introduction_value.value)
                introduction.setCurrentIndex(
                    max(0, introduction.findData(presence.introduction.value))
                )
                introduction.currentIndexChanged.connect(
                    lambda _index: self._refresh_timed_presence_change_preview()
                )
                self.timed_presence_table.setCellWidget(row, 5, introduction)

                removal = QComboBox(self.timed_presence_table)
                for removal_value in AssetPresenceRemoval:
                    removal.addItem(removal_value.value, removal_value.value)
                removal.setCurrentIndex(max(0, removal.findData(presence.removal.value)))
                removal.currentIndexChanged.connect(
                    lambda _index: self._refresh_timed_presence_change_preview()
                )
                self.timed_presence_table.setCellWidget(row, 6, removal)

                refs_item = QTableWidgetItem(", ".join(presence.canonical_reference_ids))
                self.timed_presence_table.setItem(row, 7, refs_item)

                required_item = QTableWidgetItem()
                required_item.setFlags(required_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                required_item.setCheckState(
                    Qt.CheckState.Checked if presence.required else Qt.CheckState.Unchecked
                )
                self.timed_presence_table.setItem(row, 8, required_item)

                self.timed_presence_table.setItem(row, 9, QTableWidgetItem(presence.notes))
        finally:
            self.timed_presence_table.blockSignals(False)
        self._refresh_timed_presence_change_preview()

    def _reset_timed_asset_presence(self: Any) -> None:
        shot_id = getattr(self, "_selected_shot_id", None)
        if not shot_id:
            return
        try:
            context = self.timed_asset_presence_authoring.default_context(
                shot_id,
                frames_per_second=self.timed_presence_fps.value(),
            )
        except TimedAssetPresenceAuthoringError as exc:
            QMessageBox.warning(self, "Timed Asset Presence", str(exc))
            return
        self._populate_timed_presence_context(context)
        self.timed_presence_status.setText(
            "Full-shot governed-asset defaults restored in the editor only. Nothing has been "
            "persisted. Explicitly set timed entrances/exits before Save Timed Presence Authority."
        )

    def _save_timed_asset_presence(self: Any) -> None:
        shot_id = getattr(self, "_selected_shot_id", None)
        if not shot_id:
            return
        try:
            plan = self._timed_presence_plan_from_editor()
            self.timed_asset_presence_authoring.persist(
                shot_id,
                plan,
                production_notes=self.timed_presence_notes.toPlainText(),
            )
        except (TimedAssetPresenceAuthoringError, TimedAssetPresenceError, ValueError) as exc:
            QMessageBox.warning(self, "Timed Asset Presence", str(exc))
            return
        self.refresh()

    def _timed_presence_plan_from_editor(self: Any) -> TimedAssetPresencePlan:
        shot_id = str(getattr(self, "_selected_shot_id", "") or "").strip().upper()
        if not shot_id:
            raise TimedAssetPresenceAuthoringError("Select a governed Shot first")
        presences: list[TimedAssetPresence] = []
        for row in range(self.timed_presence_table.rowCount()):
            use_item = self.timed_presence_table.item(row, 0)
            if use_item is None or use_item.checkState() is not Qt.CheckState.Checked:
                continue
            asset_item = self.timed_presence_table.item(row, 1)
            kind_item = self.timed_presence_table.item(row, 2)
            refs_item = self.timed_presence_table.item(row, 7)
            required_item = self.timed_presence_table.item(row, 8)
            notes_item = self.timed_presence_table.item(row, 9)
            from_spin = self.timed_presence_table.cellWidget(row, 3)
            through_spin = self.timed_presence_table.cellWidget(row, 4)
            introduction = self.timed_presence_table.cellWidget(row, 5)
            removal = self.timed_presence_table.cellWidget(row, 6)
            if not isinstance(from_spin, QSpinBox) or not isinstance(through_spin, QSpinBox):
                raise TimedAssetPresenceAuthoringError("Timed presence frame editor is unavailable")
            if not isinstance(introduction, QComboBox) or not isinstance(removal, QComboBox):
                raise TimedAssetPresenceAuthoringError(
                    "Timed presence transition editor is unavailable"
                )
            asset_id = asset_item.text().strip() if asset_item is not None else ""
            kind = kind_item.text().strip() if kind_item is not None else ""
            refs = tuple(
                value.strip()
                for value in (refs_item.text() if refs_item is not None else "").split(",")
                if value.strip()
            )
            presences.append(
                TimedAssetPresence(
                    asset_id=asset_id,
                    asset_kind=TimedAssetKind(kind),
                    from_frame=from_spin.value(),
                    through_frame=through_spin.value(),
                    introduction=AssetPresenceIntroduction(str(introduction.currentData())),
                    removal=AssetPresenceRemoval(str(removal.currentData())),
                    canonical_reference_ids=refs,
                    required=bool(
                        required_item is not None
                        and required_item.checkState() is Qt.CheckState.Checked
                    ),
                    notes=notes_item.text() if notes_item is not None else "",
                )
            )
        if not presences:
            raise TimedAssetPresenceAuthoringError(
                "Timed Asset Presence authority requires at least one enabled asset"
            )
        return TimedAssetPresencePlan(
            shot_id=shot_id,
            frames_per_second=self.timed_presence_fps.value(),
            frame_count=self.timed_presence_frame_count.value(),
            presences=tuple(presences),
        )

    def _timed_presence_frame_count_changed(self: Any, frame_count: int) -> None:
        maximum = max(0, frame_count - 1)
        for row in range(self.timed_presence_table.rowCount()):
            for column in (3, 4):
                widget = self.timed_presence_table.cellWidget(row, column)
                if isinstance(widget, QSpinBox):
                    widget.setMaximum(maximum)
        self._refresh_timed_presence_change_preview()

    def _refresh_timed_presence_change_preview(self: Any) -> None:
        if not hasattr(self, "timed_presence_change_frames"):
            return
        try:
            plan = self._timed_presence_plan_from_editor()
        except (TimedAssetPresenceAuthoringError, TimedAssetPresenceError, ValueError):
            self.timed_presence_change_frames.setText("Change frames: invalid draft")
            return
        changes = ", ".join(str(value) for value in plan.change_frames) or "none"
        self.timed_presence_change_frames.setText(f"Change frames: {changes}")

    workspace_class.__init__ = timed_init
    workspace_class.refresh = timed_refresh
    workspace_class._selection_changed = timed_selection_changed
    workspace_class._build_timed_asset_presence_tab = _build_timed_asset_presence_tab
    workspace_class._load_timed_asset_presence = _load_timed_asset_presence
    workspace_class._populate_timed_presence_context = _populate_timed_presence_context
    workspace_class._reset_timed_asset_presence = _reset_timed_asset_presence
    workspace_class._save_timed_asset_presence = _save_timed_asset_presence
    workspace_class._timed_presence_plan_from_editor = _timed_presence_plan_from_editor
    workspace_class._timed_presence_frame_count_changed = _timed_presence_frame_count_changed
    workspace_class._refresh_timed_presence_change_preview = _refresh_timed_presence_change_preview
    workspace_class._timed_asset_presence_workspace_installed = True
