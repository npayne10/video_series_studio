"""Reconcile superseded non-terminal production executions for Phase 20.18.2."""

from __future__ import annotations

from pathlib import Path

from vscs.application.production_execution import (
    GovernedRetryOverrideStatus,
    ProductionExecutionResult,
)

from .profile_scoped_backend import (
    LocalComfyUIProductionExecutionBackend as _ProfileScopedProductionExecutionBackend,
)


class LocalComfyUIProductionExecutionBackend(_ProfileScopedProductionExecutionBackend):
    """Repair impossible stale history before profile-scoped authority decisions.

    A durable execution cannot still be active if a later governed attempt for the same
    ProductionTask already exists. Status evaluation and execution entry points therefore
    repair any such superseded non-terminal attempts as FAILED while preserving their
    durable history. The newest attempt is never changed by this repair and remains subject
    to normal provider/restart recovery.
    """

    def has_execution_for_profile(self, task_id: str, *, profile: str) -> bool:
        self._fail_superseded_nonterminal_jobs(task_id)
        return super().has_execution_for_profile(task_id, profile=profile)

    def retry_override_status_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> GovernedRetryOverrideStatus:
        self._fail_superseded_nonterminal_jobs(task_id)
        return super().retry_override_status_for_profile(task_id, profile=profile)

    def start_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        self._fail_superseded_nonterminal_jobs(task_id)
        return super().start_for_profile(
            task_id,
            profile=profile,
            production_package=production_package,
        )

    def reconcile_for_profile(self, task_id: str, *, profile: str) -> ProductionExecutionResult:
        task = self._require_task(task_id)
        if task.task_id not in self._active and task.task_id not in self._recovered_tasks:
            self._fail_superseded_nonterminal_jobs(task.task_id)
        return super().reconcile_for_profile(task.task_id, profile=profile)

    def _fail_superseded_nonterminal_jobs(self, task_id: str) -> None:
        jobs = self._ordered_jobs(task_id)
        if not jobs:
            return
        latest_attempt = max(job.attempt_number for job in jobs)
        for job in jobs:
            if job.terminal or job.attempt_number >= latest_attempt:
                continue
            self._fail_nonterminal_job(
                job,
                (
                    f"Durable execution A{job.attempt_number:03d} was still non-terminal even "
                    f"though later governed execution A{latest_attempt:03d} already exists. "
                    "VSCS reconciliation marked the superseded attempt FAILED so durable retry "
                    "authority reflects the actual execution history."
                ),
            )
