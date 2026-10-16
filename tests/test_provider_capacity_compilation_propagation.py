"""Reviewed capacity authority must survive ReferencePlan compilation unchanged."""

from dataclasses import replace

import pytest

from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
    ShotReference,
)
from vscs.application.provider_reference_capacity import project_provider_reference_capacity
from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilationError,
    ProductionPackageCompiler,
)
from vscs.application.production_execution.provider_policy_profiles import (
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)


def _references(required: int = 5, preferred: int = 2) -> tuple[ShotReference, ...]:
    return tuple(
        ShotReference(
            reference_id=f"REF-{i}",
            role=ReferenceRole.PRIMARY_IDENTITY,
            reference_class=ReferenceClass.CANONICAL_MASTER,
            priority=ReferencePriority.REQUIRED if i < required else ReferencePriority.PREFERRED,
            subject_type=ReferenceSubjectType.CHARACTER,
            source_path=f"reference-{i}.png",
            provider_ready=True,
        )
        for i in range(required + preferred)
    )


def _approved(references: tuple[ShotReference, ...]) -> dict[str, object]:
    profile = default_provider_policy_profile_registry().require(MINIMAX_H3_POLICY_PROFILE_ID)
    return project_provider_reference_capacity(profile, references).to_dict()


def test_reviewed_five_required_two_preferred_projection_survives_compilation():
    references = _references()
    destination: dict[str, object] = {}
    authority = _approved(references)
    assert authority["passed"] is True
    assert len(authority["selected_reference_ids"]) == 5
    assert len(authority["deferred_preferred_reference_ids"]) == 2

    ProductionPackageCompiler._preserve_reviewed_provider_capacity(
        {"provider_capacity_projection": authority}, references, destination
    )

    assert destination["provider_capacity_projection"] == authority


def test_legacy_reference_plan_without_reviewed_projection_stays_legacy():
    destination: dict[str, object] = {}
    ProductionPackageCompiler._preserve_reviewed_provider_capacity(
        {}, _references(), destination
    )
    assert destination == {}


@pytest.mark.parametrize("field,value", [
    ("provider_profile_fingerprint", "stale"),
    ("capacity", 999),
    ("selected_reference_ids", ["REF-0"]),
    ("deferred_preferred_reference_ids", []),
    ("passed", False),
])
def test_mismatched_reviewed_projection_fails_closed(field, value):
    references = _references()
    authority = _approved(references)
    authority[field] = value
    with pytest.raises(ProductionPackageCompilationError, match="stale"):
        ProductionPackageCompiler._preserve_reviewed_provider_capacity(
            {"provider_capacity_projection": authority}, references, {}
        )


def test_changed_priority_invalidates_reviewed_capacity():
    original = _references()
    modified = (replace(original[0], priority=ReferencePriority.PREFERRED), *original[1:])
    with pytest.raises(ProductionPackageCompilationError, match="stale"):
        ProductionPackageCompiler._preserve_reviewed_provider_capacity(
            {"provider_capacity_projection": _approved(original)}, modified, {}
        )


def test_required_over_capacity_is_not_preserved():
    references = _references(required=6, preferred=1)
    authority = _approved(references)
    assert authority["passed"] is False
    with pytest.raises(ProductionPackageCompilationError, match="blocked"):
        ProductionPackageCompiler._preserve_reviewed_provider_capacity(
            {"provider_capacity_projection": authority}, references, {}
        )
