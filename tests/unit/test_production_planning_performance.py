from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import QLabel, QTableWidget

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.domain.assets import AssetCategory
from vscs.presentation.widgets.production_planning_performance import (
    ProductionPlanningSnapshot,
    _optimized_refresh,
)


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

    def _load_production_review(self) -> None:
        self._load("review")

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
    assert workspace.loader_calls == {
        **workspace.state_calls,
        "review": 1,
    }
    assert selection_events == 0
    assert workspace.footer_updates == 1


@dataclass(frozen=True)
class _CurrentIntegrated:
    shot_id: str
    package_id: str
    package_fingerprint: str


@dataclass(frozen=True)
class _AuthorityBinding:
    binding_id: str
    shot_id: str
    asset_id: str = "CAP-LOC-021"
    expected_category: AssetCategory = AssetCategory.LOCATION


class _AuthorityAssets:
    def __init__(self) -> None:
        self.list_calls = 0
        self.resolution_calls = 0
        self.shot_ready_calls = 0
        self.ready_calls = 0
        self.bindings = (
            _AuthorityBinding("SHT-001-AST-001", "SHT-001"),
            _AuthorityBinding("SHT-002-AST-001", "SHT-002"),
        )

    def list_bindings(self, *, shot_id: str | None = None):
        self.list_calls += 1
        if shot_id is None:
            return self.bindings
        return tuple(item for item in self.bindings if item.shot_id == shot_id)

    def resolution(self, _binding):
        self.resolution_calls += 1
        return object()

    def shot_ready(self, _shot_id: str) -> bool:
        self.shot_ready_calls += 1
        return True

    def is_production_ready(self, _binding) -> bool:
        self.ready_calls += 1
        return True


class _AuthorityPlanCollection:
    def __init__(self, attr_name: str, values: tuple[object, ...]) -> None:
        self.attr_name = attr_name
        self.values = values
        self.list_calls = 0

    def list_plans(self, **kwargs):
        self.list_calls += 1
        if not kwargs:
            return self.values
        key, requested = next(iter(kwargs.items()))
        expected_attr = {
            "scene_id": "scene_id",
            "episode_id": "episode_id",
            "story_id": "story_id",
        }[key]
        return tuple(item for item in self.values if getattr(item, expected_attr) == requested)

    def is_production_ready(self, _value) -> bool:
        return True


class _AuthorityReviews:
    def __init__(self) -> None:
        self.list_calls = 0
        self.snapshot_calls = 0
        self.assets = _AuthorityAssets()
        episode = type("Episode", (), {"episode_id": "EP-001", "story_id": "STORY-001"})()
        scene = type(
            "Scene",
            (),
            {"scene_id": "SCN-001", "episode_id": "EP-001"},
        )()
        shot_1 = type(
            "Shot",
            (),
            {"shot_id": "SHT-001", "scene_id": "SCN-001"},
        )()
        shot_2 = type(
            "Shot",
            (),
            {"shot_id": "SHT-002", "scene_id": "SCN-001"},
        )()
        self.shots = _AuthorityPlanCollection("shot_id", (shot_1, shot_2))
        self.shots.scenes = _AuthorityPlanCollection("scene_id", (scene,))
        self.shots.scenes.episodes = _AuthorityPlanCollection("episode_id", (episode,))
        self.camera = _AuthorityPlanCollection("shot_id", ())
        self.lighting = _AuthorityPlanCollection("shot_id", ())
        self.environment = _AuthorityPlanCollection("shot_id", ())

    def list_reviews(self):
        self.list_calls += 1
        return ()

    def snapshot(self, shot_id: str):
        self.snapshot_calls += 1
        # Deliberately repeat the same governed reads. The refresh cache must make
        # these operations cheap without changing their semantics.
        self.assets.list_bindings(shot_id=shot_id)
        self.assets.list_bindings(shot_id=shot_id)
        self.assets.shot_ready(shot_id)
        self.assets.shot_ready(shot_id)
        for binding in self.assets.list_bindings(shot_id=shot_id):
            self.assets.resolution(binding)
            self.assets.resolution(binding)
        return object()


class _AuthorityPlanning:
    def __init__(self) -> None:
        self.reviews = _AuthorityReviews()
        self.list_calls = 0
        self.current_calls = 0
        self.values = (
            _CurrentIntegrated("SHT-001", "PIP-SHT-001", "source-1"),
            _CurrentIntegrated("SHT-002", "PIP-SHT-002", "source-2"),
        )

    def list_packages(self, *, shot_id: str | None = None):
        self.list_calls += 1
        if shot_id is None:
            return self.values
        return tuple(item for item in self.values if item.shot_id == shot_id)

    def current_package(self, shot_id: str):
        self.current_calls += 1
        # These calls mirror the expensive repeated governance traversal in the
        # real integration service.
        self.reviews.list_reviews()
        self.reviews.list_reviews()
        self.reviews.snapshot(shot_id)
        self.reviews.snapshot(shot_id)
        self.reviews.shots.list_plans(scene_id="SCN-001")
        self.reviews.shots.list_plans(scene_id="SCN-001")
        values = self.list_packages(shot_id=shot_id)
        return values[-1] if values else None

    def is_current(self, package) -> bool:
        current = self.current_package(package.shot_id)
        return current is not None and current.package_id == package.package_id


class _AuthorityPackages:
    def __init__(self) -> None:
        self.planning = _AuthorityPlanning()
        self.list_calls = 0
        self.materialize_calls = 0
        self.values = (
            ProductionPackage(
                package_id="PP-SHT-001",
                shot_id="SHT-001",
                schema_version="1.0",
                source_fingerprint="source-1",
                package_fingerprint="package-1",
                provenance=ProductionPackageProvenance(
                    "PIP-SHT-001", "source-1", "PRV-1", "review-1"
                ),
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
            ),
            ProductionPackage(
                package_id="PP-SHT-002",
                shot_id="SHT-002",
                schema_version="1.0",
                source_fingerprint="source-2",
                package_fingerprint="package-2",
                provenance=ProductionPackageProvenance(
                    "PIP-SHT-002", "source-2", "PRV-2", "review-2"
                ),
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
            ),
        )

    def list_packages(self):
        self.list_calls += 1
        return self.values

    def current_package(self, shot_id: str):
        return next((item for item in self.values if item.shot_id == shot_id), None)

    def materialize(self, _shot_id: str):
        self.materialize_calls += 1
        raise AssertionError("existing current packages must not be rematerialized")


class _AuthorityWorkspace:
    def __init__(self) -> None:
        self.packages = _AuthorityPackages()


def test_snapshot_capture_caches_governed_authority_reads_across_shots() -> None:
    workspace = _AuthorityWorkspace()

    snapshot = ProductionPlanningSnapshot.capture(workspace)

    planning = workspace.packages.planning
    reviews = planning.reviews
    assert tuple(snapshot.current_integrated) == ("SHT-001", "SHT-002")
    assert tuple(snapshot.current_packages) == ("SHT-001", "SHT-002")
    assert planning.list_calls == 1
    assert planning.current_calls == 2
    assert reviews.list_calls == 1
    assert reviews.snapshot_calls == 2
    assert reviews.assets.list_calls == 1
    assert reviews.assets.shot_ready_calls == 2
    # Both Shots resolve the same canonical asset/category; one authoritative
    # resolution is sufficient for this immutable refresh scope.
    assert reviews.assets.resolution_calls == 1
    assert reviews.shots.list_calls == 1
    assert workspace.packages.list_calls == 1
    assert workspace.packages.materialize_calls == 0


def test_snapshot_refresh_cache_is_not_reused_across_user_refreshes() -> None:
    workspace = _AuthorityWorkspace()

    ProductionPlanningSnapshot.capture(workspace)
    ProductionPlanningSnapshot.capture(workspace)

    planning = workspace.packages.planning
    reviews = planning.reviews
    assert planning.list_calls == 2
    assert planning.current_calls == 4
    assert reviews.list_calls == 2
    assert reviews.snapshot_calls == 4
    assert reviews.assets.list_calls == 2
    assert reviews.assets.resolution_calls == 2
