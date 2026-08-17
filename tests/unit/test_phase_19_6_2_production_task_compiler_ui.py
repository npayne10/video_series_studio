from __future__ import annotations

import os
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionStatus,
)
from vscs.presentation.widgets.production_task_compiler_workspace import (
    install_production_task_compiler_workspace,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@dataclass
class FakeDraft:
    status: UniversalProductionDescriptionStatus


class FakeUniversalCompiler:
    def __init__(
        self,
        draft: FakeDraft | None,
        *,
        current: bool = True,
    ) -> None:
        self._draft = draft
        self._current = current

    def draft(self, _shot_id: str) -> FakeDraft | None:
        return self._draft

    def is_current(self, _draft: FakeDraft) -> bool:
        return self._current


class FakePackages:
    def __init__(self, *, valid: bool = True) -> None:
        validation = {
            "universal_description_complete": valid,
            "cross_authority_consistent": valid,
        }
        self.package = SimpleNamespace(
            package_id="PP-SH027-TEST",
            validation=validation,
            universal_description={
                "production": {
                    "canonical_references": [
                        {
                            "asset_id": "CAP-CHR-001",
                            "canonical_reference": "ref/james.png",
                        }
                    ]
                }
            },
        )

    def current_package(self, _shot_id: str) -> Any:
        return self.package

    def require_current_package(self, _shot_id: str) -> Any:
        return self.package


def _workspace(
    app: QApplication,
    *,
    draft: FakeDraft | None,
    current: bool = True,
    valid_package: bool = True,
) -> QWidget:
    del app
    universal = FakeUniversalCompiler(draft, current=current)
    packages = FakePackages(valid=valid_package)

    class TestWorkspace(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.universal_compiler = universal
            self.packages = packages
            layout = QVBoxLayout(self)
            self.compiler_tabs = QTabWidget(self)
            layout.addWidget(self.compiler_tabs)
            self._selected_shot_id = "SH027"

        def refresh(self) -> None:
            return None

        def _selection_changed(self) -> None:
            return None

    install_production_task_compiler_workspace(TestWorkspace)
    workspace = TestWorkspace()
    workspace.production_task_production_id.setText("production-EP01")  # type: ignore[attr-defined]
    workspace.production_task_episode_id.setText("EP01")  # type: ignore[attr-defined]
    workspace.production_task_scene_id.setText("SC04")  # type: ignore[attr-defined]
    workspace.production_task_approved_by.setText("Neill")  # type: ignore[attr-defined]
    workspace.production_task_authority_revision.setValue(3)  # type: ignore[attr-defined]
    workspace._refresh_production_task_eligibility()  # type: ignore[attr-defined]
    return workspace


def test_no_upd_disables_production_task_compilation(app: QApplication) -> None:
    workspace = _workspace(app, draft=None)

    assert not workspace.compile_production_tasks_button.isEnabled()  # type: ignore[attr-defined]
    assert "No Universal Production Description" in workspace.production_task_status.text()  # type: ignore[attr-defined]


def test_draft_and_stale_upd_are_blocked(app: QApplication) -> None:
    draft_workspace = _workspace(
        app,
        draft=FakeDraft(UniversalProductionDescriptionStatus.DRAFT),
    )
    stale_workspace = _workspace(
        app,
        draft=FakeDraft(UniversalProductionDescriptionStatus.READY),
        current=False,
    )

    assert not draft_workspace.compile_production_tasks_button.isEnabled()  # type: ignore[attr-defined]
    assert "must be Ready" in draft_workspace.production_task_status.text()  # type: ignore[attr-defined]
    assert not stale_workspace.compile_production_tasks_button.isEnabled()  # type: ignore[attr-defined]
    assert "stale" in stale_workspace.production_task_status.text().lower()  # type: ignore[attr-defined]


def test_current_ready_upd_compiles_and_displays_governed_task(app: QApplication) -> None:
    workspace = _workspace(
        app,
        draft=FakeDraft(UniversalProductionDescriptionStatus.READY),
    )

    assert workspace.compile_production_tasks_button.isEnabled()  # type: ignore[attr-defined]
    workspace.compile_production_tasks_button.click()  # type: ignore[attr-defined]

    table = workspace.production_task_table  # type: ignore[attr-defined]
    assert table.rowCount() == 1
    assert table.item(0, 1).text() == "video_generation"
    assert table.item(0, 2).text() == "planned"
    assert table.item(0, 3).text() == "3"
    assert table.item(0, 4).text() == "Neill"
    assert table.item(0, 5).text() == "video_generation"
    assert "canonical-reference:CAP-CHR-001:ref/james.png" in table.item(0, 6).text()
    assert table.item(0, 7).text() == "video/shot"
    assert table.item(0, 8).text()


def test_recompilation_is_deterministic_for_same_governed_context(app: QApplication) -> None:
    workspace = _workspace(
        app,
        draft=FakeDraft(UniversalProductionDescriptionStatus.READY),
    )
    workspace.compile_production_tasks_button.click()  # type: ignore[attr-defined]
    first_id = workspace.production_task_table.item(0, 0).text()  # type: ignore[attr-defined]

    workspace.compile_production_tasks_button.click()  # type: ignore[attr-defined]
    second_id = workspace.production_task_table.item(0, 0).text()  # type: ignore[attr-defined]

    assert first_id == second_id


def test_ui_exposes_no_provider_workflow_or_state_transition_controls(app: QApplication) -> None:
    workspace = _workspace(
        app,
        draft=FakeDraft(UniversalProductionDescriptionStatus.READY),
    )
    workspace.compile_production_tasks_button.click()  # type: ignore[attr-defined]
    table = workspace.production_task_table  # type: ignore[attr-defined]

    headers = [table.horizontalHeaderItem(index).text().lower() for index in range(table.columnCount())]
    assert not any("provider" in header for header in headers)
    assert not any("workflow" in header for header in headers)
    assert not hasattr(workspace, "production_task_state_selector")
    assert not hasattr(workspace, "production_task_execute_button")
    assert table.item(0, 2).text() == "planned"
    assert table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
