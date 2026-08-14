"""Phase 19.4.11 final Production Package acceptance tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.production_package_acceptance import (
    AcceptanceStatus,
    ProductionPackageAcceptanceError,
    ProductionPackageAcceptanceService,
)
from vscs.application.production_package_review import ReviewStatus


class _Packages:
    def __init__(self) -> None:
        reference = {
            "asset_id": "CAP-CHR-001",
            "canonical_reference": "assets/characters/james.png",
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
            package_id="PP-SHT-001-FINAL",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="package-final",
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
            universal_description={"production": {"canonical_references": [reference]}},
            provider_outputs={
                "comfyui": {
                    "status": "ready",
                    "governed": {
                        "provider_id": "comfyui",
                        "contract": "vscs.comfyui.production-input.v1",
                        "execution": "not-submitted",
                        "canonical_references": [reference],
                    },
                }
            },
            validation=validation,
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value


class _Reviews:
    def __init__(self) -> None:
        self.status = ReviewStatus.APPROVED

    def current_review(self, _shot_id: str, _provider_id: str):
        return type("Review", (), {"status": self.status})()

    def execution_authorized(self, _shot_id: str, _provider_id: str) -> bool:
        return self.status is ReviewStatus.APPROVED


def _service():
    packages = _Packages()
    reviews = _Reviews()
    service = ProductionPackageAcceptanceService(
        packages,  # type: ignore[arg-type]
        reviews,  # type: ignore[arg-type]
    )
    return service, packages, reviews


def test_complete_reviewed_package_is_accepted() -> None:
    service, _packages, _reviews = _service()
    report = service.assess("sht-001")
    assert report.status is AcceptanceStatus.ACCEPTED
    assert report.accepted
    assert report.package_id == "PP-SHT-001-FINAL"
    assert all(check.passed for check in report.checks)


def test_missing_compiler_authority_blocks_acceptance() -> None:
    service, packages, _reviews = _service()
    validation = dict(packages.value.validation)
    validation["continuity_complete"] = False
    packages.value = replace(packages.value, validation=validation)
    report = service.assess("SHT-001")
    assert not report.accepted
    assert any(
        check.code == "authority.continuity_complete" and not check.passed
        for check in report.checks
    )


def test_provider_must_remain_not_submitted_at_acceptance_boundary() -> None:
    service, packages, _reviews = _service()
    outputs = dict(packages.value.provider_outputs)
    comfyui = dict(outputs["comfyui"])
    governed = dict(comfyui["governed"])
    governed["execution"] = "submitted"
    comfyui["governed"] = governed
    outputs["comfyui"] = comfyui
    packages.value = replace(packages.value, provider_outputs=outputs)
    report = service.assess("SHT-001")
    assert not report.accepted
    assert any(
        check.code == "provider.not_submitted" and not check.passed for check in report.checks
    )


def test_provider_must_cover_all_universal_canonical_references() -> None:
    service, packages, _reviews = _service()
    outputs = dict(packages.value.provider_outputs)
    comfyui = dict(outputs["comfyui"])
    governed = dict(comfyui["governed"])
    governed["canonical_references"] = []
    comfyui["governed"] = governed
    outputs["comfyui"] = comfyui
    packages.value = replace(packages.value, provider_outputs=outputs)
    report = service.assess("SHT-001")
    assert not report.accepted
    assert any(
        check.code == "canonical.provider_coverage" and not check.passed for check in report.checks
    )


def test_stale_human_review_blocks_acceptance() -> None:
    service, _packages, reviews = _service()
    reviews.status = ReviewStatus.STALE
    report = service.assess("SHT-001")
    assert not report.accepted
    assert any(check.code == "review.current" and not check.passed for check in report.checks)
    assert any(check.code == "review.approved" and not check.passed for check in report.checks)


def test_require_accepted_reports_all_failed_integration_checks() -> None:
    service, _packages, reviews = _service()
    reviews.status = ReviewStatus.CHANGES_REQUIRED
    with pytest.raises(ProductionPackageAcceptanceError, match="not accepted"):
        service.require_accepted("SHT-001")
