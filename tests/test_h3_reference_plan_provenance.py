"""Q3.1.3.2 provenance reconciliation tests; no production filesystem."""

from types import SimpleNamespace

import pytest

from vscs.application.acpp.reference_roles import ReferencePriority, ReferenceRole
from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection
from vscs.infrastructure.production_execution.h3_reference_plan_provenance import (
    review_compiled_h3_reference_provenance,
)
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)


def _compiled() -> SimpleNamespace:
    return SimpleNamespace(
        shot_id="EP-001-SCN-001-SHT-TEST",
        package_fingerprint="package-sha",
        source_package_fingerprint="source-sha",
        reference_plan={
            "status": "passed",
            "references": [
                {
                    "reference_id": "james",
                    "role": ReferenceRole.CHARACTER_IDENTITY.value,
                    "priority": ReferencePriority.REQUIRED.value,
                    "provider_ready": True,
                },
                {
                    "reference_id": "planet",
                    "role": ReferenceRole.ENVIRONMENT_REFERENCE.value,
                    "priority": ReferencePriority.PREFERRED.value,
                    "provider_ready": True,
                },
            ],
        },
    )


def _projection() -> ProviderReferenceCapacityProjection:
    return ProviderReferenceCapacityProjection(
        provider_id="minimax-h3-ref2va",
        provider_profile_id="p",
        provider_profile_fingerprint="profile-sha",
        model_family="minimax-h3",
        reference_projection_mode="direct_span_scoped_canonical_refs",
        capacity=1,
        required_reference_ids=("james",),
        preferred_ready_reference_ids=("planet",),
        selected_reference_ids=("james",),
        deferred_preferred_reference_ids=("planet",),
        indirect_projection=False,
    )


def test_provenance_is_stable_and_preserves_authority() -> None:
    compiled = _compiled()
    original = str(compiled.reference_plan)
    report = review_compiled_h3_reference_provenance(
        compiled, _projection(), guide_overlap_ids=frozenset({"planet"})
    )
    assert report.compiled_package_fingerprint == "package-sha"
    assert report.provider_profile_fingerprint == "profile-sha"
    assert report.review.governed_selected_ids == ("james",)
    assert report.review.governed_deferred_ids == ("planet",)
    assert report.advisory_only
    assert str(compiled.reference_plan) == original
    assert report.report_fingerprint == review_compiled_h3_reference_provenance(
        compiled, _projection(), guide_overlap_ids=frozenset({"planet"})
    ).report_fingerprint


def test_missing_authoritative_reference_fails_closed() -> None:
    compiled = _compiled()
    compiled.reference_plan["references"].pop()
    with pytest.raises(H3ReferenceGovernanceError, match="span activation authority"):
        review_compiled_h3_reference_provenance(compiled, _projection())


def test_invalid_status_fails_closed() -> None:
    compiled = _compiled()
    compiled.reference_plan["status"] = "blocked"
    with pytest.raises(H3ReferenceGovernanceError, match="did not pass"):
        review_compiled_h3_reference_provenance(compiled, _projection())
