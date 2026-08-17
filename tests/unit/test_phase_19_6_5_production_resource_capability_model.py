"""Focused regression tests for Phase 19.6.5 resource capability matching."""

from dataclasses import replace

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionResourceCatalogError,
    ProductionResourceState,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)


def _task(
    *capabilities: ProductionCapability,
    state: ProductionTaskState = ProductionTaskState.READY,
) -> ProductionTask:
    return ProductionTask(
        task_id="PT-001",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint="fingerprint-001",
            approved=True,
            approved_by="tester",
        ),
        capabilities=capabilities or (ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=state,
    )


def _resource(
    resource_id: str,
    *capabilities: ProductionCapability,
    state: ProductionResourceState = ProductionResourceState.AVAILABLE,
) -> ProductionResource:
    return ProductionResource(
        resource_id=resource_id,
        capabilities=frozenset(capabilities or (ProductionCapability.VIDEO_GENERATION,)),
        state=state,
    )


def test_resource_model_requires_stable_identity_and_capabilities() -> None:
    with pytest.raises(ValueError, match="resource_id cannot be blank"):
        ProductionResource(
            resource_id="   ",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )

    with pytest.raises(ValueError, match="capabilities must contain at least one"):
        ProductionResource(resource_id="RESOURCE-A", capabilities=frozenset())


def test_catalog_rejects_duplicate_resource_identities() -> None:
    with pytest.raises(ProductionResourceCatalogError, match="duplicate resource identities"):
        ProductionResourceCatalog((_resource("RESOURCE-A"), _resource("RESOURCE-A")))


def test_catalog_orders_resources_and_matches_exact_capability_deterministically() -> None:
    catalog = ProductionResourceCatalog(
        (
            _resource("RESOURCE-B"),
            _resource("RESOURCE-A"),
        )
    )

    assert tuple(resource.resource_id for resource in catalog.resources) == (
        "RESOURCE-A",
        "RESOURCE-B",
    )
    assert tuple(resource.resource_id for resource in catalog.candidates_for(_task())) == (
        "RESOURCE-A",
        "RESOURCE-B",
    )


def test_resource_with_capability_superset_is_eligible() -> None:
    task = _task(
        ProductionCapability.VIDEO_GENERATION,
        ProductionCapability.POST_PROCESSING,
    )
    resource = _resource(
        "RESOURCE-A",
        ProductionCapability.VIDEO_GENERATION,
        ProductionCapability.POST_PROCESSING,
        ProductionCapability.QUALITY_CONTROL,
    )
    catalog = ProductionResourceCatalog((resource,))

    assert catalog.candidates_for(task) == (resource,)
    assert catalog.has_candidate(task)


def test_missing_capabilities_are_reported_and_resource_is_not_eligible() -> None:
    task = _task(
        ProductionCapability.VIDEO_GENERATION,
        ProductionCapability.POST_PROCESSING,
    )
    catalog = ProductionResourceCatalog(
        (_resource("RESOURCE-A", ProductionCapability.VIDEO_GENERATION),)
    )

    match = catalog.evaluate(task)[0]

    assert not match.eligible
    assert match.available
    assert match.missing_capabilities == (ProductionCapability.POST_PROCESSING,)
    assert catalog.candidates_for(task) == ()


def test_unavailable_resource_is_not_candidate_even_when_capabilities_match() -> None:
    resource = _resource(
        "RESOURCE-A",
        ProductionCapability.VIDEO_GENERATION,
        state=ProductionResourceState.UNAVAILABLE,
    )
    catalog = ProductionResourceCatalog((resource,))

    match = catalog.evaluate(_task())[0]

    assert not match.eligible
    assert not match.available
    assert match.missing_capabilities == ()
    assert not catalog.has_candidate(_task())


def test_matching_does_not_mutate_production_task_lifecycle() -> None:
    task = _task(state=ProductionTaskState.PLANNED)
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"),))

    before = task
    candidates = catalog.candidates_for(task)

    assert candidates == (_resource("RESOURCE-A"),)
    assert task == before
    assert task.state is ProductionTaskState.PLANNED


def test_resource_metadata_and_labels_are_validated_without_provider_contracts() -> None:
    resource = ProductionResource(
        resource_id="  RESOURCE-A  ",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        labels=("local", "gpu"),
        metadata=(("location", "workstation"),),
    )

    assert resource.resource_id == "RESOURCE-A"

    with pytest.raises(ValueError, match="labels cannot contain duplicates"):
        replace(resource, labels=("gpu", "gpu"))

    with pytest.raises(ValueError, match="metadata cannot contain duplicate keys"):
        replace(resource, metadata=(("location", "one"), ("location", "two")))
