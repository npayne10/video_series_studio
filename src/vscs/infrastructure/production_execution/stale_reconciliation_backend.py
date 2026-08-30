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

    A durable execution cannot still be active if a newer governed durable record for the
    same ProductionTask already exists. Status evaluation and execution entry points therefore
    repair any such superseded non-terminal attempts as FAILED while preserving their
    durable history. Only the single newest durable record is protected by this repair and
    remains subject to normal provider/restart recovery.
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
        self._fail_superseded_nonterminal_jobs(task.task_id)
        return super().reconcile_for_profile(task.task_id, profile=profile)

    def _fail_superseded_nonterminal_jobs(self, task_id: str) -> None:
        jobs = self._ordered_jobs(task_id)
        if not jobs:
            return
        newest = jobs[-1]
        for job in jobs[:-1]:
            if job.terminal:
                continue
            self._fail_nonterminal_job(
                job,
                (
                    f"Durable execution A{job.attempt_number:03d} ({job.execution_id}) was still "
                    "non-terminal even though newer governed durable execution "
                    f"A{newest.attempt_number:03d} ({newest.execution_id}) already exists. "
                    "VSCS reconciliation marked the superseded execution FAILED so durable retry "
                    "authority reflects the actual execution history."
                ),
            )
