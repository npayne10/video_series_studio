from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLabel, QTableWidget

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.presentation.widgets.production_planning_performance import _optimized_refresh


@dataclass(frozen=True)
class _Integrated:
    shot_id: str = "SHT-001"


class _Planning:
    def list_packages(self):
        return (_Integrated(),)

    def is_current(self, _package):
        return True


class _Projects:
    is_project_open = True


class _Packages:
    def __init__(self) -> None:
        self.planning = _Planning()
        self.materialize_calls = 0
        self.value = ProductionPackage(
            package_id="PP-SHT-001-A",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="package",
            provenance=ProductionPackageProvenance("PIP-SHT-001", "source", "PRV", "review"),
            story_context={},
            shot={},
            assets=(),
            camera={},
            lighting={},
            environment={},
            action_performance={},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=(),
            universal_description={},
            provider_outputs={},
            validation={},
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        self.materialize_calls += 1
        return self.value


class _Workspace:
    def __init__(self) -> None:
        self.projects = _Projects()
        self.packages = _Packages()
        self._selected_shot_id: str | None = "SHT-001"
        self.package_table = QTableWidget(0, 11)
        self.package_summary = QLabel()
        self.action_status = QLabel()
        self.asset_status = QLabel()
        self.state_calls: dict[str, int] = {}
        self.loader_calls: dict[str, int] = {}
        self.footer_updates = 0

    @staticmethod
    def _headers() -> tuple[str, ...]:
        return (
            "Shot",
            "Production Package",
            "Action",
            "Assets",
            "Camera",
            "Lighting",
            "Continuity",
            "Style",
            "Universal",
            "Provider",
            "Source",
        )

    def _state(self, name: str) -> str:
        self.state_calls[name] = self.state_calls.get(name, 0) + 1
        return "Ready / Compiled"

    def _action_state(self, _shot_id: str) -> str:
        return self._state("action")

    def _asset_state(self, _shot_id: str) -> str:
        return self._state("asset")

    def _camera_state(self, _shot_id: str) -> str:
        return self._state("camera")

    def _lighting_state(self, _shot_id: str) -> str:
        return self._state("lighting")

    def _continuity_state(self, _shot_id: str) -> str:
        return self._state("continuity")

    def _style_state(self, _shot_id: str) -> str:
        return self._state("style")

    def _universal_state(self, _shot_id: str) -> str:
        return self._state("universal")

    def _provider_state(self, _shot_id: str) -> str:
        return self._state("provider")

    def _load(self, name: str) -> None:
        self.loader_calls[name] = self.loader_calls.get(name, 0) + 1

    def _load_draft(self) -> None:
        self._load("action")

    def _load_asset_draft(self) -> None:
        self._load("asset")

    def _load_camera_draft(self) -> None:
        self._load("camera")

    def _load_lighting_draft(self) -> None:
        self._load("lighting")

    def _load_continuity_draft(self) -> None:
        self._load("continuity")

    def _load_style_draft(self) -> None:
        self._load("style")

    def _load_universal_draft(self) -> None:
        self._load("universal")

    def _load_provider_draft(self) -> None:
        self._load("provider")

    def _update_future_footer(self) -> None:
        self.footer_updates += 1

    def _clear_editor(self) -> None:
        pass

    def _clear_asset_editor(self) -> None:
        pass

    def _set_editor_enabled(self, _enabled: bool) -> None:
        pass

    def _set_asset_editor_enabled(self, _enabled: bool) -> None:
        pass


def test_snapshot_refresh_avoids_rematerialization_and_loads_each_compiler_once(qtbot) -> None:
    workspace = _Workspace()
    qtbot.addWidget(workspace.package_table)
    selection_events = 0

    def _selection_event() -> None:
        nonlocal selection_events
        selection_events += 1

    workspace.package_table.itemSelectionChanged.connect(_selection_event)

    _optimized_refresh(workspace)

    assert workspace.packages.materialize_calls == 0
    assert workspace.package_table.rowCount() == 1
    assert workspace.package_table.item(0, 0).text() == "SHT-001"
    assert workspace.package_table.item(0, 9).text() == "Ready / Compiled"
    assert workspace.state_calls == {
        "action": 1,
        "asset": 1,
        "camera": 1,
        "lighting": 1,
        "continuity": 1,
        "style": 1,
        "universal": 1,
        "provider": 1,
    }
    assert workspace.loader_calls == workspace.state_calls
    assert selection_events == 0
    assert workspace.footer_updates == 1
