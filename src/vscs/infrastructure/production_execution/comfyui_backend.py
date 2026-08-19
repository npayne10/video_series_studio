"""Project-scoped live ComfyUI backend for the Phase 20.15 execution workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.generated_media import (
    GeneratedMediaIngestionService,
    GeneratedMediaPersistenceService,
)
from vscs.application.production_execution import (
    ProductionExecutionCandidate,
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionExecutionState,
)
from vscs.application.production_tasks import (
    ProductionQueue,
    ProductionQueueCompilerService,
    ProductionQueueRuntimeService,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionTask,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
)
from vscs.application.provider_execution import (
    DurableExecutionJobService,
    ProviderExecutionAdapterRegistry,
    ProviderExecutionHandle,
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
    RenderRequest,
    RenderSettings,
    RendererKind,
)
from vscs.application.rendering.workflows import (
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.domain.generated_media import GeneratedMediaKind
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    LocalGeneratedMediaFileStore,
)
from vscs.infrastructure.production import (
    JsonProductionScheduleRepository,
    JsonProductionTaskRepository,
)
from vscs.infrastructure.provider_execution import (
    ComfyUIProviderAdapterFactory,
    JsonDurableExecutionJobRepository,
    JsonProviderRegistrationRepository,
)
from vscs.infrastructure.rendering import (
    ComfyUIClient,
    ComfyUIWorkflowCompiler,
    ProductionPackageComfyUIAdapter,
    UrllibComfyUITransport,
)


WORKFLOW_ID = "video_production_engine_v7_1_4"
_PROVIDER_PREFIX = "LOCAL-COMFYUI"


@dataclass(slots=True)
class _ActiveExecution:
    candidate: ProductionExecutionCandidate
    queue: ProductionQueue
    lease_id: str
    handle: ProviderExecutionHandle
    service: QueueProviderExecutionService


class LocalComfyUIProductionExecutionBackend:
    """Run approved scheduled video work through the existing Phase 19/20 authorities."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.endpoint = endpoint.strip().rstrip("/")
        self.comfyui_output_directory = (
            Path(comfyui_output_directory).expanduser().resolve(strict=False)
            if comfyui_output_directory is not None
            else None
        )
        self.managed_media_directory = managed_media_directory.strip() or "Media Output"
        self.lease_duration_seconds = lease_duration_seconds
        self.tasks = JsonProductionTaskRepository(
            self.project_directory / "production" / "production_tasks"
        )
        self.schedules = JsonProductionScheduleRepository(
            self.project_directory / "production" / "production_schedules"
        )
        self.execution_jobs = DurableExecutionJobService(
            JsonDurableExecutionJobRepository(
                self.project_directory / ".vscs" / "provider_executions"
            )
        )
        self.media = GeneratedMediaPersistenceService(
            JsonGeneratedMediaRepository(self.project_directory / ".vscs" / "generated_media")
        )
        self._active: dict[str, _ActiveExecution] = {}
        self._latest: dict[str, ProductionExecutionResult] = {}

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        """Discover READY tasks only through current approved schedule compilation."""
        production_ids = tuple(
            sorted(
                {
                    task.production_id
                    for task in self.tasks.list_all()
                    if task.state is ProductionTaskState.READY
                }
            )
        )
        candidates: list[ProductionExecutionCandidate] = []
        for production_id in production_ids:
            try:
                queue = ProductionQueueCompilerService(self.schedules, self.tasks).compile(
                    production_id
                )
            except Exception:
                continue
            for entry in queue.entries:
                task = self.tasks.get(entry.task_id)
                if task is None or task.task_type is not ProductionTaskType.VIDEO_GENERATION:
                    continue
                candidates.append(self._candidate(task, entry.resource_id, entry.entry_id))
        return tuple(
            sorted(candidates, key=lambda item: (item.production_id, item.episode_id, item.task_id))
        )

    def start(
        self,
        task_id: str,
        *,
        production_package: Path,
    ) -> ProductionExecutionResult:
        if task_id in self._active:
            raise ProductionExecutionError(f"ProductionTask already has an active execution: {task_id}")
        task = self.tasks.get(task_id)
        if task is None:
            raise ProductionExecutionError(f"ProductionTask not found: {task_id}")
        if task.task_type is not ProductionTaskType.VIDEO_GENERATION:
            raise ProductionExecutionError(
                "Phase 20.15 live ComfyUI execution currently supports VIDEO_GENERATION tasks"
            )
        queue = ProductionQueueCompilerService(self.schedules, self.tasks).compile(task.production_id)
        entry = queue.entry_for_task(task.task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in the current approved queue: {task.task_id}"
            )
        candidate = self._candidate(task, entry.resource_id, entry.entry_id)
        source_root = self._require_comfyui_output_directory()
        service, worker_id = self._execution_service(task, entry.resource_id)
        request = self._render_request(task)
        submission = service.submit(
            queue,
            entry.entry_id,
            worker_id,
            request,
            str(Path(production_package).resolve(strict=False)),
            lease_duration_seconds=self.lease_duration_seconds,
        )
        if not submission.submitted or submission.handle is None or submission.lease is None:
            result = ProductionExecutionResult(
                candidate=candidate,
                state=ProductionExecutionState.FAILED,
                provider_id=submission.provider.provider_id,
                message=submission.error_message or "Provider submission failed",
                media_output_directory=self.managed_media_directory,
            )
            self._latest[task.task_id] = result
            return result
        self._active[task.task_id] = _ActiveExecution(
            candidate=candidate,
            queue=submission.queue,
            lease_id=submission.lease.lease_id,
            handle=submission.handle,
            service=service,
        )
        result = self._result(candidate, submission.handle, message=f"Provider submitted; source output: {source_root}")
        self._latest[task.task_id] = result
        return result

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        active = self._active.get(task_id)
        if active is None:
            latest = self._latest.get(task_id)
            if latest is not None:
                return latest
            task = self.tasks.get(task_id)
            if task is None:
                raise ProductionExecutionError(f"ProductionTask not found: {task_id}")
            jobs = self.execution_jobs.list_for_task(task_id)
            if jobs:
                job = jobs[-1]
                state = self._state(job.state)
                return ProductionExecutionResult(
                    candidate=self._candidate(task, job.resource_id, job.entry_id),
                    state=state,
                    provider_id=job.provider_id,
                    execution_id=job.execution_id,
                    provider_job_id=job.provider_job_id,
                    progress=job.progress,
                    generated_media_ids=tuple(
                        item.media_id for item in self.media.list_for_task(task_id)
                    ),
                    media_output_directory=self.managed_media_directory,
                    message="Restored durable execution summary; live recovery is Phase 20.16.",
                )
            raise ProductionExecutionError(f"No execution exists for ProductionTask: {task_id}")

        reconciled = active.service.reconcile(
            active.queue,
            active.candidate.queue_entry_id,
            active.lease_id,
            active.handle,
            lease_duration_seconds=self.lease_duration_seconds,
        )
        active.queue = reconciled.queue
        active.handle = reconciled.handle
        if reconciled.lease is not None:
            active.lease_id = reconciled.lease.lease_id

        if reconciled.handle.state is ProviderExecutionState.COMPLETED:
            if reconciled.execution_job is None:
                raise ProductionExecutionError(
                    "Completed provider execution has no durable execution record for ingestion"
                )
            task = self.tasks.get(task_id)
            if task is None:
                raise ProductionExecutionError(f"ProductionTask not found: {task_id}")
            ingestion = GeneratedMediaIngestionService(
                self.media,
                LocalGeneratedMediaFileStore(
                    source_root=self._require_comfyui_output_directory(),
                    managed_root=self.project_directory,
                    managed_relative_root=self.managed_media_directory,
                ),
            )
            ingested = ingestion.ingest_execution_outputs(
                reconciled.execution_job,
                task,
                reconciled.outputs,
            )
            result = self._result(
                active.candidate,
                reconciled.handle,
                generated_media_ids=tuple(item.media.media_id for item in ingested),
                message="Provider completed; outputs ingested as authoritative Generated Media.",
            )
            self._active.pop(task_id, None)
            self._latest[task_id] = result
            return result

        if reconciled.handle.state in {
            ProviderExecutionState.FAILED,
            ProviderExecutionState.CANCELLED,
        }:
            result = self._result(
                active.candidate,
                reconciled.handle,
                message=reconciled.handle.failure_reason or reconciled.handle.state.value,
            )
            self._active.pop(task_id, None)
            self._latest[task_id] = result
            return result

        result = self._result(active.candidate, reconciled.handle)
        self._latest[task_id] = result
        return result

    def _execution_service(
        self,
        task: ProductionTask,
        resource_id: str,
    ) -> tuple[QueueProviderExecutionService, str]:
        worker_id = f"WORKER-{resource_id}"
        workers = ProductionWorkerRegistry()
        workers.register(
            ProductionWorker(
                worker_id=worker_id,
                resource_id=resource_id,
                capabilities=frozenset(task.capabilities),
            )
        )
        runtime = ProductionQueueRuntimeService(self.tasks, workers)
        resource = ProductionResource(
            resource_id=resource_id,
            capabilities=frozenset(task.capabilities),
        )
        resources = ProductionResourceCatalog((resource,))

        provider_id = f"{_PROVIDER_PREFIX}-{_safe_id(resource_id)}"
        providers = ProviderRegistryService(
            JsonProviderRegistrationRepository(
                self.project_directory / ".vscs" / "provider_registrations"
            )
        )
        registration = ProviderRegistration(
            provider_id=provider_id,
            adapter_type="comfyui",
            resource_id=resource_id,
            capabilities=frozenset(task.capabilities),
            supported_task_types=frozenset({ProductionTaskType.VIDEO_GENERATION}),
            supported_media_kinds=frozenset({GeneratedMediaKind.VIDEO}),
            endpoint=self.endpoint,
            health=self._provider_health(),
        )
        if providers.get(provider_id) is None:
            providers.register(registration)
        else:
            providers.save(registration)

        foundation = self._workflow_foundation()
        adapter = ComfyUIProviderAdapterFactory().build(registration, foundation)
        adapters = ProviderExecutionAdapterRegistry()
        adapters.register(adapter)
        return (
            QueueProviderExecutionService(
                runtime=runtime,
                tasks=self.tasks,
                resources=resources,
                providers=providers,
                adapters=adapters,
                execution_jobs=self.execution_jobs,
            ),
            worker_id,
        )

    def _provider_health(self) -> ProviderHealthState:
        if not self.endpoint:
            return ProviderHealthState.UNHEALTHY
        transport = UrllibComfyUITransport(self.endpoint, timeout_seconds=10.0)
        report = ComfyUIClient(transport, self.endpoint).health()
        return ProviderHealthState.HEALTHY if report.healthy else ProviderHealthState.UNHEALTHY

    def _workflow_foundation(self) -> ProductionPackageComfyUIAdapter:
        repository_root = Path(__file__).resolve().parents[4]
        manifest_path = (
            repository_root
            / "resources"
            / "workflows"
            / "manifests"
            / "video_production_engine_v7_1_4.json"
        )
        workflow_root = repository_root / "resources" / "workflows"
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        registry = WorkflowRegistry()
        registry.register(WorkflowManifest.from_dict(raw))
        return ProductionPackageComfyUIAdapter(
            registry,
            WorkflowCompatibilityValidator(),
            ComfyUIWorkflowCompiler(workflow_root),
        )

    @staticmethod
    def _render_request(task: ProductionTask) -> RenderRequest:
        scene = task.scene_id or "SCENE-NOT-SPECIFIED"
        shot = task.shot_id or task.task_id
        return RenderRequest(
            request_id=f"REQ-{task.task_id}",
            production_id=task.production_id,
            container_id=task.episode_id,
            scene_id=scene,
            shot_id=shot,
            clip_id=shot,
            renderer=RendererKind.COMFYUI,
            workflow_id=WORKFLOW_ID,
            quality_level=QualityLevel.PRODUCTION,
            prompt_package=PromptPackageReference(task.authority.authority_id),
            assets=AssetPackageReference(),
            continuity=ContinuityPackageReference(),
            render=RenderSettings(1280, 720, 24, 145),
            output=OutputSettings("vscs-production", task.task_id),
        )

    def _require_comfyui_output_directory(self) -> Path:
        if self.comfyui_output_directory is None:
            raise ProductionExecutionError(
                "Configure the ComfyUI output folder in Settings before starting production"
            )
        if not self.comfyui_output_directory.is_dir():
            raise ProductionExecutionError(
                f"Configured ComfyUI output folder does not exist: {self.comfyui_output_directory}"
            )
        return self.comfyui_output_directory

    def _result(
        self,
        candidate: ProductionExecutionCandidate,
        handle: ProviderExecutionHandle,
        *,
        generated_media_ids: tuple[str, ...] = (),
        message: str = "",
    ) -> ProductionExecutionResult:
        return ProductionExecutionResult(
            candidate=candidate,
            state=self._state(handle.state),
            provider_id=handle.provider_id,
            execution_id=handle.execution_id,
            provider_job_id=handle.provider_job_id,
            progress=handle.progress,
            generated_media_ids=generated_media_ids,
            media_output_directory=self.managed_media_directory,
            message=message,
        )

    @staticmethod
    def _state(state: ProviderExecutionState) -> ProductionExecutionState:
        mapping = {
            ProviderExecutionState.QUEUED: ProductionExecutionState.SUBMITTED,
            ProviderExecutionState.PREPARING: ProductionExecutionState.PREPARING,
            ProviderExecutionState.RUNNING: ProductionExecutionState.RUNNING,
            ProviderExecutionState.RETRYING: ProductionExecutionState.RUNNING,
            ProviderExecutionState.COMPLETED: ProductionExecutionState.COMPLETED,
            ProviderExecutionState.FAILED: ProductionExecutionState.FAILED,
            ProviderExecutionState.CANCELLED: ProductionExecutionState.CANCELLED,
        }
        return mapping[state]

    @staticmethod
    def _candidate(
        task: ProductionTask,
        resource_id: str,
        entry_id: str,
    ) -> ProductionExecutionCandidate:
        scope = task.shot_id or task.scene_id or task.episode_id
        label = f"{task.task_type.value.replace('_', ' ').title()} — {scope}"
        return ProductionExecutionCandidate(
            production_id=task.production_id,
            task_id=task.task_id,
            task_type=task.task_type,
            task_state=task.state,
            episode_id=task.episode_id,
            scene_id=task.scene_id,
            shot_id=task.shot_id,
            resource_id=resource_id,
            queue_entry_id=entry_id,
            label=label,
        )


def _safe_id(value: str) -> str:
    normalized = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value.strip().upper()
    )
    return normalized or "RESOURCE"
