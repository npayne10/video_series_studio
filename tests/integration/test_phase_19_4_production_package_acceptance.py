"""Phase 19.4 end-to-end review/acceptance integration tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.production_package_acceptance import (
    AcceptanceStatus,
    ProductionPackageAcceptanceService,
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
        reference = {
            "asset_id": "CAP-CHR-001",
            "canonical_reference": "assets/characters/james.png",
        }
        self.value = ProductionPackage(
            package_id="PP-SHT-001-PROVIDER",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="planning-source",
            package_fingerprint="package-v1",
            provenance=ProductionPackageProvenance(
                "PIP-SHT-001",
                "planning-source",
                "PRV-SHT-001",
                "planning-review",
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
            universal_description={
                "production": {
                    "assets": [{"asset_id": "CAP-CHR-001"}],
                    "canonical_references": [reference],
                    "consistency_findings": [],
                }
            },
            provider_outputs={
                "comfyui": {
                    "status": "ready",
                    "production_notes": "",
                    "governed": {
                        "provider_id": "comfyui",
                        "contract": "vscs.comfyui.production-input.v1",
                        "execution": "not-submitted",
                        "canonical_references": [reference],
                    },
                }
            },
            validation={
                "action_performance_complete": True,
                "assets_complete": True,
                "camera_complete": True,
                "lighting_complete": True,
                "continuity_complete": True,
                "style_complete": True,
                "universal_description_complete": True,
                "cross_authority_consistent": True,
                "provider_comfyui_complete": True,
            },
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

    def draft(self, _shot_id: str):
        return self.value

    def is_current(self, _draft) -> bool:
        return True

    def consistency_findings(self, _shot_id: str) -> tuple[str, ...]:
        return ()


class _Provider:
    def __init__(self, packages: _Packages) -> None:
        self.packages = packages
        self.value = SimpleNamespace(
            status=ProviderCompilationStatus.READY,
            dependency_fingerprint="provider-v1",
            output_value=self._output,
        )

    def _output(self) -> dict:
        return dict(self.packages.value.provider_outputs["comfyui"]["governed"])

    def draft(self, _shot_id: str, _provider_id: str):
        return self.value

    def is_current(self, _draft) -> bool:
        return True


def _pipeline(tmp_path: Path):
    packages = _Packages()
    review = ProductionPackageReviewService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _Universal(),  # type: ignore[arg-type]
        _Provider(packages),  # type: ignore[arg-type]
    )
    acceptance = ProductionPackageAcceptanceService(
        packages,  # type: ignore[arg-type]
        review,
    )
    return packages, review, acceptance


def test_human_approval_completes_phase_19_4_acceptance(tmp_path: Path) -> None:
    _packages, review, acceptance = _pipeline(tmp_path)

    before = acceptance.assess("SHT-001")
    assert before.status is AcceptanceStatus.NOT_READY
    assert not review.execution_authorized("SHT-001")

    validation = review.validate("SHT-001")
    assert validation.validation_passed
    assert review.validation_confirmed("SHT-001")

    approved = review.approve(
        "SHT-001",
        reviewed_by="Acceptance Tester",
        notes="Phase 19.4 package accepted for downstream production.",
    )
    assert approved.status is ReviewStatus.APPROVED

    after = acceptance.require_accepted("SHT-001")
    assert after.status is AcceptanceStatus.ACCEPTED
    assert review.execution_authorized("SHT-001")


def test_upstream_package_change_invalidates_previous_phase_19_4_acceptance(
    tmp_path: Path,
) -> None:
    packages, review, acceptance = _pipeline(tmp_path)
    review.validate("SHT-001")
    review.approve("SHT-001", reviewed_by="Acceptance Tester")
    assert acceptance.assess("SHT-001").accepted

    packages.value = replace(
        packages.value,
        package_id="PP-SHT-001-PROVIDER-V2",
        package_fingerprint="package-v2",
    )

    persisted = review.current_review("SHT-001")
    assert persisted is not None
    assert persisted.status is ReviewStatus.STALE
    assert acceptance.assess("SHT-001").status is AcceptanceStatus.NOT_READY
    assert not review.execution_authorized("SHT-001")
    assert not review.validation_confirmed("SHT-001")


def test_revalidation_survives_acceptance_assessment_and_allows_reapproval(
    tmp_path: Path,
) -> None:
    packages, review, acceptance = _pipeline(tmp_path)
    review.validate("SHT-001")
    review.approve("SHT-001", reviewed_by="Acceptance Tester")

    packages.value = replace(
        packages.value,
        package_id="PP-SHT-001-PROVIDER-V2",
        package_fingerprint="package-v2",
    )
    assert acceptance.assess("SHT-001").status is AcceptanceStatus.NOT_READY
    assert not review.validation_confirmed("SHT-001")

    validation = review.validate("SHT-001")
    assert validation.validation_passed
    assert review.validation_confirmed("SHT-001")

    # Production Review rendering performs an acceptance assessment before the
    # Approve for Production action. That read must not destroy fresh validation.
    reassessed = acceptance.assess("SHT-001")
    assert reassessed.status is AcceptanceStatus.NOT_READY
    assert review.validation_confirmed("SHT-001")

    persisted = review.current_review("SHT-001")
    assert persisted is not None
    assert persisted.status is ReviewStatus.STALE
    assert persisted.validation_passed
    assert review.validation_confirmed("SHT-001")

    approved = review.approve("SHT-001", reviewed_by="Acceptance Tester")
    assert approved.status is ReviewStatus.APPROVED
    assert acceptance.require_accepted("SHT-001").status is AcceptanceStatus.ACCEPTED
