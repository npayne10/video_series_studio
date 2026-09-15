from __future__ import annotations

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
    SuitabilityReferenceReview,
    SuitabilityReviewTarget,
)
from vscs.application.governed_reference_suitability_review import (
    GovernedReferenceSuitabilityReviewService,
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
        shot={},
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
    asset_id: str | None = None,
    role: ReferenceRole = ReferenceRole.SCENE_COMPOSITION_ANCHOR,
    contains_subjects: tuple[str, ...] = (),
    contains_environments: tuple[str, ...] = (),
) -> SuitabilityReferenceReview:
    return SuitabilityReferenceReview(
        reference_id=f"REF-{asset_id or 'COMPOSITION'}",
        asset_id=asset_id,
        role=role,
        reference_class=(
            ReferenceClass.CANONICAL_MASTER if asset_id else ReferenceClass.SHOT_COMPOSITE
        ),
        subject_type=(
            ReferenceSubjectType.CHARACTER
            if asset_id
            else ReferenceSubjectType.MULTI_SUBJECT_SCENE
        ),
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
    )


def test_approval_requires_every_governed_visual_asset_to_be_covered(tmp_path: Path) -> None:
    package = _package()
    source = tmp_path / "composition.png"
    source.write_bytes(b"composition")
    service = GovernedReferenceSuitabilityReviewService(_Projects(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(
        GovernedReferenceSuitabilityAuthoringError,
        match="CAP-CHR-001, CAP-LOC-008",
    ):
        service.approve_and_resolve(
            package,
            target=SuitabilityReviewTarget(),
            references=(
                _review(source, contains_subjects=("CAP-CHR-003",)),
            ),
        )


def test_approval_rejects_reversed_direct_character_identity_roles(tmp_path: Path) -> None:
    package = _package()
    sandra = tmp_path / "sandra.png"
    james = tmp_path / "james.png"
    bridge = tmp_path / "bridge.png"
    for path in (sandra, james, bridge):
        path.write_bytes(path.name.encode("utf-8"))
    service = GovernedReferenceSuitabilityReviewService(_Projects(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(
        GovernedReferenceSuitabilityAuthoringError,
        match=r"CAP-CHR-003.*primary_identity",
    ):
        service.approve_and_resolve(
            package,
            target=SuitabilityReviewTarget(),
            references=(
                _review(
                    sandra,
                    asset_id="CAP-CHR-003",
                    role=ReferenceRole.SECONDARY_IDENTITY,
                ),
                _review(
                    james,
                    asset_id="CAP-CHR-001",
                    role=ReferenceRole.PRIMARY_IDENTITY,
                ),
                _review(
                    bridge,
                    asset_id="CAP-LOC-008",
                    role=ReferenceRole.ENVIRONMENT_REFERENCE,
                ),
            ),
        )


def test_complete_composition_review_can_approve_and_persist(tmp_path: Path) -> None:
    package = _package()
    source = tmp_path / "composition.png"
    source.write_bytes(b"composition")
    service = GovernedReferenceSuitabilityReviewService(_Projects(tmp_path))  # type: ignore[arg-type]

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
