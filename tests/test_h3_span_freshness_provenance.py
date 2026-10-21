"""Q3.1.3.3 read-only source freshness and span-local reference regression."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)
from vscs.infrastructure.production_execution.h3_span_freshness_provenance import (
    validate_h3_span_freshness,
)


def _fixtures():
    records = [
        {"reference_id": "james", "role": "primary_identity", "priority": "required", "provider_ready": True},
        {"reference_id": "bridge", "role": "environment_reference", "priority": "preferred", "provider_ready": True},
        {"reference_id": "future-ros", "role": "secondary_identity", "priority": "required", "provider_ready": True},
    ]
    compiled = SimpleNamespace(
        shot_id="SHOT-TEST",
        package_fingerprint="package-one",
        source_package_fingerprint="original",
        reference_plan={"status": "passed", "references": records},
    )
    refreshed = SimpleNamespace(
        shot_id=compiled.shot_id,
        package_fingerprint=compiled.package_fingerprint,
        source_package_fingerprint=compiled.source_package_fingerprint,
        reference_plan={"status": "passed", "references": [dict(item) for item in records]},
    )
    span = SimpleNamespace(
        span_id="span-1",
        sequence_number=1,
        reference_slots=(SimpleNamespace(reference_id="james"), SimpleNamespace(reference_id="bridge")),
        active_reference_ids=("james", "bridge"),
    )
    span_plan = SimpleNamespace(
        shot_id="SHOT-TEST",
        source_package_fingerprint="package-one",
        fingerprint="span-fingerprint",
        spans=(span,),
    )
    execution = SimpleNamespace(
        span_id="span-1",
        sequence_number=1,
        source_span_input_plan_fingerprint="span-fingerprint",
        reference_slots=(SimpleNamespace(reference_id="james"), SimpleNamespace(reference_id="bridge")),
        deferred_reference_ids=(),
    )
    projection = ProviderReferenceCapacityProjection(
        provider_id="minimax-h3-ref2va",
        provider_profile_id="H3",
        provider_profile_fingerprint="policy-fingerprint",
        model_family="h3",
        reference_projection_mode="direct_span_scoped_canonical_refs",
        capacity=2,
        required_reference_ids=("james",),
        preferred_ready_reference_ids=("bridge",),
        selected_reference_ids=("james", "bridge"),
        deferred_preferred_reference_ids=(),
        indirect_projection=False,
    )
    return compiled, refreshed, span_plan, execution, projection


def test_valid_span_excludes_future_reference_and_is_deterministic():
    args = _fixtures()
    report = validate_h3_span_freshness(*args)
    assert report.advisory_only
    assert report.span_id == "span-1"
    assert report.review.governed_selected_ids == ("james", "bridge")
    assert report.fingerprint == validate_h3_span_freshness(*args).fingerprint


def test_stale_package_fails_closed():
    compiled, refreshed, span_plan, execution, projection = _fixtures()
    refreshed.package_fingerprint = "changed"
    with pytest.raises(H3ReferenceGovernanceError, match="stale"):
        validate_h3_span_freshness(compiled, refreshed, span_plan, execution, projection)


def test_stale_reference_plan_fails_closed():
    compiled, refreshed, span_plan, execution, projection = _fixtures()
    refreshed.reference_plan["references"][0]["priority"] = "preferred"
    with pytest.raises(H3ReferenceGovernanceError, match="stale"):
        validate_h3_span_freshness(compiled, refreshed, span_plan, execution, projection)


def test_span_plan_fingerprint_mismatch_fails_closed():
    compiled, refreshed, span_plan, execution, projection = _fixtures()
    execution.source_span_input_plan_fingerprint = "old"
    with pytest.raises(H3ReferenceGovernanceError, match="provenance"):
        validate_h3_span_freshness(compiled, refreshed, span_plan, execution, projection)


def test_future_only_reference_in_projection_fails_closed():
    compiled, refreshed, span_plan, execution, projection = _fixtures()
    projection = replace(
        projection,
        preferred_ready_reference_ids=("future-ros",),
        selected_reference_ids=("james", "future-ros"),
    )
    with pytest.raises(H3ReferenceGovernanceError, match="differs"):
        validate_h3_span_freshness(compiled, refreshed, span_plan, execution, projection)


def test_unknown_span_fails_closed():
    compiled, refreshed, span_plan, execution, projection = _fixtures()
    execution.span_id = "span-99"
    with pytest.raises(H3ReferenceGovernanceError, match="Exact governed span"):
        validate_h3_span_freshness(compiled, refreshed, span_plan, execution, projection)
