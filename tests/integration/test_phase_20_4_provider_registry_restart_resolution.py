"""Restart integration acceptance for Phase 20.4 provider registry resolution."""

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistryService,
)
from vscs.infrastructure.provider_execution import JsonProviderRegistrationRepository


def test_phase_20_4_provider_registration_survives_restart_and_resolves(tmp_path) -> None:
    root = tmp_path / "project" / "providers"
    service = ProviderRegistryService(JsonProviderRegistrationRepository(root))
    provider = ProviderRegistration(
        provider_id="LOCAL-COMFYUI-01",
        adapter_type="comfyui",
        resource_id="LOCAL-GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
        supported_media_kinds=frozenset({"video"}),
        endpoint="http://127.0.0.1:8188",
        secret_reference="secret://providers/local-comfyui",
        health=ProviderHealthState.HEALTHY,
        configuration=(("workflow_root", "workflows/comfyui"),),
    )
    service.register(provider)

    restarted = ProviderRegistryService(JsonProviderRegistrationRepository(root))
    restored = restarted.get("LOCAL-COMFYUI-01")
    assert restored == provider

    task = ProductionTask(
        task_id="PT-001",
        production_id="PROD-001",
        episode_id="EP-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-001",
            revision=1,
            fingerprint="fingerprint",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )
    resource = ProductionResource(
        resource_id="LOCAL-GPU-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
    )

    eligible = restarted.eligible_providers(task, resource)
    assert eligible == (provider,)
