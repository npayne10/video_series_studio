"""Phase 19.4.10 Production Package Review tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.production_package_review import (
    ProductionPackageReviewService,
    ReviewStatus,
)
from vscs.application.provider_compiler import ProviderCompilationStatus
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionStatus,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        production = {
            "assets": [{"asset_id": "CAP-CHR-001"}],
            "canonical_references": [
                {
                    "asset_id": "CAP-CHR-001",
                    "canonical_reference": "assets/characters/james.png",
                }
            ],
            "consistency_findings": [],
        }
        validation = {
            "action_performance_complete": True,
            "assets_complete": True,
            "camera_complete": True,
            "lighting_complete": True,
            "continuity_complete": True,
            "style_complete": True,
            "universal_description_complete": True,
            "cross_authority_consistent": True,
            "provider_comfyui_complete": True,
        }
        self.value = ProductionPackage(
            package_id="PP-SHT-001-READY",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="package-v1",
            provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
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
            universal_description={"production": production},
            provider_outputs={},
            validation=validation,
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value


class _Universal:
    def __init__(self) -> None:
        self.value = SimpleNamespace(
            status=UniversalProductionDescriptionStatus.READY,
            dependency_fingerprint="universal-v1",
        )
        self.current = True

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft) -> bool:
        return self.current

    def consistency_findings(self, _shot_id: str) -> tuple[str, ...]:
        return ()


class _Provider:
    def __init__(self) -> None:
        self.output = {
            "provider_id": "comfyui",
            "contract": "vscs.comfyui.production-input.v1",
            "execution": "not-submitted",
            "canonical_references": [
                {
                    "asset_id": "CAP-CHR-001",
                    "canonical_reference": "assets/characters/james.png",
                }
            ],
        }

    def draft(self, _shot_id: str, _provider_id: str):
        return SimpleNamespace(
            status=ProviderCompilationStatus.READY,
            dependency_fingerprint="provider-v1",
            output_value=lambda: dict(self.output),
        )

    def is_current(self, _draft) -> bool:
        return True


def _service(tmp_path: Path):
    packages = _Packages()
    service = ProductionPackageReviewService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _Universal(),  # type: ignore[arg-type]
        _Provider(),  # type: ignore[arg-type]
    )
    return service, packages


def test_clean_package_requires_final_human_review(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    review = service.validate("sht-001")
    assert review.validation_passed
    assert review.status is ReviewStatus.REVIEW_REQUIRED
    assert review.canonical_reference_count == 1


def test_incomplete_continuity_blocks_validation(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    validation = dict(packages.value.validation)
    validation["continuity_complete"] = False
    packages.value = replace(packages.value, validation=validation)
    review = service.validate("SHT-001")
    assert not review.validation_passed
    assert any("Continuity" in item.message for item in review.findings)


def test_approval_requires_reviewer_and_is_persisted(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    with pytest.raises(ValueError, match="reviewer identity"):
        service.approve("SHT-001", reviewed_by="")
    approved = service.approve("SHT-001", reviewed_by="Neill")
    assert approved.status is ReviewStatus.APPROVED
    assert service.current_review("SHT-001") == approved


def test_authority_change_marks_review_stale(tmp_path: Path) -> None:
    service, packages = _service(tmp_path)
    service.approve("SHT-001", reviewed_by="Neill")
    packages.value = replace(packages.value, package_fingerprint="package-v2")
    review = service.current_review("SHT-001")
    assert review is not None
    assert review.status is ReviewStatus.STALE


def test_request_changes_requires_notes(tmp_path: Path) -> None:
    service, _packages = _service(tmp_path)
    with pytest.raises(ValueError, match="Review notes"):
        service.require_changes("SHT-001", reviewed_by="Neill", notes="")
    review = service.require_changes(
        "SHT-001",
        reviewed_by="Neill",
        notes="Correct the governed camera intent.",
    )
    assert review.status is ReviewStatus.CHANGES_REQUIRED
