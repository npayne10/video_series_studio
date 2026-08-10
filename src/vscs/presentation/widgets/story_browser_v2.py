"""Production-first Story Browser v2 workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectNotOpenError
from vscs.application.story import StoryService, StoryServiceError
from vscs.application.story.hierarchy import (
    StoryHierarchy,
    StoryItemStatus,
    StoryNode,
    StoryNodeKind,
    build_story_hierarchy,
)

from .story_browser import StoryBrowserWidget


class StoryBrowserV2Widget(StoryBrowserWidget):
    """Central production navigator for containers, scenes, shots and readiness."""

    def __init__(
        self,
        stories: StoryService,
        assets: AssetService,
        parent: QWidget | None = None,
    ) -> None:
        self._v2_ready = False
        self._hierarchy: StoryHierarchy | None = None
        super().__init__(stories, assets, parent)
        self.setObjectName("storyBrowserV2")
        self._install_dashboard()
        self._install_filters()
        self.tree.setHeaderLabels(("Production Item", "Type", "Status", "Duration", "Assets"))
        self.tree.setSortingEnabled(False)
        self.tree.setUniformRowHeights(True)
        self.tree.currentItemChanged.connect(self._update_action_state)
        self._v2_ready = True
        self.refresh()

    def _install_dashboard(self) -> None:
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            raise RuntimeError("Story Browser root layout must be vertical.")

        frame = QFrame(self)
        frame.setObjectName("storyProductionDashboard")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        grid = QGridLayout(frame)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(24)

        title = QLabel("Production Overview", frame)
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        grid.addWidget(title, 0, 0, 1, 4)

        self.dashboard_labels: dict[str, QLabel] = {}
        metrics = (
            ("containers", "Containers"),
            ("scenes", "Scenes"),
            ("shots", "Shots"),
            ("planned", "Planned"),
            ("ready", "Ready"),
            ("draft", "Draft"),
            ("duration", "Duration"),
            ("assets", "Assets"),
        )
        for index, (key, label) in enumerate(metrics):
            value = QLabel("0", frame)
            value.setObjectName(f"storyDashboard{key.title()}")
            value.setStyleSheet("font-size: 15px; font-weight: 600;")
            caption = QLabel(label, frame)
            column = index % 4
            row = 1 + (index // 4) * 2
            grid.addWidget(value, row, column)
            grid.addWidget(caption, row + 1, column)
            self.dashboard_labels[key] = value
        layout.insertWidget(0, frame)

    def _install_filters(self) -> None:
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            raise RuntimeError("Story Browser root layout must be vertical.")

        row = QHBoxLayout()
        row.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit(self)
        self.search_edit.setObjectName("storySearch")
        self.search_edit.setPlaceholderText(
            "Search production, container, scene, shot or asset ID..."
        )
        self.search_edit.setClearButtonEnabled(True)
        row.addWidget(self.search_edit, 1)

        row.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox(self)
        self.status_filter.setObjectName("storyStatusFilter")
        self.status_filter.addItem("All statuses", None)
        for status in StoryItemStatus:
            self.status_filter.addItem(status.label, status)
        row.addWidget(self.status_filter)

        self.search_edit.textChanged.connect(self._apply_filters)
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        layout.insertLayout(1, row)

    def refresh(self) -> None:
        """Reload the production hierarchy and dashboard."""
        if not self._v2_ready:
            super().refresh()
            return
        selected = self._selected_identity()
        self.tree.clear()
        self.details.clear()
        try:
            scenes = self.stories.list_scenes()
        except ProjectNotOpenError:
            self._set_enabled(False)
            self.empty_label.show()
            return
        except StoryServiceError as exc:
            self.empty_label.setText(str(exc))
            self.empty_label.show()
            return

        plans = {
            scene.scene_id: plan
            for scene in scenes
            if (plan := self.stories.plan(scene.scene_id)) is not None
        }
        self._hierarchy = build_story_hierarchy(scenes, plans)
        self._update_dashboard(self._hierarchy)
        self._set_enabled(True)
        self.empty_label.setVisible(not scenes)
        self.empty_label.setText(
            "No story material yet. Use New Scene to start the production hierarchy."
        )
        for root in self._hierarchy.roots:
            item = self._append_node(None, root)
            if selected == (root.kind.value, root.node_id):
                self.tree.setCurrentItem(item)
        self.tree.expandToDepth(3)
        self._restore_selection(selected)
        self._apply_filters()
        if self.tree.currentItem() is None and self.tree.topLevelItemCount():
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._update_action_state()

    def _append_node(
        self,
        parent: QTreeWidgetItem | None,
        node: StoryNode,
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem(
            (
                node.label,
                node.kind.value.replace("_", " ").title(),
                node.status.label,
                self._duration(node.duration_seconds),
                str(node.asset_count) if node.asset_count else "—",
            )
        )
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            (node.kind.value, node.node_id, node.scene_id, node.shot_id),
        )
        item.setToolTip(0, f"{node.kind.value.title()}: {node.node_id}")
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        for child in node.children:
            self._append_node(item, child)
        return item

    def _update_dashboard(self, hierarchy: StoryHierarchy) -> None:
        stats = hierarchy.statistics
        values = {
            "containers": str(stats.containers),
            "scenes": str(stats.scenes),
            "shots": str(stats.shots),
            "planned": str(stats.planned_scenes),
            "ready": str(stats.ready_scenes),
            "draft": str(stats.draft_scenes),
            "duration": self._duration(stats.duration_seconds),
            "assets": str(stats.referenced_assets),
        }
        for key, value in values.items():
            self.dashboard_labels[key].setText(value)

    def _apply_filters(self, *_args: object) -> None:
        query = self.search_edit.text().strip().casefold()
        wanted = self.status_filter.currentData()
        for index in range(self.tree.topLevelItemCount()):
            self._filter_item(self.tree.topLevelItem(index), query, wanted)

    def _filter_item(
        self,
        item: QTreeWidgetItem,
        query: str,
        wanted: StoryItemStatus | None,
    ) -> bool:
        child_match = False
        for index in range(item.childCount()):
            child_match = self._filter_item(item.child(index), query, wanted) or child_match
        data = item.data(0, Qt.ItemDataRole.UserRole)
        text = " ".join(item.text(column) for column in range(item.columnCount()))
        if data:
            text += " " + " ".join(str(value) for value in data if value)
        query_match = not query or query in text.casefold()
        status_match = wanted is None or item.text(2) == wanted.label
        visible = child_match or (query_match and status_match)
        item.setHidden(not visible)
        if child_match and (query or wanted is not None):
            item.setExpanded(True)
        return visible

    def _selected_identity(self) -> tuple[str, str] | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return None
        return str(data[0]), str(data[1])

    def _restore_selection(self, identity: tuple[str, str] | None) -> None:
        if identity is None:
            return
        iterator = self.tree.invisibleRootItem()
        stack = [iterator.child(index) for index in range(iterator.childCount())]
        while stack:
            item = stack.pop()
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and (str(data[0]), str(data[1])) == identity:
                self.tree.setCurrentItem(item)
                return
            stack.extend(item.child(index) for index in range(item.childCount()))

    def _selected_scene_id(self) -> str | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return None
        kind = str(data[0])
        if kind == StoryNodeKind.SCENE.value:
            return str(data[2])
        if kind == StoryNodeKind.SHOT.value:
            return str(data[2])
        return None

    def _show_item(
        self,
        current: QTreeWidgetItem | None,
        previous: QTreeWidgetItem | None,
    ) -> None:
        if not self._v2_ready:
            super()._show_item(current, previous)
            return
        if current is None:
            self.details.clear()
            return
        data = current.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind = str(data[0])
        if kind in {StoryNodeKind.SCENE.value, StoryNodeKind.SHOT.value}:
            legacy_data = (
                ("scene", data[2])
                if kind == StoryNodeKind.SCENE.value
                else ("shot", data[2], data[3])
            )
            current.setData(0, Qt.ItemDataRole.UserRole, legacy_data)
            try:
                super()._show_item(current, previous)
            finally:
                current.setData(0, Qt.ItemDataRole.UserRole, data)
            return
        self.details.setHtml(
            f"<h2>{current.text(0)}</h2>"
            f"<p><b>Type:</b> {current.text(1)}</p>"
            f"<p><b>Status:</b> {current.text(2)}</p>"
            f"<p><b>Duration:</b> {current.text(3)}</p>"
            f"<p><b>Identifier:</b> {data[1]}</p>"
            f"<p><b>Contained items:</b> {current.childCount()}</p>"
        )

    def _update_action_state(self, *_args: object) -> None:
        active_scene = self._selected_scene_id() is not None
        self.edit_button.setEnabled(active_scene)
        self.delete_button.setEnabled(active_scene)
        self.plan_button.setEnabled(active_scene)
