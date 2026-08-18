"""Run the explicit Phase 20.6 queue-authorised live ComfyUI acceptance test.

This script is intentionally outside normal VSCS bootstrap. It constructs one ephemeral
ProductionTask/ProductionQueue execution and submits it through the Phase 19 runtime and
Phase 20 provider contracts. It does not create GeneratedMedia authority.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from vscs.application.generated_media import GeneratedMediaKind
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
)
from vscs.application.provider_execution import (
    ProviderExecutionAdapterRegistry,
    ProviderExecutionState,
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistryService,
    QueueProviderExecutionService,
)
from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderRequest,
    RenderSettings,
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.infrastructure.provider_execution import (
    ComfyUIProviderAdapterFactory,
    JsonProviderRegistrationRepository,
)
from vscs.infrastructure.rendering import (
    ComfyUIClient,
    ComfyUIWorkflowCompiler,
    ProductionPackageComfyUIAdapter,
    UrllibComfyUITransport,
)

DEFAULT_ENDPOINT = "http://127.0.0.1:8188"
DEFAULT_PRODUCTION_PACKAGE = Path(r"D:\VSCS TSR2\Queues\preview_production_queue.json")
WORKFLOW_ROOT = Path("resources/workflows")
MANIFEST_PATH = WORKFLOW_ROOT / "manifests/video_production_engine_v7_1_4.json"
WORKFLOW_ID = "video_production_engine_v7_1_4"
PROVIDER_ID = "LOCAL-COMFYUI-01"
RESOURCE_ID = "LOCAL-GPU-01"
WORKER_ID = "WORKER-01"
TASK_ID = "PT-20-6-LIVE-001"
QUEUE_ID = "PQ-20-6-LIVE-001"
ENTRY_ID = "PQE-PT-20-6-LIVE-001"


class _TaskRepository:
    """Ephemeral repository used only by this explicit acceptance harness."""

    def __init__(self, task: ProductionTask) -> None:
        self.task = task

    def get(self, task_id: str) -> ProductionTask | None:
        return self.task if task_id == self.task.task_id else None

    def save(self, task: ProductionTask) -> ProductionTask:
        self.task = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return (self.task,) if production_id == self.task.production_id else ()


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--production-package",
        type=Path,
        default=DEFAULT_PRODUCTION_PACKAGE,
        help="JSON file injected into XorixProductionPackageLoaderV714.",
    )
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--lease-seconds", type=float, default=600.0)
    parser.add_argument("--timeout-seconds", type=float, default=7200.0)
    return parser.parse_args()


def _require_input_file(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_file():
        raise RuntimeError(f"Production package does not exist: {resolved}")
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Production package is not readable JSON: {resolved}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RuntimeError("Production package JSON root must be an object")
    return resolved


def _workflow_foundation() -> ProductionPackageComfyUIAdapter:
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    registry = WorkflowRegistry()
    registry.register(WorkflowManifest.from_dict(raw))
    return ProductionPackageComfyUIAdapter(
        registry,
        WorkflowCompatibilityValidator(),
        ComfyUIWorkflowCompiler(WORKFLOW_ROOT),
    )


def _task() -> ProductionTask:
    return ProductionTask(
        task_id=TASK_ID,
        production_id="PHASE-20-6-LIVE",
        episode_id="EP-LIVE-001",
        scene_id="SCN-LIVE-001",
        shot_id="SHT-LIVE-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-6-LIVE",
            revision=1,
            fingerprint="phase-20-6-live-acceptance",
            approved=True,
            approved_by="phase-20-6-live-acceptance",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _queue() -> ProductionQueue:
    return ProductionQueue(
        queue_id=QUEUE_ID,
        production_id="PHASE-20-6-LIVE",
        schedule_id="SCHED-20-6-LIVE",
        schedule_revision=1,
        schedule_fingerprint="phase-20-6-live-schedule",
        entries=(
            ProductionQueueEntry(
                entry_id=ENTRY_ID,
                task_id=TASK_ID,
                resource_id=RESOURCE_ID,
                task_type=ProductionTaskType.VIDEO_GENERATION,
                state=ProductionQueueState.READY,
                priority=ProductionTaskPriority.NORMAL,
            ),
        ),
    )


def _render_request() -> RenderRequest:
    return RenderRequest(
        request_id="REQ-20-6-LIVE-001",
        production_id="PHASE-20-6-LIVE",
        container_id="EP-LIVE-001",
        scene_id="SCN-LIVE-001",
        shot_id="SHT-LIVE-001",
        clip_id="CLP-LIVE-001",
        renderer=RendererKind.COMFYUI,
        workflow_id=WORKFLOW_ID,
        quality_level=QualityLevel.PRODUCTION,
        prompt_package=PromptPackageReference("PROMPT-20-6-LIVE"),
        assets=AssetPackageReference(),
        continuity=ContinuityPackageReference(),
        render=RenderSettings(1280, 720, 24, 145),
        output=OutputSettings("renders/phase-20-6-live", "phase-20-6-live-001"),
    )


def _print_header(endpoint: str, package: Path) -> None:
    print("PHASE 20.6 LIVE ACCEPTANCE")
    print()
    print(f"ComfyUI endpoint          : {endpoint}")
    print(f"Provider                  : {PROVIDER_ID}")
    print(f"Resource                  : {RESOURCE_ID}")
    print(f"Worker                    : {WORKER_ID}")
    print(f"ProductionTask            : {TASK_ID}")
    print(f"Queue Entry               : {ENTRY_ID}")
    print(f"Production package        : {package}")
    print()


def main() -> int:
    args = _arguments()
    if args.poll_seconds <= 0 or args.lease_seconds <= 0 or args.timeout_seconds <= 0:
        raise RuntimeError("poll, lease and timeout values must be positive")

    endpoint = str(args.endpoint).strip().rstrip("/")
    package = _require_input_file(args.production_package)
    _print_header(endpoint, package)

    transport = UrllibComfyUITransport(endpoint, timeout_seconds=10.0)
    health = ComfyUIClient(transport, endpoint).health()
    print(f"ComfyUI health            : {'HEALTHY' if health.healthy else 'UNHEALTHY'}")
    if not health.healthy:
        print("PHASE 20.6 LIVE ACCEPTANCE: FAIL")
        return 2

    task = _task()
    tasks = _TaskRepository(task)
    workers = ProductionWorkerRegistry()
    workers.register(
        ProductionWorker(
            worker_id=WORKER_ID,
            resource_id=RESOURCE_ID,
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    runtime = ProductionQueueRuntimeService(tasks, workers)
    resources = ProductionResourceCatalog(
        (
            ProductionResource(
                resource_id=RESOURCE_ID,
                capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
            ),
        )
    )

    with tempfile.TemporaryDirectory(prefix="vscs-phase-20-6-") as temp_root:
        providers = ProviderRegistryService(
            JsonProviderRegistrationRepository(Path(temp_root) / "providers")
        )
        registration = providers.register(
            ProviderRegistration(
                provider_id=PROVIDER_ID,
                adapter_type="comfyui",
                resource_id=RESOURCE_ID,
                capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
                supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
                supported_media_kinds=frozenset({GeneratedMediaKind.VIDEO}),
                endpoint=endpoint,
                health=ProviderHealthState.HEALTHY,
            )
        )
        foundation = _workflow_foundation()
        adapter = ComfyUIProviderAdapterFactory().build(
            registration,
            foundation,
            transport=transport,
        )
        adapters = ProviderExecutionAdapterRegistry()
        adapters.register(adapter)
        execution = QueueProviderExecutionService(
            runtime=runtime,
            tasks=tasks,
            resources=resources,
            providers=providers,
            adapters=adapters,
        )

        print("Claiming queue and submitting to ComfyUI...")
        submitted = execution.submit(
            _queue(),
            ENTRY_ID,
            WORKER_ID,
            _render_request(),
            str(package),
            lease_duration_seconds=args.lease_seconds,
            provider_id=PROVIDER_ID,
        )
        entry = submitted.queue.entry(ENTRY_ID)
        print(f"Queue state               : {entry.state.value if entry else 'missing'}")
        if not submitted.submitted or submitted.handle is None or submitted.lease is None:
            print(f"Submission error          : {submitted.error_message or 'unknown'}")
            print("PHASE 20.6 LIVE ACCEPTANCE: FAIL")
            return 3

        queue = submitted.queue
        handle = submitted.handle
        lease = submitted.lease
        print(f"VSCS execution ID         : {handle.execution_id}")
        print(f"ComfyUI prompt ID         : {handle.provider_job_id}")
        print(f"Provider state            : {handle.state.value}")
        print(f"Lease                     : {lease.lease_id}")
        print()

        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            time.sleep(args.poll_seconds)
            reconciled = execution.reconcile(
                queue,
                ENTRY_ID,
                lease.lease_id,
                handle,
                lease_duration_seconds=args.lease_seconds,
            )
            queue = reconciled.queue
            handle = reconciled.handle
            print(f"Provider state            : {handle.state.value}")
            if reconciled.terminal:
                entry = queue.entry(ENTRY_ID)
                print(f"Queue state               : {entry.state.value if entry else 'missing'}")
                if reconciled.outputs:
                    print("Outputs:")
                    for output in reconciled.outputs:
                        print(f"  {output.relative_path}")
                if handle.state is ProviderExecutionState.COMPLETED:
                    print("Lease active              : no")
                    print("PHASE 20.6 LIVE ACCEPTANCE: PASS")
                    return 0
                print(f"Failure reason            : {handle.failure_reason or 'provider did not complete'}")
                print("PHASE 20.6 LIVE ACCEPTANCE: FAIL")
                return 4
            if reconciled.lease is None:
                raise RuntimeError("Non-terminal provider execution lost its active lease")
            lease = reconciled.lease
            print("Lease renewed             : yes")
            print()

        print("Acceptance timeout reached before provider completion")
        print("PHASE 20.6 LIVE ACCEPTANCE: FAIL")
        return 5


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAcceptance interrupted by operator", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"PHASE 20.6 LIVE ACCEPTANCE ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
