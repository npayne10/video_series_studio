"""Phase 19.4.8 Universal Production Description Compiler tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionStatus,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        self.value = ProductionPackage(
            package_id="PP-SHT-001-A",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="fingerprint",
            provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
            story_context={"scene": "Bridge"},
            shot={"title": "Bridge Dialogue"},
            assets=({"production": {"asset_id": "CAP-SHP-001"}},),
            camera={"production": {"shot_size": "medium_close", "movement": "static"}},
            lighting={"production": {"lighting_intent": "practical_motivated"}},
            environment={"environment_plan_id": "ENV-BRIDGE"},
            action_performance={
                "production": {
                    "temporal_narrative": "James walks to Cheryl.",
                    "closing_state": "James stands beside Cheryl.",
                }
            },
            continuity={"production": {"opening_state": "James enters the bridge."}},
            style={"production": {"provider_neutral": True}},
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
                "continuity_complete": True,
                "style_complete": True,
            },
            status=ProductionPackageStatus.COMPILING,
        )
        self.history: list[ProductionPackage] = []

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def _append_derived(self, current: ProductionPackage, data: dict):
        derived = replace(
            current,
            package_id="PP-SHT-001-UPD",
            package_fingerprint="upd-fingerprint",
            universal_description=dict(data["universal_description"]),
            validation=dict(data["validation"]),
            status=ProductionPackageStatus.COMPILING,
        )
        self.value = derived
        self.history.append(derived)
        return derived


def _service(tmp_path: Path):
    packages = _Packages()
    service = UniversalProductionDescriptionCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_create_assembles_all_governed_authority_without_provider_output(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-001")
    value = draft.description_value()

    assert value["current_shot_id"] == "SHT-001"
    assert value["action_performance"]["temporal_narrative"] == "James walks to Cheryl."
    assert value["assets"][0]["asset_id"] == "CAP-SHP-001"
    assert value["camera"]["movement"] == "static"
    assert value["provider_neutral"] is True
    assert "ACTION & PERFORMANCE" in value["universal_text"]
    assert "provider_outputs" not in value


def test_final_approval_is_blocked_until_all_upstream_authority_is_ready(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(
        packages.value,
        validation={**packages.value.validation, "style_complete": False},
    )
    service.create_from_current_package("SHT-001")

    assert service.missing_prerequisites("SHT-001") == ("Style",)
    with pytest.raises(UniversalProductionDescriptionCompilerError, match="Style"):
        service.mark_ready("SHT-001")


def test_ready_compiles_immutable_universal_description_and_locks_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Approved universal description.")
    ready = service.mark_ready("SHT-001")

    assert ready.status is UniversalProductionDescriptionStatus.READY
    assert packages.value.validation["universal_description_complete"] is True
    assert packages.value.universal_description["production"]["provider_neutral"] is True
    with pytest.raises(UniversalProductionDescriptionCompilerError, match="return to Draft"):
        service.save_notes("SHT-001", "Changed")


def test_upstream_change_makes_draft_stale_and_refresh_preserves_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Keep this note.")
    packages.value = replace(
        packages.value,
        camera={"production": {"shot_size": "wide", "movement": "tracking"}},
    )

    stale = service.draft("SHT-001")
    assert stale is not None
    assert not service.is_current(stale)
    refreshed = service.rebase_to_current_package("SHT-001")

    assert service.is_current(refreshed)
    assert refreshed.production_notes == "Keep this note."
    assert refreshed.description_value()["camera"]["movement"] == "tracking"


def test_return_to_draft_allows_review_after_ready(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    draft = service.return_to_draft("SHT-001")

    assert draft.status is UniversalProductionDescriptionStatus.DRAFT
