from pathlib import Path

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import ProviderHealthState
from vscs.infrastructure.production_execution import LocalComfyUIProductionExecutionBackend


def _task(task_id: str) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="XORIX",
        episode_id="EP-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{task_id}",
            revision=1,
            fingerprint=f"fingerprint-{task_id}",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def test_execution_services_share_worker_and_lease_authority(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "project"
    source = tmp_path / "comfyui-output"
    project.mkdir()
    source.mkdir()
    backend = LocalComfyUIProductionExecutionBackend(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=source,
    )
    monkeypatch.setattr(
        backend,
        "_provider_health",
        lambda: ProviderHealthState.HEALTHY,
    )

    first, first_worker = backend._execution_service(_task("PT-001"), "GPU-01")
    second, second_worker = backend._execution_service(_task("PT-002"), "GPU-01")

    assert first_worker == second_worker == "WORKER-GPU-01"
    assert first.runtime.workers is second.runtime.workers
    assert first.runtime.leases is second.runtime.leases
    assert first.runtime.leases is backend._leases
    worker = backend._workers.require("WORKER-GPU-01")
    assert worker.capabilities == frozenset({ProductionCapability.VIDEO_GENERATION})
