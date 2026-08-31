"""Phase 20.18.2 READY-UPD governed-reference refresh regression tests."""

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
            assets=(),
            camera={"production": {"shot_size": "medium_close", "movement": "static"}},
            lighting={"production": {"lighting_intent": "practical_motivated"}},
            environment={"environment_context": "interior"},
            action_performance={
                "production": {
                    "temporal_narrative": "James turns toward Sandra.",
                    "closing_state": "James attends to Sandra's report.",
                }
            },
            continuity={"production": {}},
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
        revision = len(self.history) + 1
        derived = replace(
            current,
            package_id=f"PP-SHT-001-UPD-{revision}",
            package_fingerprint=f"upd-fingerprint-{revision}",
            universal_description=dict(data["universal_description"]),
            validation=dict(data["validation"]),
            status=ProductionPackageStatus.COMPILING,
        )
        self.value = derived
        self.history.append(derived)
        return derived


class _ReferencePlans:
    def __init__(self, plan: dict | None = None) -> None:
        self.plan = plan

    def reference_plan_for_shot(self, shot_id: str):
        assert shot_id == "SHT-001"
        return None if self.plan is None else dict(self.plan)


def _plan(reference_id: str = "REF-JAMES-16X9") -> dict:
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
            "aspect_tolerance": 0.03,
        },
        "references": [
            {
                "reference_id": reference_id,
                "asset_id": "CAP-CHR-001",
                "role": "primary_identity",
                "reference_class": "provider_ready_derivative",
                "priority": "required",
                "subject_type": "character",
                "source_path": "references/james-16x9.png",
                "provider_ready": True,
                "provider_profiles": ["production-video-16x9"],
                "width": 1672,
                "height": 941,
                "coverage": {
                    "framing_type": "full_body",
                    "coverage": "full_required_asset",
                    "required_features_visible": True,
                    "identity_visible": True,
                    "full_required_asset_visible": True,
                },
            }
        ],
        "diagnostics": [],
    }


def _service(tmp_path: Path):
    packages = _Packages()
    plans = _ReferencePlans()
    service = UniversalProductionDescriptionCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        plans,  # type: ignore[arg-type]
    )
    return service, packages, plans


def test_ready_upd_auto_refreshes_when_only_governed_reference_dependency_changes(
    tmp_path: Path,
) -> None:
    service, packages, plans = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    ready = service.mark_ready("SHT-001")
    assert ready.status is UniversalProductionDescriptionStatus.READY
    assert "reference_plan" not in packages.value.universal_description["production"]
    first_package_id = packages.value.package_id

    plans.plan = _plan()
    stale = service.draft("SHT-001")
    assert stale is not None
    assert not service.is_current(stale)

    refreshed_package = service.compile("SHT-001")
    refreshed_draft = service.draft("SHT-001")

    assert refreshed_draft is not None
    assert refreshed_draft.status is UniversalProductionDescriptionStatus.READY
    assert service.is_current(refreshed_draft)
    assert refreshed_package.package_id != first_package_id
    assert refreshed_package.universal_description["production"]["reference_plan"] == _plan()


def test_ready_upd_still_blocks_automatic_refresh_when_upstream_authority_changes(
    tmp_path: Path,
) -> None:
    service, packages, plans = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    plans.plan = _plan()
    packages.value = replace(
        packages.value,
        camera={"production": {"shot_size": "wide", "movement": "tracking"}},
    )

    with pytest.raises(
        UniversalProductionDescriptionCompilerError,
        match="return to Draft",
    ):
        service.compile("SHT-001")
