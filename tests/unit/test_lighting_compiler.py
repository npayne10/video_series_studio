"""Phase 19.4.5 Lighting Compiler tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.lighting_compiler import (
    LightingCompilationStatus,
    LightingCompilerError,
    LightingCompilerService,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        self.value = self._package("source-1", "PP-SHT-001-A")
        self.derived: dict | None = None
        self.notes = ""

    @staticmethod
    def _lighting() -> dict:
        return {
            "lighting_plan_id": "LGT-SHT-001",
            "shot_id": "SHT-001",
            "lighting_intent": "practical_motivated",
            "key_direction": "front_side",
            "key_quality": "soft",
            "color_temperature_k": 4300,
            "fill_level_percent": 50,
            "exposure_intent": "balanced",
            "source_strategy": "Use motivated practical sources.",
            "shadow_strategy": "Preserve soft directional modelling.",
            "subject_readability": "Maintain natural facial readability.",
            "separation_strategy": "Use restrained tonal separation.",
            "continuity_notes": "Preserve established bridge lighting state.",
            "lighting_constraints": ["No decorative glow"],
            "lighting_profile_asset_id": "CAP-LGT-001",
        }

    @classmethod
    def _package(cls, source: str, package_id: str) -> ProductionPackage:
        return ProductionPackage(
            package_id=package_id,
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint=source,
            package_fingerprint=f"fingerprint-{source}",
            provenance=ProductionPackageProvenance("PIP-1", source, "PRV-1", "review"),
            story_context={},
            shot={},
            assets=(),
            camera={"production": {"screen_direction": "neutral"}},
            lighting=cls._lighting(),
            environment={},
            action_performance={"temporal_narrative": "Dialogue on bridge."},
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
            },
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def derive_lighting(self, _shot_id: str, compiled, *, production_notes: str = ""):
        self.derived = compiled
        self.notes = production_notes
        return replace(self.value, lighting=compiled)


def _service(tmp_path: Path):
    packages = _Packages()
    service = LightingCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_create_seeds_governed_lighting_without_invention(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    draft = service.create_from_current_package("sht-001")

    assert draft.shot_id == "SHT-001"
    assert draft.lighting == packages.value.lighting
    assert draft.production_notes == ""
    assert draft.status is LightingCompilationStatus.DRAFT


def test_ready_compilation_is_provider_neutral_and_preserves_lighting_authority(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "User approves the motivated bridge lighting.")
    ready = service.mark_ready("SHT-001")

    assert ready.status is LightingCompilationStatus.READY
    assert packages.derived is not None
    assert packages.derived["governed"]["lighting_plan_id"] == "LGT-SHT-001"
    assert packages.derived["production"]["lighting_intent"] == "practical_motivated"
    assert packages.derived["production"]["color_temperature_k"] == 4300
    assert packages.derived["production"]["continuity_notes"].startswith("Preserve")
    assert packages.derived["production"]["provider_neutral"] is True
    assert packages.notes == "User approves the motivated bridge lighting."


def test_ready_lighting_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    with pytest.raises(LightingCompilerError, match="return to Draft"):
        service.save_notes("SHT-001", "Changed")

    draft = service.return_to_draft("SHT-001")
    assert draft.status is LightingCompilationStatus.DRAFT
    assert service.save_notes("SHT-001", "Changed").production_notes == "Changed"


def test_upstream_change_makes_lighting_stale_and_refresh_preserves_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Preserve this user review note.")
    packages.value = packages._package("source-2", "PP-SHT-001-B")

    stale = service.draft("SHT-001")
    assert stale is not None
    assert not service.is_current(stale)
    with pytest.raises(LightingCompilerError, match="stale"):
        service.mark_ready("SHT-001")

    refreshed = service.rebase_to_current_package("SHT-001")
    assert service.is_current(refreshed)
    assert refreshed.source_package_id == "PP-SHT-001-B"
    assert refreshed.production_notes == "Preserve this user review note."


def test_current_refresh_rebuilds_from_governed_compiled_lighting(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Preserve current review note.")
    governed = packages._lighting()
    governed["color_temperature_k"] = 4100
    packages.value = replace(
        packages.value,
        lighting={"governed": governed, "production": {"color_temperature_k": 4100}},
    )

    refreshed = service.rebase_to_current_package("SHT-001")

    assert refreshed.lighting["color_temperature_k"] == 4100
    assert "governed" not in refreshed.lighting
    assert "production" not in refreshed.lighting
    assert refreshed.production_notes == "Preserve current review note."


def test_incomplete_governed_lighting_is_rejected_at_approval(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(packages.value, lighting={"lighting_intent": "naturalistic"})
    service.create_from_current_package("SHT-001")

    with pytest.raises(LightingCompilerError, match="incomplete"):
        service.mark_ready("SHT-001")
