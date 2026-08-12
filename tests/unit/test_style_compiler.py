"""Phase 19.4.7 Style Compiler tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.style_compiler import (
    StyleCompilationStatus,
    StyleCompilerError,
    StyleCompilerService,
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
            story_context={},
            shot={
                "shot_id": "SHT-001",
                "visual_style": "grounded hard science-fiction realism",
                "tone": "restrained and observational",
            },
            assets=(
                {"production": {"asset_id": "CAP-CHR-001"}},
                {"production": {"asset_id": "CAP-SHP-001"}},
            ),
            camera={
                "production": {
                    "shot_size": "medium_close",
                    "movement": "static",
                    "lens_family": "normal",
                    "screen_direction": "preserve_previous",
                }
            },
            lighting={
                "production": {
                    "lighting_intent": "practical_motivated",
                    "key_quality": "soft",
                    "color_temperature_k": 4300,
                }
            },
            environment={"environment_plan_id": "ENV-BRIDGE"},
            action_performance={},
            continuity={
                "production": {
                    "opening_state": "James stands beside Cheryl.",
                    "closing_state": "James turns toward the console.",
                    "inheritance_mode": "previous-shot-closing-state",
                }
            },
            style={},
            dialogue=(),
            effects=(),
            references=(
                {
                    "asset_id": "CAP-CHR-001",
                    "canonical_reference": "refs/james.png",
                },
            ),
            universal_description={},
            provider_outputs={},
            validation={
                "assets_complete": True,
                "camera_complete": True,
                "lighting_complete": True,
                "continuity_complete": True,
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
            package_id="PP-SHT-001-STYLE",
            package_fingerprint="style-fingerprint",
            style=dict(data["style"]),
            validation=dict(data["validation"]),
            status=ProductionPackageStatus.COMPILING,
        )
        self.value = derived
        self.history.append(derived)
        return derived


def _service(tmp_path: Path):
    packages = _Packages()
    service = StyleCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
    )
    return service, packages


def test_create_assembles_style_only_from_governed_authority(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    draft = service.create_from_current_package("SHT-001")
    style = draft.style_value()

    assert style["declared_style"] == "grounded hard science-fiction realism"
    assert style["declared_tone"] == "restrained and observational"
    assert style["camera_language"]["movement"] == "static"
    assert style["lighting_language"]["color_temperature_k"] == 4300
    assert style["asset_ids"] == ["CAP-CHR-001", "CAP-SHP-001"]
    assert style["provider_neutral"] is True


def test_missing_declared_style_is_not_invented(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(packages.value, shot={"shot_id": "SHT-001"})

    draft = service.create_from_current_package("SHT-001")

    assert draft.style_value()["declared_style"] == ""
    assert draft.style_value()["declared_tone"] == ""


def test_ready_compiles_style_and_locks_notes(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "User approves governed production style.")
    ready = service.mark_ready("SHT-001")

    assert ready.status is StyleCompilationStatus.READY
    assert packages.value.style["production"]["provider_neutral"] is True
    assert packages.value.validation["style_complete"] is True
    assert (
        packages.value.validation["style_review_notes"]
        == "User approves governed production style."
    )
    with pytest.raises(StyleCompilerError, match="return to Draft"):
        service.save_notes("SHT-001", "Changed")


def test_style_finalization_requires_upstream_compilers_ready(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    packages.value = replace(
        packages.value,
        validation={"lighting_complete": True},
    )
    service.create_from_current_package("SHT-001")

    assert service.missing_prerequisites("SHT-001") == ("Assets", "Camera", "Continuity")
    with pytest.raises(StyleCompilerError, match="Assets, Camera, Continuity"):
        service.mark_ready("SHT-001")


def test_upstream_camera_change_makes_draft_stale_and_refresh_preserves_notes(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.save_notes("SHT-001", "Preserve style review note.")
    packages.value = replace(
        packages.value,
        camera={"production": {"shot_size": "wide", "movement": "tracking"}},
    )

    stale = service.draft("SHT-001")
    assert stale is not None
    assert not service.is_current(stale)
    with pytest.raises(StyleCompilerError, match="stale"):
        service.mark_ready("SHT-001")

    refreshed = service.rebase_to_current_package("SHT-001")
    assert service.is_current(refreshed)
    assert refreshed.production_notes == "Preserve style review note."
    assert refreshed.style_value()["camera_language"]["shot_size"] == "wide"


def test_return_to_draft_allows_review_after_ready(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    service.create_from_current_package("SHT-001")
    service.mark_ready("SHT-001")

    draft = service.return_to_draft("SHT-001")

    assert draft.status is StyleCompilationStatus.DRAFT
