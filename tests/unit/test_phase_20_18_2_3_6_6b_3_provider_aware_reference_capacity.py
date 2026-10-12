"""Phase 20.18.2.3.6.6b.3 provider-aware reference governance regressions."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
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
from vscs.application.provider_reference_capacity import (
    project_provider_reference_capacity,
)
from vscs.infrastructure.production_execution.provider_policy_profiles import (
    LTX25_CANDIDATE_C_POLICY_PROFILE_ID,
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)


@dataclass(frozen=True)
class _CapacityReference:
    reference_id: str
    role: ReferenceRole
    priority: ReferencePriority
    provider_ready: bool = True


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


def test_h3_capacity_selects_required_then_provider_ready_preferred() -> None:
    registry = default_provider_policy_profile_registry()
    profile = registry.require(MINIMAX_H3_POLICY_PROFILE_ID)
    references = (
        _CapacityReference("REF-SANDRA", ReferenceRole.PRIMARY_IDENTITY, ReferencePriority.REQUIRED),
        _CapacityReference("REF-JAMES", ReferenceRole.SECONDARY_IDENTITY, ReferencePriority.REQUIRED),
        _CapacityReference(
            "REF-BRIDGE",
            ReferenceRole.ENVIRONMENT_REFERENCE,
            ReferencePriority.REQUIRED,
        ),
        _CapacityReference(
            "REF-XORIX",
            ReferenceRole.ENVIRONMENT_REFERENCE,
            ReferencePriority.REQUIRED,
        ),
        _CapacityReference(
            "REF-ORBIT",
            ReferenceRole.ENVIRONMENT_REFERENCE,
            ReferencePriority.PREFERRED,
        ),
        _CapacityReference(
            "REF-SHIP",
            ReferenceRole.BACKGROUND_IDENTITY,
            ReferencePriority.PREFERRED,
        ),
    )

    projection = project_provider_reference_capacity(profile, references)

    assert projection.passed is True
    assert projection.capacity == 5
    assert projection.selected_reference_ids == (
        "REF-SANDRA",
        "REF-JAMES",
        "REF-BRIDGE",
        "REF-XORIX",
        "REF-ORBIT",
    )
    assert projection.deferred_preferred_reference_ids == ("REF-SHIP",)


def test_h3_capacity_never_drops_required_reference() -> None:
    profile = default_provider_policy_profile_registry().require(MINIMAX_H3_POLICY_PROFILE_ID)
    references = tuple(
        _CapacityReference(
            f"REF-{index}",
            ReferenceRole.ENVIRONMENT_REFERENCE,
            ReferencePriority.REQUIRED,
        )
        for index in range(1, 7)
    )

    projection = project_provider_reference_capacity(profile, references)

    assert projection.passed is False
    assert projection.selected_reference_ids == ()
    assert "6 required" in str(projection.blocked_reason)
    assert "capacity 5" in str(projection.blocked_reason)


def test_ltx25_indirect_projection_does_not_fake_direct_slot_capacity() -> None:
    profile = default_provider_policy_profile_registry().require(
        LTX25_CANDIDATE_C_POLICY_PROFILE_ID
    )
    projection = project_provider_reference_capacity(
        profile,
        (
            _CapacityReference(
                "REF-SANDRA",
                ReferenceRole.PRIMARY_IDENTITY,
                ReferencePriority.REQUIRED,
            ),
        ),
    )

    assert projection.passed is True
    assert projection.indirect_projection is True
    assert projection.selected_reference_ids == ()
    assert projection.reference_projection_mode == "baked_into_governed_keyframe"


def _package() -> ProductionPackage:
    assets = (
        ("CAP-CHR-003", "character", "Supporting Character", "sandra.png"),
        ("CAP-CHR-001", "character", "Supporting Character", "james.png"),
        ("CAP-LOC-021", "location", "Location", "bridge.png"),
        ("CAP-ENV-004", "environment", "Environment Context", "orbit.png"),
        ("CAP-PLN-002", "planet", "Visible Planet", "xorix.png"),
        ("CAP-SHP-002", "ship", "Vehicle/Ship", "ship.png"),
    )
    production_assets = tuple(
        {
            "production": {
                "asset_id": asset_id,
                "category": category,
                "role": role,
                "canonical_reference": f"assets/{filename}",
            }
        }
        for asset_id, category, role, filename in assets
    )
    references = tuple(
        {
            "asset_id": asset_id,
            "canonical_reference": f"assets/{filename}",
        }
        for asset_id, _category, _role, filename in assets
    )
    return ProductionPackage(
        package_id="PP-SHT-003",
        shot_id="EP-001-SCN-001-SHT-003",
        schema_version="1.0",
        source_fingerprint="source",
        package_fingerprint="package",
        provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
        story_context={},
        shot={"target_runtime_seconds": 10},
        assets=production_assets,
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


def _write_assets(root: Path) -> dict[str, Path]:
    names = {
        "CAP-CHR-003": "sandra.png",
        "CAP-CHR-001": "james.png",
        "CAP-LOC-021": "bridge.png",
        "CAP-ENV-004": "orbit.png",
        "CAP-PLN-002": "xorix.png",
        "CAP-SHP-002": "ship.png",
    }
    result: dict[str, Path] = {}
    for asset_id, filename in names.items():
        path = root / "assets" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(asset_id.encode("utf-8"))
        result[asset_id] = path
    return result


def _review(
    asset_id: str,
    source: Path,
    *,
    role: ReferenceRole,
    priority: ReferencePriority,
    subject_type: ReferenceSubjectType,
) -> SuitabilityReferenceReview:
    return SuitabilityReferenceReview(
        reference_id=f"REF-{asset_id}",
        asset_id=asset_id,
        role=role,
        reference_class=ReferenceClass.CANONICAL_MASTER,
        subject_type=subject_type,
        priority=priority,
        source_path=str(source),
        canonical_source_id=asset_id,
        label=asset_id,
        width=1672,
        height=941,
        provider_ready=True,
        provider_profiles=("production-video-16x9",),
        framing_type="full_asset",
        coverage="full_required_asset",
        required_features_visible=True,
        identity_visible=True,
        full_required_asset_visible=True,
    )


def _sht003_reviews(paths: dict[str, Path]) -> tuple[SuitabilityReferenceReview, ...]:
    return (
        _review(
            "CAP-CHR-003",
            paths["CAP-CHR-003"],
            role=ReferenceRole.PRIMARY_IDENTITY,
            priority=ReferencePriority.REQUIRED,
            subject_type=ReferenceSubjectType.CHARACTER,
        ),
        _review(
            "CAP-CHR-001",
            paths["CAP-CHR-001"],
            role=ReferenceRole.SECONDARY_IDENTITY,
            priority=ReferencePriority.REQUIRED,
            subject_type=ReferenceSubjectType.CHARACTER,
        ),
        _review(
            "CAP-LOC-021",
            paths["CAP-LOC-021"],
            role=ReferenceRole.ENVIRONMENT_REFERENCE,
            priority=ReferencePriority.REQUIRED,
            subject_type=ReferenceSubjectType.ENVIRONMENT,
        ),
        _review(
            "CAP-ENV-004",
            paths["CAP-ENV-004"],
            role=ReferenceRole.ENVIRONMENT_REFERENCE,
            priority=ReferencePriority.PREFERRED,
            subject_type=ReferenceSubjectType.ENVIRONMENT,
        ),
        _review(
            "CAP-PLN-002",
            paths["CAP-PLN-002"],
            role=ReferenceRole.ENVIRONMENT_REFERENCE,
            priority=ReferencePriority.REQUIRED,
            subject_type=ReferenceSubjectType.ENVIRONMENT,
        ),
        _review(
            "CAP-SHP-002",
            paths["CAP-SHP-002"],
            role=ReferenceRole.BACKGROUND_IDENTITY,
            priority=ReferencePriority.PREFERRED,
            subject_type=ReferenceSubjectType.SHIP,
        ),
    )


def test_sht003_supporting_characters_get_deterministic_primary_secondary_roles(
    tmp_path: Path,
) -> None:
    package = _package()
    _write_assets(tmp_path)
    service = GovernedReferenceSuitabilityReviewService(_Projects(tmp_path))  # type: ignore[arg-type]

    candidates = service.candidates_for_package(package)
    by_asset = {candidate.asset_id: candidate for candidate in candidates}

    assert by_asset["CAP-CHR-003"].suggested_role is ReferenceRole.PRIMARY_IDENTITY
    assert by_asset["CAP-CHR-001"].suggested_role is ReferenceRole.SECONDARY_IDENTITY


def test_sht003_review_records_and_persists_h3_capacity_projection(tmp_path: Path) -> None:
    package = _package()
    paths = _write_assets(tmp_path)
    reviews = _sht003_reviews(paths)
    registry = default_provider_policy_profile_registry()
    service = GovernedReferenceSuitabilityReviewService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        provider_policies=registry,
    )
    target = SuitabilityReviewTarget(
        provider_id="minimax-h3-ref2va",
    )

    plan = service.approve_and_resolve(
        package,
        target=target,
        references=reviews,
    )

    projection = plan["provider_capacity_projection"]
    assert projection["capacity"] == 5
    assert projection["selected_reference_ids"] == [
        "REF-CAP-CHR-003",
        "REF-CAP-CHR-001",
        "REF-CAP-LOC-021",
        "REF-CAP-PLN-002",
        "REF-CAP-ENV-004",
    ]
    assert projection["deferred_preferred_reference_ids"] == ["REF-CAP-SHP-002"]

    review_path = tmp_path / "production" / (
        "governed_reference_suitability_EP-001-SCN-001-SHT-003.json"
    )
    review_payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert review_payload["target"]["provider_id"] == "minimax-h3-ref2va"
    assert review_payload["provider_capacity_projection"]["passed"] is True


def test_sht003_approval_blocks_when_required_references_exceed_h3_capacity(
    tmp_path: Path,
) -> None:
    package = _package()
    paths = _write_assets(tmp_path)
    reviews = tuple(
        replace(review, priority=ReferencePriority.REQUIRED)
        for review in _sht003_reviews(paths)
    )
    service = GovernedReferenceSuitabilityReviewService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        provider_policies=default_provider_policy_profile_registry(),
    )

    with pytest.raises(
        GovernedReferenceSuitabilityAuthoringError,
        match=r"6 required governed direct references exceed provider capacity 5",
    ):
        service.approve_and_resolve(
            package,
            target=SuitabilityReviewTarget(provider_id="minimax-h3-ref2va"),
            references=reviews,
        )
