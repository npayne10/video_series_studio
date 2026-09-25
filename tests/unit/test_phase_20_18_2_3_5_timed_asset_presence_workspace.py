"""Phase 20.18.2.3.5 Timed Asset Presence authoring/UI acceptance."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QSpinBox, QTabWidget, QVBoxLayout, QWidget

from vscs.application.governed_reference_plan_source import PersistedGovernedReferencePlanSource
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetPresencePlan,
)
from vscs.application.timed_asset_presence_authoring import (
    TimedAssetPresenceAuthoringService,
)
from vscs.presentation.widgets.timed_asset_presence_workspace import (
    install_timed_asset_presence_workspace,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        self.value = SimpleNamespace(
            shot_id="EP-001-SCN-001-SHT-002",
            shot={"target_runtime_seconds": 6},
            assets=(
                {
                    "production": {
                        "asset_id": "CAP-CHR-003",
                        "category": "character",
                    }
                },
                {
                    "production": {
                        "asset_id": "CAP-CHR-001",
                        "category": "character",
                    }
                },
                {
                    "production": {
                        "asset_id": "CAP-PLN-002",
                        "category": "planet",
                    }
                },
                {
                    "production": {
                        "asset_id": "CAP-CHR-005",
                        "category": "character",
                    }
                },
                {
                    "production": {
                        "asset_id": "CAP-LOC-021",
                        "category": "location",
                    }
                },
            ),
            timed_asset_presence={},
        )
        self.saved: TimedAssetPresencePlan | None = None

    def current_package(self, _shot_id: str) -> Any:
        return self.value

    def derive_timed_asset_presence(
        self,
        _shot_id: str,
        plan: TimedAssetPresencePlan,
        *,
        production_notes: str = "",
    ) -> Any:
        self.saved = plan
        self.value.timed_asset_presence = plan.to_dict()
        self.value.production_notes = production_notes
        return self.value


def _reference_plan() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
        },
        "references": [
            {
                "reference_id": "LIVE-PRIMARY_IDENTITY-CAP-CHR-003",
                "asset_id": "CAP-CHR-003",
                "role": "primary_identity",
            },
            {
                "reference_id": "LIVE-SECONDARY_IDENTITY-CAP-CHR-001",
                "asset_id": "CAP-CHR-001",
                "role": "secondary_identity",
            },
            {
                "reference_id": "LIVE-ENVIRONMENT_REFERENCE-CAP-PLN-002",
                "asset_id": "CAP-PLN-002",
                "role": "environment_reference",
            },
            {
                "reference_id": "LIVE-SECONDARY_IDENTITY-CAP-CHR-005",
                "asset_id": "CAP-CHR-005",
                "role": "secondary_identity",
            },
            {
                "reference_id": "LIVE-SCENE_COMPOSITION_ANCHOR-TEST",
                "asset_id": None,
                "role": "scene_composition_anchor",
                "contains_environments": ["CAP-LOC-021"],
            },
        ],
        "diagnostics": [],
    }


def _persist_reference_plan(projects: _Projects) -> None:
    PersistedGovernedReferencePlanSource(projects).save_reference_plan(
        "EP-001-SCN-001-SHT-002",
        _reference_plan(),
    )


def test_authoring_defaults_use_governed_assets_and_direct_reference_ids(tmp_path: Path) -> None:
    projects = _Projects(tmp_path)
    packages = _Packages()
    _persist_reference_plan(projects)
    service = TimedAssetPresenceAuthoringService(
        packages,  # type: ignore[arg-type]
        PersistedGovernedReferencePlanSource(projects),
    )

    context = service.context("EP-001-SCN-001-SHT-002")

    assert context.persisted is False
    assert context.frames_per_second == 24
    assert context.frame_count == 144
    assert len(context.plan.presences) == 5
    assert context.plan.change_frames == ()
    planet = next(item for item in context.plan.presences if item.asset_id == "CAP-PLN-002")
    assert planet.asset_kind.value == "planet"
    bridge = next(item for item in context.plan.presences if item.asset_id == "CAP-LOC-021")
    assert bridge.canonical_reference_ids == ()
    assert "LIVE-SCENE_COMPOSITION_ANCHOR-TEST" not in {
        reference_id
        for presence in context.plan.presences
        for reference_id in presence.canonical_reference_ids
    }


def test_authoring_persists_explicit_ros_frame_96_without_prose_inference(
    tmp_path: Path,
) -> None:
    projects = _Projects(tmp_path)
    packages = _Packages()
    _persist_reference_plan(projects)
    service = TimedAssetPresenceAuthoringService(
        packages,  # type: ignore[arg-type]
        PersistedGovernedReferencePlanSource(projects),
    )
    default = service.context("EP-001-SCN-001-SHT-002").plan
    presences = []
    for presence in default.presences:
        if presence.asset_id != "CAP-CHR-005":
            presences.append(presence)
            continue
        presences.append(
            type(presence)(
                asset_id=presence.asset_id,
                asset_kind=presence.asset_kind,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=presence.canonical_reference_ids,
                notes="Ros enters at the governed frame-96 boundary.",
            )
        )
    plan = TimedAssetPresencePlan(
        shot_id=default.shot_id,
        frames_per_second=default.frames_per_second,
        frame_count=default.frame_count,
        presences=tuple(presences),
    )

    service.persist("EP-001-SCN-001-SHT-002", plan, production_notes="Human reviewed.")

    assert packages.saved is not None
    assert packages.saved.change_frames == (96,)
    assert {item.asset_id for item in packages.saved.active_at(95)} == {
        "CAP-CHR-003",
        "CAP-CHR-001",
        "CAP-PLN-002",
        "CAP-LOC-021",
    }
    assert "CAP-CHR-005" in {item.asset_id for item in packages.saved.active_at(96)}


def test_workspace_exposes_explicit_timed_presence_editor_and_saves_ros_boundary(
    qtbot: object,
    tmp_path: Path,
) -> None:
    projects = _Projects(tmp_path)
    packages = _Packages()
    _persist_reference_plan(projects)

    class _Workspace(QWidget):
        def __init__(self, projects_arg: _Projects, packages_arg: _Packages) -> None:
            super().__init__()
            self.projects = projects_arg
            self.packages = packages_arg
            self._selected_shot_id = "EP-001-SCN-001-SHT-002"
            layout = QVBoxLayout(self)
            self.compiler_tabs = QTabWidget(self)
            layout.addWidget(self.compiler_tabs)

        def refresh(self) -> None:
            return

        def _selection_changed(self) -> None:
            return

    install_timed_asset_presence_workspace(_Workspace)
    widget = _Workspace(projects, packages)
    qtbot.addWidget(widget)  # type: ignore[attr-defined]

    assert any(
        widget.compiler_tabs.tabText(index) == "Timed Asset Presence"
        for index in range(widget.compiler_tabs.count())
    )
    assert widget.timed_presence_table.rowCount() == 5
    assert "NOT authority" in widget.timed_presence_status.text()

    ros_row = next(
        row
        for row in range(widget.timed_presence_table.rowCount())
        if widget.timed_presence_table.item(row, 1).text() == "CAP-CHR-005"
    )
    from_spin = widget.timed_presence_table.cellWidget(ros_row, 3)
    introduction = widget.timed_presence_table.cellWidget(ros_row, 5)
    assert isinstance(from_spin, QSpinBox)
    assert isinstance(introduction, QComboBox)
    from_spin.setValue(96)
    introduction.setCurrentIndex(introduction.findData("enter"))

    qtbot.mouseClick(
        widget.timed_presence_save_button,
        Qt.MouseButton.LeftButton,
    )  # type: ignore[attr-defined]

    assert packages.saved is not None
    assert packages.saved.change_frames == (96,)
    ros = next(item for item in packages.saved.presences if item.asset_id == "CAP-CHR-005")
    assert ros.from_frame == 96
    assert ros.introduction is AssetPresenceIntroduction.ENTER
