from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
)
from vscs.application.governed_reference_suitability_authoring import (
    GovernedReferenceSuitabilityAuthoringError,
    GovernedReferenceSuitabilityAuthoringService,
    SuitabilityReferenceReview,
    SuitabilityReviewTarget,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


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


def _review(
    source: Path,
    *,
    reference_id: str = "LIVE-COMPOSITION",
    asset_id: str | None = None,
    role: ReferenceRole = ReferenceRole.SCENE_COMPOSITION_ANCHOR,
    subject_type: ReferenceSubjectType = ReferenceSubjectType.MULTI_SUBJECT_SCENE,
    reference_class: ReferenceClass = ReferenceClass.SHOT_COMPOSITE,
    contains_subjects: tuple[str, ...] = (),
    contains_environments: tuple[str, ...] = (),
) -> SuitabilityReferenceReview:
    return SuitabilityReferenceReview(
        reference_id=reference_id,
        asset_id=asset_id,
        role=role,
        reference_class=reference_class,
        subject_type=subject_type,
        priority=ReferencePriority.REQUIRED,
        source_path=str(source),
        canonical_source_id=asset_id,
        label="Reviewed reference",
        width=1280,
        height=720,
        provider_ready=True,
        provider_profiles=("production-video-16x9",),
        framing_type="shot_composition",
        coverage="full_required_scene",
        required_features_visible=True,
        identity_visible=True,
        full_required_asset_visible=True,
        contains_subjects=contains_subjects,
        contains_environments=contains_environments,
        review_note="Human reviewed for provider suitability.",
    )


def test_candidates_derive_semantic_identity_roles_without_promoting_files(tmp_path: Path) -> None:
    package = _package()
    for relative in ("assets/sandra.png", "assets/james.png", "assets/bridge.png"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode("utf-8"))
    service = GovernedReferenceSuitabilityAuthoringService(_Projects(tmp_path))  # type: ignore[arg-type]

    candidates = service.candidates_for_package(package)
    by_asset = {candidate.asset_id: candidate for candidate in candidates}

    assert by_asset["CAP-CHR-003"].suggested_role is ReferenceRole.PRIMARY_IDENTITY
    assert by_asset["CAP-CHR-001"].suggested_role is ReferenceRole.SECONDARY_IDENTITY
    assert by_asset["CAP-LOC-008"].suggested_role is ReferenceRole.ENVIRONMENT_REFERENCE
    assert all(
        candidate.suggested_reference_class is ReferenceClass.CANONICAL_MASTER
        for candidate in candidates
    )
    assert by_asset["CAP-CHR-003"].file_checksum == hashlib.sha256(b"assets/sandra.png").hexdigest()


def test_save_review_writes_explicit_schema_and_recomputes_checksum(tmp_path: Path) -> None:
    package = _package()
    source = tmp_path / "references" / "composition.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"reviewed-composition")
    service = GovernedReferenceSuitabilityAuthoringService(_Projects(tmp_path))  # type: ignore[arg-type]

    path = service.save_review(
        package,
        target=SuitabilityReviewTarget(),
        references=(
            _review(
                source,
                contains_subjects=("CAP-CHR-003", "CAP-CHR-001"),
                contains_environments=("CAP-LOC-008",),
            ),
        ),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["shot_id"] == package.shot_id
    assert payload["target"]["profile_id"] == "production-video-16x9"
    assert payload["references"][0]["provider_ready"] is True
    assert (
        payload["references"][0]["file_checksum"]
        == hashlib.sha256(b"reviewed-composition").hexdigest()
    )
    assert payload["references"][0]["contains_subjects"] == [
        "CAP-CHR-003",
        "CAP-CHR-001",
    ]


def test_save_review_rejects_non_governed_asset_coverage(tmp_path: Path) -> None:
    package = _package()
    source = tmp_path / "composition.png"
    source.write_bytes(b"composition")
    service = GovernedReferenceSuitabilityAuthoringService(_Projects(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(
        GovernedReferenceSuitabilityAuthoringError,
        match="not governed by the current Production Package",
    ):
        service.save_review(
            package,
            target=SuitabilityReviewTarget(),
            references=(
                _review(
                    source,
                    contains_subjects=("CAP-CHR-003", "CAP-CHR-NOT-GOVERNED"),
                ),
            ),
        )


def test_approve_and_resolve_uses_existing_resolver_and_persists_plan(tmp_path: Path) -> None:
    package = _package()
    source = tmp_path / "composition.png"
    source.write_bytes(b"composition")
    service = GovernedReferenceSuitabilityAuthoringService(_Projects(tmp_path))  # type: ignore[arg-type]

    plan = service.approve_and_resolve(
        package,
        target=SuitabilityReviewTarget(),
        references=(
            _review(
                source,
                contains_subjects=("CAP-CHR-003", "CAP-CHR-001"),
                contains_environments=("CAP-LOC-008",),
            ),
        ),
    )

    assert plan["status"] == "passed"
    assert plan["references"][0]["role"] == "scene_composition_anchor"
    persisted = tmp_path / "production" / "governed_reference_plans.json"
    assert persisted.is_file()
    payload = json.loads(persisted.read_text(encoding="utf-8"))
    records = payload["governed_reference_plans"]
    assert records[0]["shot_id"] == package.shot_id


def test_direct_character_review_can_be_authored_without_story_specific_code(
    tmp_path: Path,
) -> None:
    package = _package()
    source = tmp_path / "sandra.png"
    source.write_bytes(b"sandra")
    service = GovernedReferenceSuitabilityAuthoringService(_Projects(tmp_path))  # type: ignore[arg-type]

    path = service.save_review(
        package,
        target=SuitabilityReviewTarget(),
        references=(
            _review(
                source,
                reference_id="LIVE-PRIMARY-CAP-CHR-003",
                asset_id="CAP-CHR-003",
                role=ReferenceRole.PRIMARY_IDENTITY,
                subject_type=ReferenceSubjectType.CHARACTER,
                reference_class=ReferenceClass.CANONICAL_MASTER,
            ),
        ),
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    reference = payload["references"][0]
    assert reference["asset_id"] == "CAP-CHR-003"
    assert reference["role"] == "primary_identity"
    assert reference["reference_class"] == "canonical_master"
