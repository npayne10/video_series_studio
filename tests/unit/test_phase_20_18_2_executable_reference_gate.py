from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.governed_reference_plan_source import (
    PersistedGovernedReferencePlanSource,
)
from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilationError,
    ProductionPackageCompilerService,
)


class _Projects:
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory


def _reference_plan(*, status: str = "passed") -> dict[str, object]:
    diagnostics: list[dict[str, object]] = []
    if status != "passed":
        diagnostics.append(
            {
                "severity": "error",
                "code": "REFERENCE_NOT_PROVIDER_READY",
                "message": "Required identity reference is not provider-ready.",
                "reference_id": "REF-CHR-001",
            }
        )
    return {
        "schema_version": "1.0",
        "status": status,
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
            "aspect_tolerance": 0.03,
        },
        "references": [
            {
                "reference_id": "REF-CHR-001",
                "asset_id": "CAP-CHR-001",
                "role": "primary_identity",
                "reference_class": "provider_ready_derivative",
                "priority": "required",
                "subject_type": "character",
                "source_path": "references/character.png",
                "canonical_source_id": "CAP-CHR-001-MASTER",
                "width": 1280,
                "height": 720,
                "provider_ready": status == "passed",
                "provider_profiles": ["production-video-16x9"],
                "coverage": {
                    "framing_type": "full_body",
                    "coverage": "full_required_asset",
                    "required_features_visible": True,
                    "identity_visible": True,
                    "full_required_asset_visible": True,
                },
            }
        ],
        "diagnostics": diagnostics,
    }


def test_reference_free_authority_remains_compilable_without_governed_plan() -> None:
    service = ProductionPackageCompilerService()

    assert service._reference_plan_payload({"canonical_references": []}, "SHT-001") is None


def test_canonical_visual_authority_requires_governed_plan_before_execution_compile() -> None:
    service = ProductionPackageCompilerService()
    production = {
        "canonical_references": [
            {
                "asset_id": "CAP-CHR-001",
                "canonical_reference": "references/james.png",
            }
        ]
    }

    with pytest.raises(
        ProductionPackageCompilationError,
        match="no provider-ready governed ReferencePlan has been persisted",
    ):
        service._reference_plan_payload(production, "EP-001-SCN-001-SHT-002")


def test_failed_embedded_governed_plan_blocks_execution_compile() -> None:
    service = ProductionPackageCompilerService()
    production = {
        "canonical_references": [
            {
                "asset_id": "CAP-CHR-001",
                "canonical_reference": "references/james.png",
            }
        ],
        "reference_plan": _reference_plan(status="failed"),
    }

    with pytest.raises(
        ProductionPackageCompilationError,
        match="REFERENCE_NOT_PROVIDER_READY",
    ):
        service._reference_plan_payload(production, "EP-001-SCN-001-SHT-002")


def test_passing_embedded_governed_plan_is_preserved() -> None:
    service = ProductionPackageCompilerService()
    plan = _reference_plan()

    assert service._reference_plan_payload(
        {"canonical_references": [], "reference_plan": plan},
        "EP-001-SCN-001-SHT-002",
    ) == plan


def test_passing_persisted_governed_plan_is_loaded_at_executable_boundary(
    tmp_path: Path,
) -> None:
    plan = _reference_plan()
    store = PersistedGovernedReferencePlanSource(_Projects(tmp_path))  # type: ignore[arg-type]
    store.save_reference_plan(
        "EP-001-SCN-001-SHT-002",
        plan,
        provenance={"source": "phase-20.18.2-live-integration-test"},
    )
    service = ProductionPackageCompilerService(reference_root=tmp_path)

    resolved = service._reference_plan_payload(
        {
            "canonical_references": [
                {
                    "asset_id": "CAP-CHR-001",
                    "canonical_reference": "references/james.png",
                }
            ]
        },
        "EP-001-SCN-001-SHT-002",
    )

    assert resolved == plan


def test_failed_persisted_governed_plan_blocks_execution_compile(tmp_path: Path) -> None:
    plan = _reference_plan(status="failed")
    store = PersistedGovernedReferencePlanSource(_Projects(tmp_path))  # type: ignore[arg-type]
    store.save_reference_plan("EP-001-SCN-001-SHT-002", plan)
    service = ProductionPackageCompilerService(reference_root=tmp_path)

    with pytest.raises(
        ProductionPackageCompilationError,
        match="REFERENCE_NOT_PROVIDER_READY",
    ):
        service._reference_plan_payload(
            {
                "canonical_references": [
                    {
                        "asset_id": "CAP-CHR-001",
                        "canonical_reference": "references/james.png",
                    }
                ]
            },
            "EP-001-SCN-001-SHT-002",
        )
