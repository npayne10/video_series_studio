"""Production-level completion gate for live ComfyUI execution.

Provider graph completion is provisional. VSCS only exposes production COMPLETED after
provider outputs exist, their source files are present, and Generated Media ingestion succeeds.
"""

from __future__ import annotations

from pathlib import Path

from vscs.application.generated_media import GeneratedMediaIngestionService
from vscs.application.production_execution import (
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionExecutionState,
)
from vscs.application.production_tasks import ProductionTask
from vscs.application.provider_execution import (
    DurableExecutionJob,
    ProviderExecutionHandle,
    ProviderExecutionOutput,
    ProviderExecutionState,
)
from vscs.infrastructure.generated_media import LocalGeneratedMediaFileStore

from .compiled_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase2016RecoveryBackend,
)


class LocalComfyUIProductionExecutionBackend(_Phase2016RecoveryBackend):
    """Require authoritative output ingestion before reporting production completion."""

    def reconcile(self, task_id: str) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        if task.task_id in self._recovered_tasks or task.task_id not in self._active:
            return super().reconcile(task.task_id)
        return self._reconcile_current_session(task)

    def _reconcile_current_session(self, task: ProductionTask) -> ProductionExecutionResult:
        active = self._active.get(task.task_id)
        if active is None:
            raise ProductionExecutionError(
                f"Active execution is no longer attached: {task.task_id}"
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
                f"Current production reconciliation failed safely: {exc}"
            ) from exc

        active.handle = refreshed
        active.lease_id = renewed.lease_id

        if refreshed.state is ProviderExecutionState.COMPLETED:
            return self._finalize_current_completion(task, active, adapter, refreshed)

        durable_job = self.execution_jobs.observe(refreshed.execution_id, refreshed)
        if refreshed.state is ProviderExecutionState.FAILED:
            active.queue = active.service.runtime.fail(
                active.queue,
                active.candidate.queue_entry_id,
                active.lease_id,
                refreshed.failure_reason or "provider execution failed",
            )
            result = self._result(
                active.candidate,
                refreshed,
                message=durable_job.failure_reason or "Provider execution failed.",
            )
            self._finish_current(task.task_id, result)
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
                message="Provider execution was cancelled.",
            )
            self._finish_current(task.task_id, result)
            return result

        result = self._result(active.candidate, refreshed)
        self._latest[task.task_id] = result
        return result

    def _finalize_current_completion(
        self,
        task: ProductionTask,
        active: object,
        adapter: object,
        refreshed: ProviderExecutionHandle,
    ) -> ProductionExecutionResult:
        try:
            outputs = adapter.fetch_outputs(refreshed)  # type: ignore[attr-defined]
        except Exception as exc:
            return self._fail_current_completion(
                task,
                active,
                refreshed,
                f"ComfyUI reported completion but output discovery failed: {exc}",
            )

        issue = self._current_output_issue(outputs)
        if issue is not None:
            return self._fail_current_completion(task, active, refreshed, issue)

        durable_job = self.execution_jobs.observe(refreshed.execution_id, refreshed)
        try:
            ingested = GeneratedMediaIngestionService(
                self.media,
                LocalGeneratedMediaFileStore(
                    source_root=self._require_comfyui_output_directory(),
                    project_root=self.project_directory,
                    managed_relative_root=self.managed_media_directory,
                ),
            ).ingest_execution_outputs(durable_job, task, outputs)
        except Exception as exc:
            message = f"Provider completed but VSCS could not ingest production output: {exc}"
            self._fail_queue_after_provider_completion(active, message)
            result = self._production_failure_result(task, durable_job, message)
            self._finish_current(task.task_id, result)
            return result

        active.queue = active.service.runtime.complete(  # type: ignore[attr-defined]
            active.queue,  # type: ignore[attr-defined]
            active.candidate.queue_entry_id,  # type: ignore[attr-defined]
            active.lease_id,  # type: ignore[attr-defined]
        )
        result = self._result(
            active.candidate,  # type: ignore[attr-defined]
            refreshed,
            generated_media_ids=tuple(item.media.media_id for item in ingested),
            message=(
                "Provider completed; output files validated, copied into project media storage, "
                "and ingested as authoritative Generated Media."
            ),
        )
        self._finish_current(task.task_id, result)
        return result

    def _fail_current_completion(
        self,
        task: ProductionTask,
        active: object,
        refreshed: ProviderExecutionHandle,
        reason: str,
    ) -> ProductionExecutionResult:
        current_job = self.execution_jobs.require(refreshed.execution_id)
        if current_job.terminal:
            failed_handle = self._provider_fact_as_failed_handle(current_job, reason)
        else:
            failed_handle = self._failed_handle(current_job, reason)
            self.execution_jobs.observe(current_job.execution_id, failed_handle)
        active.handle = failed_handle  # type: ignore[attr-defined]
        active.queue = active.service.runtime.fail(  # type: ignore[attr-defined]
            active.queue,  # type: ignore[attr-defined]
            active.candidate.queue_entry_id,  # type: ignore[attr-defined]
            active.lease_id,  # type: ignore[attr-defined]
            reason,
        )
        result = self._result(active.candidate, failed_handle, message=reason)  # type: ignore[attr-defined]
        self._finish_current(task.task_id, result)
        return result

    def _current_output_issue(
        self,
        outputs: tuple[ProviderExecutionOutput, ...],
    ) -> str | None:
        if not outputs:
            return "ComfyUI reported completion but produced no production output files."
        source_root = self._require_comfyui_output_directory()
        missing = tuple(
            output.relative_path
            for output in outputs
            if not (source_root / Path(output.relative_path)).is_file()
        )
        if missing:
            return "ComfyUI reported completion but output file(s) do not exist: " + ", ".join(
                missing
            )
        return None

    def _fail_queue_after_provider_completion(self, active: object, reason: str) -> None:
        try:
            active.queue = active.service.runtime.fail(  # type: ignore[attr-defined]
                active.queue,  # type: ignore[attr-defined]
                active.candidate.queue_entry_id,  # type: ignore[attr-defined]
                active.lease_id,  # type: ignore[attr-defined]
                reason,
            )
        except Exception:
            active.service.runtime.leases.release(active.lease_id)  # type: ignore[attr-defined]

    def _production_failure_result(
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
            generated_media_ids=tuple(
                item.media_id for item in self.media.list_for_task(task.task_id)
            ),
            media_output_directory=self.managed_media_directory,
            message=message,
        )

    @staticmethod
    def _provider_fact_as_failed_handle(
        job: DurableExecutionJob,
        reason: str,
    ) -> ProviderExecutionHandle:
        if job.provider_job_id is None:
            raise ProductionExecutionError(
                "Cannot represent failed production completion without provider job identity."
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

    def _finish_current(self, task_id: str, result: ProductionExecutionResult) -> None:
        self._active.pop(task_id, None)
        self._latest[task_id] = result
