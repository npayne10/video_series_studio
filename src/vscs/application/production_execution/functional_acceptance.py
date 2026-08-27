"""End-to-end Phase 20.18.2 orchestration for one governed live video shot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from vscs.application.acpp import ReferencePlan
from vscs.application.generated_media import (
    GeneratedMediaIngestionResult,
    GeneratedMediaIngestionService,
)
from vscs.application.production_tasks import ProductionQueue, ProductionTask
from vscs.application.provider_execution import (
    ProviderExecutionHandle,
    QueueProviderExecutionReconciliation,
    QueueProviderExecutionService,
    QueueProviderExecutionSubmission,
)

from .package_compilation import CompiledProductionPackage
from .reference_plan_rendering import (
    ReferencePlanRenderBinding,
    ReferencePlanRenderRequestBinder,
)


class LiveShotFunctionalAcceptanceError(RuntimeError):
    """Raised when the governed Phase 20 live-shot chain cannot proceed safely."""


@dataclass(frozen=True, slots=True)
class LiveShotFunctionalAcceptanceSubmission:
    """Reference binding and provider submission for one live acceptance shot."""

    binding: ReferencePlanRenderBinding
    provider_submission: QueueProviderExecutionSubmission

    @property
    def submitted(self) -> bool:
        return self.provider_submission.submitted


@dataclass(frozen=True, slots=True)
class LiveShotFunctionalAcceptanceReconciliation:
    """Provider reconciliation plus any authoritative Generated Media registration."""

    provider_reconciliation: QueueProviderExecutionReconciliation
    generated_media: tuple[GeneratedMediaIngestionResult, ...] = ()

    @property
    def completed(self) -> bool:
        return self.provider_reconciliation.handle.state.value == "completed"


class LiveShotFunctionalAcceptanceService:
    """Prove ReferencePlan -> provider execution -> GeneratedMedia for a real Shot."""

    def __init__(
        self,
        *,
        execution: QueueProviderExecutionService,
        ingestion: GeneratedMediaIngestionService,
        binder: ReferencePlanRenderRequestBinder | None = None,
    ) -> None:
        self.execution = execution
        self.ingestion = ingestion
        self.binder = binder or ReferencePlanRenderRequestBinder()

    def submit(
        self,
        *,
        queue: ProductionQueue,
        entry_id: str,
        worker_id: str,
        task: ProductionTask,
        package: CompiledProductionPackage,
        reference_plan: ReferencePlan,
        production_package_path: str,
        lease_duration_seconds: float,
        provider_id: str,
        workflow_id: str = "ltx23_production_v1",
        now: datetime | None = None,
    ) -> LiveShotFunctionalAcceptanceSubmission:
        """Bind governed references and submit one queue-authorised live video render."""
        if task.task_id != package.task_id:
            raise LiveShotFunctionalAcceptanceError(
                "Compiled production package does not belong to the ProductionTask"
            )
        if task.authority.fingerprint != package.authority_fingerprint:
            raise LiveShotFunctionalAcceptanceError(
                "Compiled production package authority no longer matches the ProductionTask"
            )
        binding = self.binder.bind(package, reference_plan, workflow_id=workflow_id)
        submission = self.execution.submit(
            queue,
            entry_id,
            worker_id,
            binding.request,
            production_package_path,
            lease_duration_seconds=lease_duration_seconds,
            provider_id=provider_id,
            now=now,
        )
        return LiveShotFunctionalAcceptanceSubmission(
            binding=binding,
            provider_submission=submission,
        )

    def reconcile(
        self,
        *,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        handle: ProviderExecutionHandle,
        task: ProductionTask,
        lease_duration_seconds: float,
        now: datetime | None = None,
    ) -> LiveShotFunctionalAcceptanceReconciliation:
        """Monitor provider state and ingest terminal outputs under VSCS authority."""
        reconciliation = self.execution.reconcile(
            queue,
            entry_id,
            lease_id,
            handle,
            lease_duration_seconds=lease_duration_seconds,
            now=now,
        )
        if not reconciliation.terminal or not reconciliation.outputs:
            return LiveShotFunctionalAcceptanceReconciliation(reconciliation)
        if reconciliation.execution_job is None:
            raise LiveShotFunctionalAcceptanceError(
                "Completed provider execution has no durable execution record for provenance"
            )
        if reconciliation.handle.state.value != "completed":
            return LiveShotFunctionalAcceptanceReconciliation(reconciliation)
        media = self.ingestion.ingest_execution_outputs(
            reconciliation.execution_job,
            task,
            reconciliation.outputs,
        )
        return LiveShotFunctionalAcceptanceReconciliation(
            provider_reconciliation=reconciliation,
            generated_media=media,
        )
