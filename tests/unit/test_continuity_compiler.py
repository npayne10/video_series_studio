"""Phase 19.4.6 Continuity Compiler tests."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.continuity_compiler import (
    ContinuityCompilationStatus,
    ContinuityCompilerError,
    ContinuityCompilerService,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Integrated:
    def __init__(self, shot_id: str) -> None:
        self.shot_id = shot_id


class _Planning:
    def __init__(self, shot_ids: tuple[str, ...]) -> None:
        self.values = tuple(_Integrated(value) for value in shot_ids)

    def list_packages(self):
        return self.values

    def is_current(self, _item):
        return True


class _Packages:
    def __init__(self) -> None:
        self.planning = _Planning(("SHT-001", "SHT-002"))
        self.values = {
            "SHT-001": self._package(
                "SHT-001",
                "Previous closes beside viewport.",
                opening="Previous opens on bridge.",
            ),
            "SHT-002": self._package(
                "SHT-002",
                "Current closes at console.",
                opening="Previous closes beside viewport.",
            ),
        }
        self.history: list[ProductionPackage] = []

    @staticmethod
    def _package(shot_id: str, closing: str, *, opening: str) -> ProductionPackage:
        return ProductionPackage(
            package_id=f"PP-{shot_id}-A",
            shot_id=shot_id,
            schema_version="1.0",
            source_fingerprint=f"source-{shot_id}",
            package_fingerprint=f"fingerprint-{shot_id}",
            provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
            story_context={},
            shot={"shot_id": shot_id, "continuity_in": opening, "continuity_out": closing},
            assets=(
                {
                    "resolution": {"asset_id": "CAP-CHR-001"},
                },
            ),
            camera={"production": {"screen_direction": "left_to_right"}},
            lighting={"production": {"continuity_notes": "Keep bridge practicals stable."}},
            environment={"environment_plan_id": "ENV-BRIDGE"},
            action_performance={"opening_state": opening, "closing_state": closing},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=(),
            universal_description={},
            provider_outputs={},
            validation={
                "action_performance_complete": True,
                "assets_complete": True,
                "camera_complete": True,
                "lighting_complete": True,
            },
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, shot_id: str):
        return self.values.get(shot_id)

    def materialize(self, shot_id: str):
        return self.values[shot_id]

    def require_current_package(self, shot_id: str):
        return self.values[shot_id]

    def _append_derived(self, current: ProductionPackage, data: dict):
        derived = replace(
            current,
            package_id=f"{current.package_id}-C",
            package_fingerprint=f"{current.package_fingerprint}-C",
            continuity=dict(data["continuity"]),
            validation=dict(data["validation"]),
            status=ProductionPackageStatus.COMPILING,
        )
        self.values[current.shot_id] = derived
        self.history.append(derived)
        return derived


def _service(tmp_path: Path):
    packages = _Packages()
    service = ContinuityCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_create_inherits_previous_closing_state_without_invention(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-002")
    continuity = draft.continuity_value()

    assert draft.previous_shot_id == "SHT-001"
    assert continuity["previous_closing_state"] == "Previous closes beside viewport."
    assert continuity["effective_opening_state"] == "Previous closes beside viewport."
    assert continuity["current_asset_ids"] == ["CAP-CHR-001"]
    assert continuity["inheritance_mode"] == "previous-shot-closing-state"
    assert continuity["continuity_conflicts"] == []


def test_first_shot_uses_series_entry_without_fake_previous_state(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-001")

    assert draft.previous_shot_id == ""
    assert draft.continuity_value()["previous_closing_state"] == ""
    assert draft.continuity_value()["inheritance_mode"] == "series-entry"


def test_conflict_is_exposed_for_user_review_not_silently_rewritten(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.values["SHT-002"] = replace(
        packages.values["SHT-002"],
        action_performance={
            "opening_state": "Different opening state.",
            "closing_state": "Current closes at console.",
        },
    )
    draft = service.create_from_current_package("SHT-002")

    assert draft.continuity_value()["effective_opening_state"] == "Different opening state."
    assert len(draft.continuity_value()["continuity_conflicts"]) == 1


def test_ready_compiles_provider_neutral_continuity_and_locks_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-002")
    service.save_notes("SHT-002", "User reviewed inherited bridge state.")
    ready = service.mark_ready("SHT-002")

    assert ready.status is ContinuityCompilationStatus.READY
    compiled = packages.values["SHT-002"].continuity
    assert compiled["production"]["previous_shot_id"] == "SHT-001"
    assert compiled["production"]["provider_neutral"] is True
    assert packages.values["SHT-002"].validation["continuity_complete"] is True
    assert (
        packages.values["SHT-002"].validation["continuity_review_notes"]
        == "User reviewed inherited bridge state."
    )
    with pytest.raises(ContinuityCompilerError, match="return to Draft"):
        service.save_notes("SHT-002", "Changed")


def test_previous_shot_change_makes_draft_stale_and_refresh_preserves_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-002")
    service.save_notes("SHT-002", "Preserve this review note.")
    packages.values["SHT-001"] = replace(
        packages.values["SHT-001"],
        action_performance={
            "opening_state": "Previous opens on bridge.",
            "closing_state": "Previous now closes at tactical station.",
        },
    )

    stale = service.draft("SHT-002")
    assert stale is not None
    assert not service.is_current(stale)
    with pytest.raises(ContinuityCompilerError, match="stale"):
        service.mark_ready("SHT-002")

    refreshed = service.rebase_to_current_package("SHT-002")
    assert service.is_current(refreshed)
    assert refreshed.production_notes == "Preserve this review note."
    assert (
        refreshed.continuity_value()["previous_closing_state"]
        == "Previous now closes at tactical station."
    )
