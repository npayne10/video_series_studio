"""Human-governed retry override composition for Phase 20.16.1."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from vscs.application.production_execution import ProductionExecutionError
from vscs.application.production_execution.retry_override import (
    GovernedRetryAuthorization,
    GovernedRetryOverrideState,
    GovernedRetryOverrideStatus,
)
from vscs.application.production_tasks import ProductionQueueAttempt, ProductionTask
from vscs.application.provider_execution import DurableExecutionJob, ProviderExecutionState

from .finalizing_backend import (
    LocalComfyUIProductionExecutionBackend as _Phase2016FinalizingBackend,
)
from .retry_override_store import LocalGovernedRetryAuthorizationStore


class LocalComfyUIProductionExecutionBackend(_Phase2016FinalizingBackend):
    """Require explicit human authority for attempts beyond the configured retry policy."""

    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.retry_authorizations = LocalGovernedRetryAuthorizationStore(self.project_directory)

    def retry_override_status(self, task_id: str) -> GovernedRetryOverrideStatus:
        task = self._require_task(task_id)
        jobs = self._ordered_jobs(task.task_id)
        matching = self._matching_authorizations(task)
        base = task.attempt_policy.maximum_attempts
        effective = base + len(matching)
        attempts = len(jobs)
        latest = matching[-1] if matching else None

        if any(not job.terminal for job in jobs):
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.BLOCKED,
                base,
                attempts,
                effective,
                latest_authorization=latest,
                message="A provider execution is still non-terminal; retry override is unavailable.",
            )
        if self.media.list_for_task(task.task_id):
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.BLOCKED,
                base,
                attempts,
                effective,
                latest_authorization=latest,
                message="Authoritative Generated Media already exists; retry override is unavailable.",
            )
        if attempts < base:
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.NOT_REQUIRED,
                base,
                attempts,
                effective,
                next_attempt_number=attempts + 1,
                latest_authorization=latest,
                message="Configured retry policy still permits another attempt.",
            )
        if attempts < effective:
            return GovernedRetryOverrideStatus(
                GovernedRetryOverrideState.AUTHORIZED,
                base,
                attempts,
                effective,
                next_attempt_number=attempts + 1,
                latest_authorization=latest,
                message=(
                    f"Human retry override authorizes attempt A{attempts + 1:03d}. "
                    "The authorization is consumed when that attempt is created."
                ),
            )
        return GovernedRetryOverrideStatus(
            GovernedRetryOverrideState.ELIGIBLE,
            base,
            attempts,
            effective,
            next_attempt_number=attempts + 1,
            latest_authorization=latest,
            message=(
                f"Retry limit exhausted after {attempts} attempt(s). A human may authorize "
                f"exactly one additional attempt A{attempts + 1:03d}."
            ),
        )

    def authorize_retry(
        self,
        task_id: str,
        *,
        authorized_by: str,
        reason: str,
    ) -> GovernedRetryOverrideStatus:
        task = self._require_task(task_id)
        actor = authorized_by.strip()
        justification = reason.strip()
        if not actor:
            raise ProductionExecutionError("Retry override requires an authorizing human identity.")
        if not justification:
            raise ProductionExecutionError("Retry override requires a non-blank reason.")
        status = self.retry_override_status(task.task_id)
        if not status.eligible or status.next_attempt_number is None:
            raise ProductionExecutionError(
                status.message or "Retry override is not currently eligible."
            )
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
        return self.retry_override_status(task.task_id)

    def has_execution(self, task_id: str) -> bool:
        task = self._require_task(task_id)
        if task.task_id in self._active:
            return True
        jobs = self._ordered_jobs(task.task_id)
        if not jobs:
            return False
        if any(not job.terminal for job in jobs):
            return True
        latest = jobs[-1]
        if latest.state is ProviderExecutionState.COMPLETED and self.media.list_for_task(
            task.task_id
        ):
            return True
        effective = task.attempt_policy.maximum_attempts + len(self._matching_authorizations(task))
        return len(jobs) >= effective

    def _retry_attempt_history(
        self,
        task: ProductionTask,
        jobs: tuple[DurableExecutionJob, ...],
    ) -> tuple[ProductionQueueAttempt, ...]:
        effective = task.attempt_policy.maximum_attempts + len(self._matching_authorizations(task))
        widened = replace(
            task,
            attempt_policy=replace(task.attempt_policy, maximum_attempts=effective),
        )
        return super()._retry_attempt_history(widened, jobs)

    def _matching_authorizations(
        self,
        task: ProductionTask,
    ) -> tuple[GovernedRetryAuthorization, ...]:
        return tuple(
            sorted(
                (
                    item
                    for item in self.retry_authorizations.list_for_task(task.task_id)
                    if item.production_id == task.production_id
                    and item.authority_fingerprint == task.authority.fingerprint
                ),
                key=lambda item: (
                    item.authorized_attempt_number,
                    item.created_at,
                    item.authorization_id,
                ),
            )
        )

    def _ordered_jobs(self, task_id: str) -> tuple[DurableExecutionJob, ...]:
        return tuple(
            sorted(
                self.execution_jobs.list_for_task(task_id),
                key=lambda item: (item.attempt_number, item.updated_at, item.execution_id),
            )
        )
