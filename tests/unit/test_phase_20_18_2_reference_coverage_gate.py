from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.application.governed_reference_suitability import GovernedReferenceSuitabilityError
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.reference_preparing_universal_compiler import (
    GovernedReferenceAwareUniversalProductionDescriptionCompilerService,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self, package: ProductionPackage) -> None:
        self.value = package

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value


def _package() -> ProductionPackage:
    assets = (
        {
            "production": {
                "asset_id": "CAP-CHR-003",
                "category": "character",
                "role": "Dialogue Speaker",
                "canonical_reference": "assets/sandra.png",
            }
        },
        {
            "production": {
                "asset_id": "CAP-CHR-001",
                "category": "character",
                "role": "Supporting Character",
                "canonical_reference": "assets/james.png",
            }
        },
        {
            "production": {
                "asset_id": "CAP-LOC-008",
                "category": "location",
                "role": "Location",
                "canonical_reference": "assets/bridge.png",
            }
        },
    )
    references = tuple(
        {
            "asset_id": item["production"]["asset_id"],
            "canonical_reference": item["production"]["canonical_reference"],
        }
        for item in assets
    )
    return ProductionPackage(
        package_id="PP-SHT-002",
        shot_id="EP-001-SCN-001-SHT-002",
        schema_version="1.0",
        source_fingerprint="source",
        package_fingerprint="package",
        provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
        story_context={},
        shot={"title": "Dialogue delivery"},
        assets=assets,
        camera={},
        lighting={},
        environment={},
        action_performance={},
        continuity={},
        style={},
        dialogue=(),
        effects=(),
        references=references,
        universal_description={},
        provider_outputs={},
        validation={},
        status=ProductionPackageStatus.COMPILING,
    )


def _service(tmp_path: Path, package: ProductionPackage):
    return GovernedReferenceAwareUniversalProductionDescriptionCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        _Packages(package),  # type: ignore[arg-type]
    )


def _write_review(tmp_path: Path, references: list[dict[str, object]]) -> None:
    path = tmp_path / "production" / "governed_reference_suitability_EP-001-SCN-001-SHT-002.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "shot_id": "EP-001-SCN-001-SHT-002",
                "target": {
                    "width": 1280,
                    "height": 720,
                    "profile_id": "production-video-16x9",
                },
                "references": references,
            }
        ),
        encoding="utf-8",
    )


def test_explicit_suitability_cannot_silently_drop_governed_visual_assets(
    tmp_path: Path,
) -> None:
    package = _package()
    _write_review(
        tmp_path,
        [
            {
                "asset_id": "CAP-CHR-003",
                "role": "primary_identity",
            }
        ],
    )
    service = _service(tmp_path, package)

    with pytest.raises(GovernedReferenceSuitabilityError, match="CAP-CHR-001, CAP-LOC-008"):
        service._require_explicit_visual_coverage(package)

    assert not (tmp_path / "production" / "governed_reference_plans.json").exists()


def test_dialogue_speaker_and_supporting_character_roles_follow_governed_semantics(
    tmp_path: Path,
) -> None:
    package = _package()
    _write_review(
        tmp_path,
        [
            {"asset_id": "CAP-CHR-003", "role": "secondary_identity"},
            {"asset_id": "CAP-CHR-001", "role": "primary_identity"},
            {"asset_id": "CAP-LOC-008", "role": "environment_reference"},
        ],
    )
    service = _service(tmp_path, package)

    with pytest.raises(
        GovernedReferenceSuitabilityError,
        match=r"CAP-CHR-003.*primary_identity",
    ):
        service._require_explicit_visual_coverage(package)


def test_composition_coverage_may_cover_additional_governed_assets(tmp_path: Path) -> None:
    package = _package()
    _write_review(
        tmp_path,
        [
            {"asset_id": "CAP-CHR-003", "role": "primary_identity"},
            {"asset_id": "CAP-CHR-001", "role": "secondary_identity"},
            {
                "role": "scene_composition_anchor",
                "contains_environments": ["CAP-LOC-008"],
            },
        ],
    )
    service = _service(tmp_path, package)

    service._require_explicit_visual_coverage(package)
