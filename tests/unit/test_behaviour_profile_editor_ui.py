from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

from vscs.application.behaviours import BehaviourProfileRepository, BehaviourProfileService
from vscs.domain.assets import AssetCategory
from vscs.domain.behaviours import BehaviourAuthority, BehaviourCategory, BehaviourProfile
from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.database import DatabaseManager
from vscs.presentation.widgets.behaviour_profile_manager import (
    BehaviourProfileEditorDialog,
    BehaviourProfileManagerWidget,
)


@pytest.fixture
def behaviour_service(tmp_path: Path) -> BehaviourProfileService:
    database = DatabaseManager()
    database.open(tmp_path, ProjectMetadata(name="Behaviour Editor"))
    service = BehaviourProfileService(BehaviourProfileRepository(database))
    yield service
    database.close()


def _profile(*, authority: BehaviourAuthority = BehaviourAuthority.DRAFT) -> BehaviourProfile:
    return BehaviourProfile(
        profile_id="BEP-SHP-DOCK",
        name="Ship Docking",
        version="1.0",
        description="Controlled ship docking.",
        category=BehaviourCategory.MANEUVERING,
        action="dock",
        applicable_asset_categories=(AssetCategory.SHIP,),
        aliases=("berth",),
        tags=("ship", "docking"),
        authority=authority,
        metadata={"department": "flight"},
    )


def test_editor_is_resizable_scrollable_and_round_trips_draft(qtbot) -> None:
    dialog = BehaviourProfileEditorDialog(_profile())
    qtbot.addWidget(dialog)

    assert dialog.minimumWidth() <= 680
    assert dialog.minimumHeight() <= 480
    assert isinstance(dialog.scroll_area, QScrollArea)
    assert dialog.scroll_area.widgetResizable()
    assert not dialog.profile_id_edit.isEnabled()
    assert not dialog.version_edit.isEnabled()

    dialog.resize(700, 500)
    rebuilt = dialog.build_profile()
    assert rebuilt == _profile()


def test_governed_profile_is_read_only(qtbot) -> None:
    dialog = BehaviourProfileEditorDialog(_profile(authority=BehaviourAuthority.APPROVED))
    qtbot.addWidget(dialog)

    assert not dialog.name_edit.isEnabled()
    assert not dialog.tabs.isEnabled()
    save = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
    assert save is not None
    assert not save.isEnabled()


def test_manager_does_not_query_without_project(behaviour_service, qtbot) -> None:
    manager = BehaviourProfileManagerWidget(
        behaviour_service,
        project_available=lambda: False,
    )
    qtbot.addWidget(manager)

    assert manager.table.rowCount() == 0
    assert not manager.edit_button.isEnabled()
    assert not manager.delete_button.isEnabled()


def test_manager_exposes_governance_actions(behaviour_service, qtbot) -> None:
    behaviour_service.create(_profile())
    manager = BehaviourProfileManagerWidget(behaviour_service)
    qtbot.addWidget(manager)
    manager.table.selectRow(0)

    assert manager.table.rowCount() == 1
    assert manager.submit_button.isEnabled()
    assert manager.delete_button.isEnabled()
    assert not manager.approve_button.isEnabled()

    manager._transition(BehaviourAuthority.PROPOSED)
    manager.table.selectRow(0)
    assert manager.approve_button.isEnabled()
    assert manager.rework_button.isEnabled()
    assert not manager.delete_button.isEnabled()


def test_manager_revision_preserves_governed_source(behaviour_service, qtbot, monkeypatch) -> None:
    behaviour_service.create(_profile())
    behaviour_service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)
    behaviour_service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.APPROVED)
    manager = BehaviourProfileManagerWidget(behaviour_service)
    qtbot.addWidget(manager)
    manager.table.selectRow(0)

    monkeypatch.setattr(
        "vscs.presentation.widgets.behaviour_profile_manager.QInputDialog.getText",
        lambda *_args, **_kwargs: ("2.0", True),
    )
    manager._revise()

    assert behaviour_service.get("BEP-SHP-DOCK", "1.0").authority is BehaviourAuthority.APPROVED
    assert behaviour_service.get("BEP-SHP-DOCK", "2.0").authority is BehaviourAuthority.DRAFT
    assert manager.table.rowCount() == 2
