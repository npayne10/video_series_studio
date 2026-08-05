"""Story Browser integration for editable Advanced Clip Production Packages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from vscs.application.acpp import ACPPEditorError, ACPPEditorService
from vscs.application.asset_resolution import AssetBrowserService
from vscs.application.assets import AssetService
from vscs.application.projects import ProjectNotOpenError
from vscs.application.shots import ShotPlanningService
from vscs.application.story import StoryService
from vscs.presentation.dialogs.browseable_acpp_editor_dialog import (
    BrowseableACPPEditorDialog,
)

from .shot_planning_story_browser import ShotPlanningStoryBrowserWidget


class ACPPStoryBrowserWidget(ShotPlanningStoryBrowserWidget):
    """Expose ACPP creation and editing for persistent production shots."""

    def __init__(
        self,
        stories: StoryService,
        assets: AssetService,
        shot_plans: ShotPlanningService,
        acpp: ACPPEditorService,
        asset_browser: AssetBrowserService,
        parent: QWidget | None = None,
    ) -> None:
        self.acpp = acpp
        self.asset_browser = asset_browser
        super().__init__(stories, assets, shot_plans, parent)
        self.acpp_button = QPushButton("ACPP Editor", self)
        self.acpp_button.setObjectName("openACPPEditor")
        self.acpp_button.setToolTip(
            "Create or edit the Advanced Clip Production Package "
            "for the selected shot."
        )
        toolbar_item = self.layout().itemAt(2)
        toolbar = toolbar_item.layout() if toolbar_item is not None else None
        if not isinstance(toolbar, QHBoxLayout):
            raise RuntimeError("Story Browser toolbar is unavailable.")
        toolbar.insertWidget(5, self.acpp_button)
        self.acpp_button.clicked.connect(self._open_acpp_editor)
        self.tree.currentItemChanged.connect(self._update_acpp_action_state)
        self.refresh()

    def refresh(self) -> None:
        """Refresh production hierarchy and annotate shots with ACPP readiness."""
        super().refresh()
        if not hasattr(self, "acpp_button"):
            return
        try:
            packages = {
                package.identity.shot_id: package
                for package in self.acpp.list_packages()
            }
        except (ProjectNotOpenError, ACPPEditorError):
            self.acpp_button.setEnabled(False)
            return
        for item in self._walk_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if not data or str(data[0]) != self.SHOT_KIND:
                continue
            package = packages.get(str(data[1]))
            if package is None:
                item.setToolTip(0, "No ACPP created")
                continue
            status = package.metadata.get("editor_status", "draft").title()
            version = package.metadata.get("editor_version", "1")
            item.setToolTip(0, f"ACPP {status}, version {version}")
            item.setText(2, f"{item.text(2)} / ACPP {status}")
        self._update_acpp_action_state()

    def _selected_production_shot_id(self) -> str | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and str(data[0]) == self.SHOT_KIND:
            return str(data[1])
        return None

    def _open_acpp_editor(self) -> None:
        shot_id = self._selected_production_shot_id()
        if shot_id is None:
            return
        shot = self.shot_plans.shot(shot_id)
        if shot is None:
            return
        dialog = BrowseableACPPEditorDialog(
            shot,
            self.acpp,
            self.asset_browser,
            self,
        )
        dialog.exec()
        self.refresh()
        self._select_production_shot(shot_id)

    def _select_production_shot(self, shot_id: str) -> None:
        for item in self._walk_items():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if (
                data
                and str(data[0]) == self.SHOT_KIND
                and str(data[1]) == shot_id
            ):
                self.tree.setCurrentItem(item)
                return

    def _update_acpp_action_state(self, *_args: object) -> None:
        self.acpp_button.setEnabled(
            self._selected_production_shot_id() is not None
        )
