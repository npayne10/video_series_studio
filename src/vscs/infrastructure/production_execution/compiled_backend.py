"""Production-package-aware ComfyUI execution with Phase 20.16 restart recovery."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vscs.application.generated_media import GeneratedMediaIngestionService
from vscs.application.production_execution import (
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionPackageStatus,
    ProductionTelemetrySnapshot,
    ProductionTelemetryState,
)
from vscs.application.production_execution.recovery import (
    ProductionRestartRecoveryError,
    RestartRecoveryLeaseManager,
    RestartRecoveryQueueAdopter,
)
from vscs.application.production_tasks import (
    ProductionQueue,
    ProductionQueueAttempt,
    ProductionQueueCompilerService,
    ProductionTask,
)
from vscs.application.provider_execution import (
    DurableExecutionJob,
    ProviderExecutionHandle,
    ProviderExecutionHandleRestorer,
    ProviderExecutionState,
)
from vscs.infrastructure.generated_media import LocalGeneratedMediaFileStore

from .comfyui_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase2015ComfyUIBackend,
)
from .comfyui_backend import _ActiveExecution
from .live_telemetry import ComfyUIProductionTelemetryReader
from .package_compilation import (
    ComfyUIV714InputAssurance,
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)
from .restart_recovery import (
    ComfyUIRecoveryPresence,
    ComfyUIRestartRecoveryProbe,
)


class LocalComfyUIProductionExecutionBackend(_Phase2015ComfyUIBackend):
    """Compile, execute, monitor and safely recover governed ComfyUI production work."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            project_directory,
            endpoint=endpoint,
            comfyui_output_directory=comfyui_output_directory,
            managed_media_directory=managed_media_directory,
            lease_duration_seconds=lease_duration_seconds,
        )
        # Normal starts still use ProductionLeaseManager.acquire(). Restart adoption uses a
        # fresh PRLEASE identity so the old durable lease is never impersonated after restart.
        self._leases = RestartRecoveryLeaseManager()
        self.package_compilation = LocalProductionPackageCompilationService(self.project_directory)
        self.input_assurance = ComfyUIV714InputAssurance()
        self._recovered_tasks: set[str] = set()

    def has_execution(self, task_id: str) -> bool:
        """Return whether an execution currently blocks a fresh governed attempt."""
        task = self._require_task(task_id)
        if task.task_id in self._active:
            return True
        jobs = self.execution_jobs.list_for_task(task.task_id)
        if not jobs:
            return False
        if any(not job.terminal for job in jobs):
            return True
        latest = max(jobs, key=lambda job: (job.attempt_number, job.updated_at, job.execution_id))
        if latest.state is ProviderExecutionState.COMPLETED and self.media.list_for_task(
            task.task_id
        ):
            return True
        return latest.attempt_number >= task.attempt_policy.maximum_attempts

    def telemetry(self, task_id: str) -> ProductionTelemetrySnapshot:
        """Return live telemetry after recovery or a durable summary before recovery."""
        task = self._require_task(task_id)
        reader = ComfyUIProductionTelemetryReader(self.endpoint)
        active = self._active.get(task.task_id)
        if active is not None:
            return reader.observe_live(
                active.handle,
                task_id=task.task_id,
                resource_id=active.candidate.resource_id,
                queue_entry_id=active.candidate.queue_entry_id,
            )
        jobs = self.execution_jobs.list_for_task(task.task_id)
        if jobs:
            latest = jobs[-1]
            snapshot = reader.observe_durable(latest)
            if latest.state is ProviderExecutionState.COMPLETED and not self.media.list_for_task(
                task.task_id
            ):
                return replace(
                    snapshot,
                    state=ProductionTelemetryState.FAILED,
                    progress=None,
                    stage="Provider completed without recoverable production output",
                    message=(
                        "Provider execution reached COMPLETED but no Generated Media or recoverable "
                        "output exists; VSCS treats the production attempt as failed and retryable."
                    ),
                )
            return snapshot
        raise ProductionExecutionError(f"No execution exists for ProductionTask: {task.task_id}")

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        task = self._require_task(task_id)
        return self.package_compilation.status(task, profile=profile)

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        task = self._require_task(task_id)
        workflow_path = (
            Path(__file__).resolve().parents[4]
            / "resources"
            / "workflows"
            / "workflows"
            / "video_production_engine_v7_1_4_api.json"
        )
        assurance = self.input_assurance.inspect(workflow_path)
        if not assurance.passed:
            raise ProductionExecutionError(
                "ComfyUI production workflow input assurance failed: " + "; ".join(assurance.issues)
            )
        try:
            return self.package_compilation.compile(task, profile=profile)
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def start(
        self,
        task_id: str,
        *,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        """Start a first or governed retry attempt from current approved queue authority."""
        task = self._require_task(task_id)
        if self.has_execution(task.task_id):
            raise ProductionExecutionError(
                "ProductionTask has an active, successful, or exhausted execution history. "
                "Inspect execution status before creating another attempt."
            )
        try:
            if production_package is None:
                package = self.package_compilation.require_current(task).path
                assert package is not None
            else:
                package = Path(production_package).expanduser().resolve(strict=False)
                self.package_compilation.validate_file(task, package)
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

        queue = ProductionQueueCompilerService(self.schedules, self.tasks).compile(
            task.production_id
        )
        entry = queue.entry_for_task(task.task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in the current approved queue: {task.task_id}"
            )
        history = self._retry_attempt_history(
            task,
            self.execution_jobs.list_for_queue_entry(queue.queue_id, entry.entry_id),
        )
        if history:
            queue = self._queue_with_attempt_history(queue, task.task_id, history)
            entry = queue.entry_for_task(task.task_id)
            assert entry is not None

        candidate = self._candidate(task, entry.resource_id, entry.entry_id)
        source_root = self._require_comfyui_output_directory()
        service, worker_id = self._execution_service(task, entry.resource_id)
        submission = service.submit(
            queue,
            entry.entry_id,
            worker_id,
            self._render_request(task),
            str(package.resolve(strict=False)),
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
        result = self._result(
            candidate,
            submission.handle,
            message=f"Provider submitted; source output: {source_root}",
        )
        self._latest[task.task_id] = result
        return result

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        """Reconcile current-session work or recover a detached durable execution."""
        task = self._require_task(task_id)
        if task.task_id in self._recovered_tasks:
            return self._reconcile_recovered(task)
        if task.task_id in self._active:
            return super().reconcile(task.task_id)
        if self.execution_jobs.list_for_task(task.task_id):
            return self.recover(task.task_id)
        return super().reconcile(task.task_id)

    def recover(self, task_id: str) -> ProductionExecutionResult:
        """Reattach verified provider work without resubmission or stale-lease reuse."""
        task = self._require_task(task_id)
        active = self._active.get(task.task_id)
        if active is not None:
            return self._result(
                active.candidate,
                active.handle,
                message="Execution is already attached to the current VSCS session.",
            )
        jobs = self.execution_jobs.list_for_task(task.task_id)
        if not jobs:
            raise ProductionExecutionError(
                f"No durable execution exists for ProductionTask: {task_id}"
            )
        job = jobs[-1]
        media_ids = tuple(item.media_id for item in self.media.list_for_task(task.task_id))
        if job.state in {ProviderExecutionState.FAILED, ProviderExecutionState.CANCELLED}:
            return self._durable_result(
                task,
                job,
                message=(
                    "Durable provider execution is terminal and unsuccessful. "
                    "A governed retry is allowed if attempt policy permits."
                ),
            )
        if job.state is ProviderExecutionState.COMPLETED and media_ids:
            return self._durable_result(
                task,
                job,
                message="Completed durable execution is already reconciled to Generated Media.",
            )
        self._validate_recovery_authority(task, job)
        if job.provider_job_id is None:
            failed = self._fail_nonterminal_job(
                job,
                "Durable execution has no provider job identity and produced no recoverable output.",
            )
            return self._durable_result(
                task,
                failed,
                message="Execution marked FAILED because no provider job or production output exists.",
            )

        probe = ComfyUIRestartRecoveryProbe(self.endpoint)
        observation = probe.observe(job.provider_job_id)
        if observation.presence is ComfyUIRecoveryPresence.UNREACHABLE:
            return self._durable_result(task, job, message=observation.message)
        if observation.presence is ComfyUIRecoveryPresence.NOT_FOUND:
            if job.terminal:
                return self._failed_production_result(
                    task,
                    job,
                    observation.message
                    + " No production output exists; the attempt is failed and may be rerun.",
                )
            failed = self._fail_nonterminal_job(
                job,
                observation.message + " No production output exists.",
            )
            return self._durable_result(
                task,
                failed,
                message=(
                    "Provider no longer accounts for the durable prompt and no production output "
                    "exists. Execution marked FAILED; governed retry is now allowed."
                ),
            )
        if observation.presence is ComfyUIRecoveryPresence.FAILED:
            if job.terminal:
                return self._failed_production_result(
                    task,
                    job,
                    observation.failure_reason or observation.message,
                )
            failed = self._fail_nonterminal_job(
                job,
                observation.failure_reason or observation.message,
            )
            return self._durable_result(
                task,
                failed,
                message=failed.failure_reason or "Recovered provider execution failed.",
            )
        if observation.presence is ComfyUIRecoveryPresence.COMPLETED:
            issue = self._completed_output_issue(probe, job.provider_job_id)
            if issue is not None:
                if job.terminal:
                    return self._failed_production_result(task, job, issue)
                failed = self._fail_nonterminal_job(job, issue)
                return self._durable_result(
                    task,
                    failed,
                    message=(
                        issue
                        + " Execution marked FAILED because provider completion without an output "
                        "is not a successful VSCS production run."
                    ),
                )

        queue = ProductionQueueCompilerService(self.schedules, self.tasks).compile(
            task.production_id
        )
        entry = queue.entry_for_task(task.task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in current approved queue: {task.task_id}"
            )
        self._validate_queue_against_job(queue.queue_id, entry.entry_id, entry.resource_id, job)
        service, worker_id = self._execution_service(task, entry.resource_id)
        if worker_id != job.worker_id:
            raise ProductionExecutionError(
                "Durable execution worker identity does not match the current scheduled resource."
            )
        adapter = service.adapters.require(job.provider_id)
        if not isinstance(adapter, ProviderExecutionHandleRestorer):
            raise ProductionExecutionError(
                f"Provider adapter cannot restore durable execution handles: {job.provider_id}"
            )
        try:
            handle = adapter.restore_handle(job)
            refreshed = adapter.monitor(handle)
            if refreshed.state is ProviderExecutionState.COMPLETED:
                issue = self._completed_output_issue(probe, refreshed.provider_job_id)
                if issue is not None:
                    if job.terminal:
                        return self._failed_production_result(task, job, issue)
                    failed = self._fail_nonterminal_job(job, issue)
                    return self._durable_result(task, failed, message=issue)
            if refreshed.state is ProviderExecutionState.FAILED:
                failed = self.execution_jobs.observe(job.execution_id, refreshed)
                return self._durable_result(
                    task,
                    failed,
                    message=failed.failure_reason or "Recovered provider execution failed.",
                )
            if refreshed.state is ProviderExecutionState.CANCELLED:
                cancelled = self.execution_jobs.observe(job.execution_id, refreshed)
                return self._durable_result(
                    task,
                    cancelled,
                    message="Recovered provider execution is cancelled; governed retry may proceed.",
                )
            observed_job = self.execution_jobs.observe(job.execution_id, refreshed)
            attempts = self._recovery_attempts(
                self.execution_jobs.list_for_queue_entry(job.queue_id, job.entry_id),
                observed_job,
            )
            worker = self._workers.require(worker_id)
            # The recovery lease must live in the exact runtime that will heartbeat and finish it.
            adoption = RestartRecoveryQueueAdopter(service.runtime.leases).adopt(
                queue,
                task,
                worker,
                attempts,
                lease_duration_seconds=self.lease_duration_seconds,
            )
        except ProductionRestartRecoveryError as exc:
            raise ProductionExecutionError(str(exc)) from exc
        except Exception as exc:
            raise ProductionExecutionError(
                f"Unable to restore durable provider execution safely: {exc}"
            ) from exc

        candidate = self._candidate(task, entry.resource_id, entry.entry_id)
        self._active[task.task_id] = _ActiveExecution(
            candidate=candidate,
            queue=adoption.queue,
            lease_id=adoption.lease.lease_id,
            handle=refreshed,
            service=service,
        )
        self._recovered_tasks.add(task.task_id)
        if refreshed.state is ProviderExecutionState.COMPLETED:
            return self._reconcile_recovered(task)
        result = self._result(
            candidate,
            refreshed,
            message=(
                "Restart recovery reattached the existing provider execution. A fresh recovery "
                "lease was acquired; the ComfyUI prompt was not resubmitted."
            ),
        )
        self._latest[task.task_id] = result
        return result

    def _reconcile_recovered(self, task: ProductionTask) -> ProductionExecutionResult:
        active = self._active.get(task.task_id)
        if active is None:
            raise ProductionExecutionError(
                f"Recovered execution is no longer attached: {task.task_id}"
            )
        try:
            renewed = active.service.runtime.heartbeat(
                active.queue,
                active.candidate.queue_entry_id,
                active.lease_id,
                duration_seconds=self.lease_duration_seconds,
            )
            adapter = active.service.adapters.require(active.handle.provider_id)
            refreshed = adapter.monitor(active.handle)
        except Exception as exc:
            raise ProductionExecutionError(
                f"Recovered execution reconciliation failed safely: {exc}"
            ) from exc
        active.handle = refreshed
        active.lease_id = renewed.lease_id

        if refreshed.state is ProviderExecutionState.COMPLETED:
            probe = ComfyUIRestartRecoveryProbe(self.endpoint)
            issue = self._completed_output_issue(probe, refreshed.provider_job_id)
            if issue is not None:
                current_job = self.execution_jobs.require(refreshed.execution_id)
                failed_job = self._fail_nonterminal_job(current_job, issue)
                active.queue = active.service.runtime.fail(
                    active.queue,
                    active.candidate.queue_entry_id,
                    active.lease_id,
                    issue,
                )
                failed_handle = self._failed_handle(failed_job, issue)
                result = self._result(active.candidate, failed_handle, message=issue)
                self._finish_recovery(task.task_id, result)
                return result
            durable_job = self.execution_jobs.observe(refreshed.execution_id, refreshed)
            outputs = probe.completed_outputs(refreshed.provider_job_id)
            active.queue = active.service.runtime.complete(
                active.queue,
                active.candidate.queue_entry_id,
                active.lease_id,
            )
            ingestion = GeneratedMediaIngestionService(
                self.media,
                LocalGeneratedMediaFileStore(
                    source_root=self._require_comfyui_output_directory(),
                    project_root=self.project_directory,
                    managed_relative_root=self.managed_media_directory,
                ),
            )
            ingested = ingestion.ingest_execution_outputs(durable_job, task, outputs)
            result = self._result(
                active.candidate,
                refreshed,
                generated_media_ids=tuple(item.media.media_id for item in ingested),
                message=(
                    "Recovered provider completion reconciled after restart; outputs ingested "
                    "as authoritative Generated Media."
                ),
            )
            self._finish_recovery(task.task_id, result)
            return result

        durable_job = self.execution_jobs.observe(refreshed.execution_id, refreshed)
        if refreshed.state is ProviderExecutionState.FAILED:
            active.queue = active.service.runtime.fail(
                active.queue,
                active.candidate.queue_entry_id,
                active.lease_id,
                refreshed.failure_reason or "provider execution failed after restart recovery",
            )
            result = self._result(
                active.candidate,
                refreshed,
                message=refreshed.failure_reason or "Recovered provider execution failed.",
            )
            self._finish_recovery(task.task_id, result)
            return result

        if refreshed.state is ProviderExecutionState.CANCELLED:
            active.queue = active.service.runtime.queue_engine.cancel(
                active.queue,
                active.candidate.queue_entry_id,
            )
            active.service.runtime.leases.release(active.lease_id)
            result = self._result(
                active.candidate,
                refreshed,
                message="Recovered provider execution is cancelled.",
            )
            self._finish_recovery(task.task_id, result)
            return result

        result = self._result(
            active.candidate,
            refreshed,
            message="Recovered provider execution remains active and is monitored by this session.",
        )
        self._latest[task.task_id] = result
        return result

    def _finish_recovery(self, task_id: str, result: ProductionExecutionResult) -> None:
        self._active.pop(task_id, None)
        self._recovered_tasks.discard(task_id)
        self._latest[task_id] = result

    def _completed_output_issue(
        self,
        probe: ComfyUIRestartRecoveryProbe,
        provider_job_id: str,
    ) -> str | None:
        outputs = probe.completed_outputs(provider_job_id)
        if not outputs:
            return "ComfyUI reports completion but exposes no production output files."
        source_root = self._require_comfyui_output_directory()
        missing = tuple(
            output.relative_path
            for output in outputs
            if not (source_root / Path(output.relative_path)).is_file()
        )
        if missing:
            return "ComfyUI reports completion but output file(s) do not exist: " + ", ".join(
                missing
            )
        return None

    def _fail_nonterminal_job(self, job: DurableExecutionJob, reason: str) -> DurableExecutionJob:
        if job.terminal:
            return job
        handle = self._failed_handle(job, reason)
        return self.execution_jobs.observe(job.execution_id, handle)

    @staticmethod
    def _failed_handle(job: DurableExecutionJob, reason: str) -> ProviderExecutionHandle:
        if job.provider_job_id is None:
            raise ProductionExecutionError(
                "Cannot record a post-submission recovery failure without provider job identity."
            )
        return ProviderExecutionHandle(
            execution_id=job.execution_id,
            provider_id=job.provider_id,
            provider_job_id=job.provider_job_id,
            state=ProviderExecutionState.FAILED,
            submitted_at=job.submitted_at or job.created_at,
            progress=job.progress,
            failure_reason=reason,
            metadata=job.provider_metadata,
        )

    def _failed_production_result(
        self,
        task: ProductionTask,
        job: DurableExecutionJob,
        message: str,
    ) -> ProductionExecutionResult:
        return ProductionExecutionResult(
            candidate=self._candidate(task, job.resource_id, job.entry_id),
            state=ProductionExecutionState.FAILED,
            provider_id=job.provider_id,
            execution_id=job.execution_id,
            provider_job_id=job.provider_job_id,
            progress=None,
            generated_media_ids=(),
            media_output_directory=self.managed_media_directory,
            message=message,
        )

    def _validate_recovery_authority(self, task: ProductionTask, job: DurableExecutionJob) -> None:
        if job.production_id != task.production_id or job.task_id != task.task_id:
            raise ProductionExecutionError(
                "Durable execution does not belong to the current ProductionTask scope."
            )
        if job.authority_fingerprint != task.authority.fingerprint:
            raise ProductionExecutionError(
                "ProductionTask authority changed after provider submission; restart recovery is blocked."
            )

    @staticmethod
    def _validate_queue_against_job(
        queue_id: str,
        entry_id: str,
        resource_id: str,
        job: DurableExecutionJob,
    ) -> None:
        if queue_id != job.queue_id or entry_id != job.entry_id:
            raise ProductionExecutionError(
                "Current approved schedule no longer resolves to the durable execution queue identity."
            )
        if resource_id != job.resource_id:
            raise ProductionExecutionError(
                "Current approved schedule assigns a different resource than the durable execution."
            )

    @staticmethod
    def _recovery_attempts(
        jobs: tuple[DurableExecutionJob, ...],
        current: DurableExecutionJob,
    ) -> tuple[ProductionQueueAttempt, ...]:
        relevant = tuple(
            sorted(
                (job for job in jobs if job.attempt_number <= current.attempt_number),
                key=lambda item: item.attempt_number,
            )
        )
        numbers = tuple(job.attempt_number for job in relevant)
        expected = tuple(range(1, current.attempt_number + 1))
        if numbers != expected:
            raise ProductionRestartRecoveryError(
                "Durable execution history is incomplete or contains duplicate attempt numbers."
            )
        attempts: list[ProductionQueueAttempt] = []
        for job in relevant:
            is_current = job.execution_id == current.execution_id
            if not is_current and not job.terminal:
                raise ProductionRestartRecoveryError(
                    "An earlier durable execution attempt is still non-terminal."
                )
            succeeded: bool | None = None
            error_message: str | None = None
            completed_at = None
            if not is_current:
                completed_at = job.updated_at
                succeeded = job.state is ProviderExecutionState.COMPLETED
                if not succeeded:
                    error_message = job.failure_reason or f"provider attempt {job.state.value}"
            attempts.append(
                ProductionQueueAttempt(
                    attempt_number=job.attempt_number,
                    worker_id=job.worker_id,
                    started_at=job.submitted_at or job.created_at,
                    completed_at=completed_at,
                    succeeded=succeeded,
                    error_message=error_message,
                )
            )
        return tuple(attempts)

    def _retry_attempt_history(
        self,
        task: ProductionTask,
        jobs: tuple[DurableExecutionJob, ...],
    ) -> tuple[ProductionQueueAttempt, ...]:
        if not jobs:
            return ()
        ordered = tuple(sorted(jobs, key=lambda job: job.attempt_number))
        numbers = tuple(job.attempt_number for job in ordered)
        expected = tuple(range(1, len(ordered) + 1))
        if numbers != expected:
            raise ProductionExecutionError(
                "Cannot retry because durable execution attempt history is incomplete or duplicated."
            )
        if any(not job.terminal for job in ordered):
            raise ProductionExecutionError(
                "Cannot retry while a prior durable execution is still non-terminal."
            )
        if len(ordered) >= task.attempt_policy.maximum_attempts:
            raise ProductionExecutionError(
                "ProductionTask has exhausted its configured execution attempt policy."
            )
        successful_media = bool(self.media.list_for_task(task.task_id))
        attempts: list[ProductionQueueAttempt] = []
        for job in ordered:
            succeeded = job.state is ProviderExecutionState.COMPLETED and successful_media
            attempts.append(
                ProductionQueueAttempt(
                    attempt_number=job.attempt_number,
                    worker_id=job.worker_id,
                    started_at=job.submitted_at or job.created_at,
                    completed_at=job.updated_at,
                    succeeded=succeeded,
                    error_message=(
                        None
                        if succeeded
                        else job.failure_reason
                        or "provider execution produced no authoritative production output"
                    ),
                )
            )
        return tuple(attempts)

    @staticmethod
    def _queue_with_attempt_history(
        queue: ProductionQueue,
        task_id: str,
        attempts: tuple[ProductionQueueAttempt, ...],
    ) -> ProductionQueue:
        entry = queue.entry_for_task(task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in current approved queue: {task_id}"
            )
        updated = replace(entry, attempts=attempts)
        return replace(
            queue,
            entries=tuple(
                updated if item.entry_id == entry.entry_id else item for item in queue.entries
            ),
        )

    def _durable_result(
        self,
        task: ProductionTask,
        job: DurableExecutionJob,
        *,
        message: str,
    ) -> ProductionExecutionResult:
        return ProductionExecutionResult(
            candidate=self._candidate(task, job.resource_id, job.entry_id),
            state=self._state(job.state),
            provider_id=job.provider_id,
            execution_id=job.execution_id,
            provider_job_id=job.provider_job_id,
            progress=job.progress,
            generated_media_ids=tuple(
                item.media_id for item in self.media.list_for_task(task.task_id)
            ),
            media_output_directory=self.managed_media_directory,
            message=message,
        )

    def _require_task(self, task_id: str) -> ProductionTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise ProductionExecutionError(f"ProductionTask not found: {task_id}")
        return task
