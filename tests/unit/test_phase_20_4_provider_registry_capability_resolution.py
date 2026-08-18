"""Focused tests for Phase 20.4 provider registry and capability resolution."""

from dataclasses import replace

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionResourceState,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    ProviderCapabilityResolver,
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistrationRepositoryError,
    ProviderRegistrationState,
    ProviderRegistryService,
)
from vscs.domain.generated_media import GeneratedMediaKind
from vscs.infrastructure.provider_execution import JsonProviderRegistrationRepository


def _task(
    *,
    task_type: ProductionTaskType = ProductionTaskType.VIDEO_GENERATION,
    capabilities: tuple[ProductionCapability, ...] = (ProductionCapability.VIDEO_GENERATION,),
) -> ProductionTask:
    return ProductionTask(
        task_id="PT-001",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=task_type,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-001",
            revision=1,
            fingerprint="authority-fingerprint",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=capabilities,
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _resource(
    *,
    resource_id: str = "LOCAL-GPU-01",
    capabilities: frozenset[ProductionCapability] = frozenset(
        {ProductionCapability.VIDEO_GENERATION}
    ),
    state: ProductionResourceState = ProductionResourceState.AVAILABLE,
) -> ProductionResource:
    return ProductionResource(
        resource_id=resource_id,
        capabilities=capabilities,
        state=state,
    )


def _provider(
    provider_id: str = "LOCAL-COMFYUI-01",
    *,
    resource_id: str = "LOCAL-GPU-01",
    capabilities: frozenset[ProductionCapability] = frozenset(
        {ProductionCapability.VIDEO_GENERATION}
    ),
    state: ProviderRegistrationState = ProviderRegistrationState.ENABLED,
    health: ProviderHealthState = ProviderHealthState.UNKNOWN,
) -> ProviderRegistration:
    return ProviderRegistration(
        provider_id=provider_id,
        adapter_type="comfyui",
        resource_id=resource_id,
        capabilities=capabilities,
        supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
        supported_media_kinds=frozenset({GeneratedMediaKind.VIDEO}),
        endpoint="http://127.0.0.1:8188",
        secret_reference="secret://providers/local-comfyui",
        state=state,
        health=health,
        configuration=(("workflow_root", "workflows/comfyui"),),
        metadata=(("location", "local"),),
    )


def test_provider_registration_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="secret_reference"):
        replace(_provider(), configuration=(("api_key", "plaintext-secret"),))


def test_provider_capability_resolution_accepts_bound_compatible_provider() -> None:
    result = ProviderCapabilityResolver().resolve(_task(), _resource(), _provider())

    assert result.eligible
    assert result.reasons == ()
    assert result.missing_resource_capabilities == ()
    assert result.missing_provider_capabilities == ()


def test_provider_resolution_reports_disabled_unhealthy_and_mismatched_provider() -> None:
    provider = _provider(
        resource_id="OTHER-GPU",
        state=ProviderRegistrationState.DISABLED,
        health=ProviderHealthState.UNHEALTHY,
        capabilities=frozenset({ProductionCapability.IMAGE_GENERATION}),
    )
    result = ProviderCapabilityResolver().resolve(_task(), _resource(), provider)

    assert not result.eligible
    assert result.reasons == (
        "provider-resource-mismatch",
        "provider-disabled",
        "provider-unhealthy",
        "provider-capability-mismatch",
    )
    assert result.missing_provider_capabilities == (ProductionCapability.VIDEO_GENERATION,)


def test_provider_resolution_requires_available_capable_resource() -> None:
    resource = _resource(
        capabilities=frozenset({ProductionCapability.IMAGE_GENERATION}),
        state=ProductionResourceState.UNAVAILABLE,
    )
    result = ProviderCapabilityResolver().resolve(_task(), resource, _provider())

    assert not result.eligible
    assert result.reasons == (
        "resource-unavailable",
        "resource-capability-mismatch",
    )


def test_registry_service_returns_eligible_providers_deterministically(tmp_path) -> None:
    service = ProviderRegistryService(
        JsonProviderRegistrationRepository(tmp_path / "providers")
    )
    service.register(_provider("PROVIDER-B"))
    service.register(_provider("PROVIDER-A"))
    service.register(
        _provider(
            "PROVIDER-C",
            state=ProviderRegistrationState.DISABLED,
        )
    )

    assert [item.provider_id for item in service.eligible_providers(_task(), _resource())] == [
        "PROVIDER-A",
        "PROVIDER-B",
    ]


def test_registry_rejects_duplicate_stable_identity(tmp_path) -> None:
    service = ProviderRegistryService(
        JsonProviderRegistrationRepository(tmp_path / "providers")
    )
    provider = _provider()
    service.register(provider)

    with pytest.raises(ProviderRegistrationRepositoryError, match="already exists"):
        service.register(provider)
