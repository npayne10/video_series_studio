"""Profile-scoped execution attempt authority for Phase 20.16.2."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vscs.application.production_execution import (
    GovernedRetryAuthorization,
    GovernedRetryOverrideState,
    GovernedRetryOverrideStatus,
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionExecutionState,
    ProductionTelemetrySnapshot,
    ProductionTelemetryState,
    normalize_execution_profile,
)
from vscs.application.production_tasks import (
    ProductionQueue,
    ProductionQueueAttempt,
    ProductionQueueCompilerService,
    ProductionTask,
)
from vscs.application.provider_execution import DurableExecutionJob, ProviderExecutionState

from .comfyui_backend import _ActiveExecution
from .execution_profile_store import LocalExecutionProfileStore
from .governed_retry_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase20161GovernedRetryBackend,
)
from .live_telemetry import ComfyUIProductionTelemetryReader
from .package_compilation import LocalProductionPackageCompilationError
from .retry_profile_store import LocalRetryAuthorizationProfileStore


class LocalComfyUIProductionExecutionBackend(_Phase20161GovernedRetryBackend):
    """Give Preview, Production and Master independent attempt budgets."""

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.execution_profiles = LocalExecutionProfileStore(self.project_directory)
        self.retry_profiles = LocalRetryAuthorizationProfileStore(self.project_directory)

    def has_execution_for_profile(self, task_id: str, *, profile: str) -> bool:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        if task.task_id in self._active:
            return True
        all_jobs = self._ordered_jobs(task.task_id)
        if any(not job.terminal for job in all_jobs):
            return True
        if self._media_for_profile(task.task_id, normalized):
            return True
        profile_jobs = self._jobs_for_profile(all_jobs, normalized)
        effective = task.attempt_policy.maximum_attempts + len(
            self._authorizations_for_profile(task, normalized)
        )
        return len(profile_jobs) >= effective

    def telemetry_for_profile(self, task_id: str, *, profile: str) -> ProductionTelemetrySnapshot:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        active = self._active.get(task.task_id)
        if active is not None:
            return super().telemetry(task.task_id)
        jobs = self._jobs_for_profile(self._ordered_jobs(task.task_id), normalized)
        if not jobs:
            raise ProductionExecutionError(
                f"No {normalized} execution exists for ProductionTask: {task.task_id}"
            )
        latest = jobs[-1]
        snapshot = ComfyUIProductionTelemetryReader(self.endpoint).observe_durable(latest)
        if latest.state is ProviderExecutionState.COMPLETED and not self._media_for_profile(
            task.task_id, normalized
        ):
            return replace(
                snapshot,
                state=ProductionTelemetryState.FAILED,
                progress=None,
                stage=f"{normalized.title()} provider completion has no governed production output",
                message=(
                    f"{normalized.title()} provider execution reached COMPLETED but no Generated "
                    "Media or recoverable output exists; VSCS treats that profile attempt as failed."
                ),
            )
        return snapshot

    def retry_override_status_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> GovernedRetryOverrideStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        all_jobs = self._ordered_jobs(task.task_id)
        profile_jobs = self._jobs_for_profile(all_jobs, normalized)
        authorizations = self._authorizations_for_profile(task, normalized)
        base = task.attempt_policy.maximum_attempts
        effective = base + len(authorizations)
        attempts = len(profile_jobs)
        latest = authorizations[-1] if authorizations else None
        profile_label = normalized.title()
        next_profile_attempt = attempts + 1
        next_global_attempt = max((job.attempt_number for job in all_jobs), default=0) + 1

        if any(not job.terminal for job in all_jobs):
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.BLOCKED,
                base,
                attempts,
                effective,
                latest_authorization=latest,
                message=(
                    f"A provider execution is still non-terminal; {profile_label} retry authority "
                    "cannot change while another profile is executing."
                ),
            )
        if self._media_for_profile(task.task_id, normalized):
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.BLOCKED,
                base,
                attempts,
                effective,
                latest_authorization=latest,
                message=f"{profile_label} Generated Media already exists; retry override is unavailable.",
            )
        if attempts < base:
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.NOT_REQUIRED,
                base,
                attempts,
                effective,
                next_attempt_number=next_profile_attempt,
                latest_authorization=latest,
                message=(
                    f"{profile_label} still permits attempt {next_profile_attempt}/{effective}. "
                    f"The next global execution identity will be A{next_global_attempt:03d}."
                ),
            )
        if attempts < effective:
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.AUTHORIZED,
                base,
                attempts,
                effective,
                next_attempt_number=next_profile_attempt,
                latest_authorization=latest,
                message=(
                    f"Human retry override authorizes {profile_label} attempt "
                    f"{next_profile_attempt}/{effective}. The next global execution identity will be "
                    f"A{next_global_attempt:03d}."
                ),
            )
        return GovernedRetryOverrideStatus(
            GovernedRetryOverrideState.ELIGIBLE,
            base,
            attempts,
            effective,
            next_attempt_number=next_profile_attempt,
            latest_authorization=latest,
            message=(
                f"{profile_label} retry limit is exhausted after {attempts} profile attempt(s). "
                f"A human may authorize exactly one additional {profile_label} attempt."
            ),
        )

    def authorize_retry_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        actor = authorized_by.strip()
        justification = reason.strip()
        if not actor:
            raise ProductionExecutionError("Retry override requires an authorizing human identity.")
        if not justification:
            raise ProductionExecutionError("Retry override requires a non-blank reason.")
        status = self.retry_override_status_for_profile(task.task_id, profile=normalized)
        if not status.eligible or status.next_attempt_number is None:
            raise ProductionExecutionError(status.message or "Retry override is not currently eligible.")
        authorization = GovernedRetryAuthorization(
            authorization_id=f"GRO-{uuid4().hex.upper()}",
            production_id=task.production_id,
            task_id=task.task_id,
            authority_fingerprint=task.authority.fingerprint,
            authorized_attempt_number=status.next_attempt_number,
            authorized_by=actor,
            reason=justification,
            created_at=datetime.now(UTC),
        )
        self.retry_authorizations.save(authorization)
        self.retry_profiles.assign(authorization.authorization_id, task.task_id, normalized)
        return self.retry_override_status_for_profile(task.task_id, profile=normalized)

    def start_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        if self.has_execution_for_profile(task.task_id, profile=normalized):
            raise ProductionExecutionError(
                f"{normalized.title()} execution is active, successful, or has exhausted its "
                "profile-scoped attempt allowance. Inspect profile execution status first."
            )
        try:
            if production_package is None:
                package = self.package_compilation.require_current(task, profile=normalized).path
                assert package is not None
            else:
                package = Path(production_package).expanduser().resolve(strict=False)
                self.package_compilation.validate_file(task, package)
                payload_profile = self._package_profile(package)
                if payload_profile != normalized:
                    raise ProductionExecutionError(
                        f"Production Package profile {payload_profile!r} does not match selected "
                        f"profile {normalized!r}."
                    )
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

        queue = ProductionQueueCompilerService(self.schedules, self.tasks).compile(task.production_id)
        entry = queue.entry_for_task(task.task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in the current approved queue: {task.task_id}"
            )
        all_jobs = tuple(
            sorted(
                self.execution_jobs.list_for_queue_entry(queue.queue_id, entry.entry_id),
                key=lambda item: item.attempt_number,
            )
        )
        history = self._global_attempt_history(task, all_jobs)
        profile_jobs = self._jobs_for_profile(all_jobs, normalized)
        effective = task.attempt_policy.maximum_attempts + len(
            self._authorizations_for_profile(task, normalized)
        )
        remaining = effective - len(profile_jobs)
        if remaining < 1:
            raise ProductionExecutionError(
                f"{normalized.title()} has exhausted its profile-scoped execution attempt allowance."
            )
        if history:
            queue = self._queue_with_profile_history(
                queue,
                task.task_id,
                history,
                maximum_attempts=len(history) + remaining,
            )
            entry = queue.entry_for_task(task.task_id)
            assert entry is not None

        next_global_attempt = len(history) + 1
        predicted_execution_id = (
            f"PEX-{queue.queue_id}-{entry.entry_id}-A{next_global_attempt:03d}"
        )
        self.execution_profiles.assign(
            predicted_execution_id,
            task.task_id,
            normalized,
        )

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
        actual_execution_id = (
            submission.handle.execution_id
            if submission.handle is not None
            else submission.execution_job.execution_id
            if submission.execution_job is not None
            else None
        )
        if actual_execution_id is not None and actual_execution_id != predicted_execution_id:
            raise ProductionExecutionError(
                "Provider execution identity did not match the governed profile assignment."
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
            message=(
                f"{normalized.title()} provider submitted as global execution "
                f"A{next_global_attempt:03d}; source output: {source_root}"
            ),
        )
        self._latest[task.task_id] = result
        return result

    def reconcile_for_profile(self, task_id: str, *, profile: str) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        if task.task_id in self._active or task.task_id in self._recovered_tasks:
            return super().reconcile(task.task_id)
        jobs = self._jobs_for_profile(self._ordered_jobs(task.task_id), normalized)
        if not jobs:
            raise ProductionExecutionError(
                f"No {normalized} execution exists for ProductionTask: {task.task_id}"
            )
        latest = jobs[-1]
        if not latest.terminal:
            return super().recover(task.task_id)
        if latest.state is ProviderExecutionState.COMPLETED:
            if self._media_for_profile(task.task_id, normalized):
                return self._durable_result(
                    task,
                    latest,
                    message=f"Completed {normalized} execution is reconciled to Generated Media.",
                )
            return self._failed_production_result(
                task,
                latest,
                f"{normalized.title()} provider completion has no authoritative production output.",
            )
        return self._durable_result(
            task,
            latest,
            message=(
                f"Durable {normalized} execution is terminal and unsuccessful. A profile-scoped "
                "retry is allowed if that profile's attempt policy permits."
            ),
        )

    def _jobs_for_profile(
        self,
        jobs: tuple[DurableExecutionJob, ...],
        profile: str,
    ) -> tuple[DurableExecutionJob, ...]:
        normalized = normalize_execution_profile(profile)
        return tuple(
            job
            for job in jobs
            if self.execution_profiles.profile_for_execution(job.execution_id) == normalized
        )

    def _authorizations_for_profile(
        self,
        task: ProductionTask,
        profile: str,
    ) -> tuple[GovernedRetryAuthorization, ...]:
        normalized = normalize_execution_profile(profile)
        return tuple(
            sorted(
                (
                    item
                    for item in self.retry_authorizations.list_for_task(task.task_id)
                    if item.production_id == task.production_id
                    and item.authority_fingerprint == task.authority.fingerprint
                    and self.retry_profiles.profile_for_authorization(item.authorization_id)
                    == normalized
                ),
                key=lambda item: (
                    item.authorized_attempt_number,
                    item.created_at,
                    item.authorization_id,
                ),
            )
        )

    def _media_for_profile(self, task_id: str, profile: str) -> tuple[object, ...]:
        normalized = normalize_execution_profile(profile)
        return tuple(
            media
            for media in self.media.list_for_task(task_id)
            if self.execution_profiles.profile_for_execution(media.provenance.execution_id)
            == normalized
        )

    def _global_attempt_history(
        self,
        task: ProductionTask,
        jobs: tuple[DurableExecutionJob, ...],
    ) -> tuple[ProductionQueueAttempt, ...]:
        if not jobs:
            return ()
        numbers = tuple(job.attempt_number for job in jobs)
        expected = tuple(range(1, len(jobs) + 1))
        if numbers != expected:
            raise ProductionExecutionError(
                "Cannot execute because global durable attempt history is incomplete or duplicated."
            )
        if any(not job.terminal for job in jobs):
            raise ProductionExecutionError(
                "Cannot execute another profile while a prior durable execution is non-terminal."
            )
        media_execution_ids = {
            item.provenance.execution_id for item in self.media.list_for_task(task.task_id)
        }
        return tuple(
            ProductionQueueAttempt(
                attempt_number=job.attempt_number,
                worker_id=job.worker_id,
                started_at=job.submitted_at or job.created_at,
                completed_at=job.updated_at,
                succeeded=(
                    job.state is ProviderExecutionState.COMPLETED
                    and job.execution_id in media_execution_ids
                ),
                error_message=(
                    None
                    if job.state is ProviderExecutionState.COMPLETED
                    and job.execution_id in media_execution_ids
                    else job.failure_reason
                    or "provider execution produced no authoritative production output"
                ),
            )
            for job in jobs
        )

    @staticmethod
    def _queue_with_profile_history(
        queue: ProductionQueue,
        task_id: str,
        attempts: tuple[ProductionQueueAttempt, ...],
        *,
        maximum_attempts: int,
    ) -> ProductionQueue:
        entry = queue.entry_for_task(task_id)
        if entry is None:
            raise ProductionExecutionError(
                f"ProductionTask is not present in current approved queue: {task_id}"
            )
        updated = replace(
            entry,
            attempts=attempts,
            maximum_attempts=max(maximum_attempts, len(attempts) + 1),
        )
        return replace(
            queue,
            entries=tuple(
                updated if item.entry_id == entry.entry_id else item for item in queue.entries
            ),
        )

    @staticmethod
    def _package_profile(path: Path) -> str:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ProductionExecutionError("Production Package JSON root is not an object")
        return normalize_execution_profile(str(payload.get("profile", "production")))
