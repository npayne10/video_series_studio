"""Reconcile authoritative Generated Media selection back to ProductionTask completion."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar

from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskLifecycleService,
    ProductionTaskState,
    ProductionTaskTransition,
)
from vscs.domain.generated_media import GeneratedMedia, GeneratedMediaKind, GeneratedMediaState

from .persistence import GeneratedMediaPersistenceService
from .selection import GeneratedMediaSelection, GeneratedMediaSelectionRepository


class ProductionTaskCompletionReconciliationError(RuntimeError):
    """Raised when authoritative completion reconciliation cannot proceed safely."""


class ProductionTaskCompletionSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class ProductionTaskCompletionFinding:
    """One deterministic completion reconciliation finding."""

    code: str
    message: str
    severity: ProductionTaskCompletionSeverity = ProductionTaskCompletionSeverity.ERROR

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("completion finding code and message are required")


@dataclass(frozen=True, slots=True)
class ProductionTaskOutputRequirement:
    """One provider-neutral ProductionTask output contract resolved to a media kind."""

    contract: str
    media_kind: GeneratedMediaKind


@dataclass(frozen=True, slots=True)
class ProductionTaskCompletionEvidence:
    """Authoritative selected media satisfying one task output contract."""

    contract: str
    media_kind: GeneratedMediaKind
    selection_id: str
    media_id: str
    revision: int


@dataclass(frozen=True, slots=True)
class ProductionTaskCompletionAssessment:
    """Read-only deterministic assessment before any task lifecycle mutation."""

    task: ProductionTask
    requirements: tuple[ProductionTaskOutputRequirement, ...]
    evidence: tuple[ProductionTaskCompletionEvidence, ...]
    findings: tuple[ProductionTaskCompletionFinding, ...]

    @property
    def ready_to_complete(self) -> bool:
        return not any(
            finding.severity is ProductionTaskCompletionSeverity.ERROR for finding in self.findings
        )


@dataclass(frozen=True, slots=True)
class ProductionTaskCompletionReconciliationResult:
    """Result of one idempotent task completion reconciliation request."""

    task: ProductionTask
    assessment: ProductionTaskCompletionAssessment
    transitions: tuple[ProductionTaskTransition, ...]
    already_completed: bool = False

    @property
    def completed(self) -> bool:
        return self.task.state is ProductionTaskState.COMPLETED


class ProductionTaskOutputContractResolver:
    """Resolve canonical ProductionTask output contracts without provider knowledge."""

    _KINDS: ClassVar[dict[str, GeneratedMediaKind]] = {
        kind.value: kind for kind in GeneratedMediaKind
    }

    def resolve(self, contract: str) -> ProductionTaskOutputRequirement | None:
        normalized = contract.strip().casefold()
        if not normalized:
            return None
        prefix = normalized.split("/", 1)[0]
        kind = self._KINDS.get(prefix)
        if kind is None:
            return None
        return ProductionTaskOutputRequirement(contract=contract.strip(), media_kind=kind)


class ProductionTaskCompletionReconciliationService:
    """Complete ProductionTasks only from governed authoritative Generated Media selection."""

    METADATA_PREFIX = "completion_reconciliation."

    def __init__(
        self,
        lifecycle: ProductionTaskLifecycleService,
        media: GeneratedMediaPersistenceService,
        selections: GeneratedMediaSelectionRepository,
        resolver: ProductionTaskOutputContractResolver | None = None,
    ) -> None:
        self.lifecycle = lifecycle
        self.media = media
        self.selections = selections
        self.resolver = resolver or ProductionTaskOutputContractResolver()

    def assess(self, task_id: str) -> ProductionTaskCompletionAssessment:
        """Assess whether authoritative selected media satisfies every expected output."""
        task = self.lifecycle.require(task_id)
        requirements, findings = self._requirements(task)
        if findings:
            return ProductionTaskCompletionAssessment(
                task=task,
                requirements=requirements,
                evidence=(),
                findings=findings,
            )

        selections = self.selections.list_for_task(task.task_id)
        by_kind: dict[GeneratedMediaKind, list[GeneratedMediaSelection]] = {}
        for selection in selections:
            by_kind.setdefault(selection.kind, []).append(selection)

        evidence: list[ProductionTaskCompletionEvidence] = []
        issues: list[ProductionTaskCompletionFinding] = []
        for requirement in requirements:
            candidates = by_kind.get(requirement.media_kind, [])
            if not candidates:
                issues.append(
                    ProductionTaskCompletionFinding(
                        code="missing-authoritative-selection",
                        message=(
                            f"Expected output {requirement.contract!r} has no authoritative "
                            f"{requirement.media_kind.value} selection."
                        ),
                    )
                )
                continue
            if len(candidates) != 1:
                issues.append(
                    ProductionTaskCompletionFinding(
                        code="conflicting-authoritative-selection",
                        message=(
                            f"Expected output {requirement.contract!r} resolves to multiple "
                            "authoritative selections."
                        ),
                    )
                )
                continue
            selection = candidates[0]
            media = self.media.get(selection.selected_media_id)
            media_issue = self._validate_selected_media(task, requirement, selection, media)
            if media_issue is not None:
                issues.append(media_issue)
                continue
            assert media is not None
            evidence.append(
                ProductionTaskCompletionEvidence(
                    contract=requirement.contract,
                    media_kind=requirement.media_kind,
                    selection_id=selection.selection_id,
                    media_id=media.media_id,
                    revision=media.revision,
                )
            )

        return ProductionTaskCompletionAssessment(
            task=task,
            requirements=requirements,
            evidence=tuple(sorted(evidence, key=lambda item: item.contract.casefold())),
            findings=tuple(sorted(issues, key=lambda item: (item.code, item.message))),
        )

    def reconcile(
        self,
        task_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionTaskCompletionReconciliationResult:
        """Persist COMPLETED only when governed selected media satisfies task outputs."""
        assessment = self.assess(task_id)
        task = assessment.task
        if task.state is ProductionTaskState.COMPLETED:
            return ProductionTaskCompletionReconciliationResult(
                task=task,
                assessment=assessment,
                transitions=(),
                already_completed=True,
            )
        if not assessment.ready_to_complete:
            return ProductionTaskCompletionReconciliationResult(
                task=task,
                assessment=assessment,
                transitions=(),
            )
        if task.state not in {ProductionTaskState.READY, ProductionTaskState.RUNNING}:
            blocked = ProductionTaskCompletionAssessment(
                task=task,
                requirements=assessment.requirements,
                evidence=assessment.evidence,
                findings=(
                    ProductionTaskCompletionFinding(
                        code="task-state-not-completable",
                        message=(
                            "ProductionTask completion reconciliation requires READY or RUNNING "
                            f"state, not {task.state.value}."
                        ),
                    ),
                ),
            )
            return ProductionTaskCompletionReconciliationResult(
                task=task,
                assessment=blocked,
                transitions=(),
            )

        current = now or datetime.now(UTC)
        working = task
        transitions: list[ProductionTaskTransition] = []
        if working.state is ProductionTaskState.READY:
            working, staged = self.lifecycle.stages.transition(
                working,
                ProductionTaskState.RUNNING,
                reason="Governed selected media proves completed execution for reconciliation",
                now=current,
            )
            transitions.append(staged)

        working, completed = self.lifecycle.stages.transition(
            working,
            ProductionTaskState.COMPLETED,
            reason="Authoritative selected Generated Media satisfies expected outputs",
            now=current,
        )
        transitions.append(completed)
        working = replace(
            working,
            metadata=self._completion_metadata(task, assessment.evidence, current),
        )
        saved = self.lifecycle.repository.save(working)
        return ProductionTaskCompletionReconciliationResult(
            task=saved,
            assessment=assessment,
            transitions=tuple(transitions),
        )

    def _requirements(
        self,
        task: ProductionTask,
    ) -> tuple[
        tuple[ProductionTaskOutputRequirement, ...],
        tuple[ProductionTaskCompletionFinding, ...],
    ]:
        requirements: list[ProductionTaskOutputRequirement] = []
        findings: list[ProductionTaskCompletionFinding] = []
        kinds: set[GeneratedMediaKind] = set()
        for contract in sorted(task.expected_outputs, key=str.casefold):
            requirement = self.resolver.resolve(contract)
            if requirement is None:
                findings.append(
                    ProductionTaskCompletionFinding(
                        code="unsupported-output-contract",
                        message=f"Expected output contract is not supported: {contract!r}.",
                    )
                )
                continue
            if requirement.media_kind in kinds:
                findings.append(
                    ProductionTaskCompletionFinding(
                        code="ambiguous-output-contract-kind",
                        message=(
                            "Multiple expected outputs resolve to the same selection slot kind: "
                            f"{requirement.media_kind.value}."
                        ),
                    )
                )
                continue
            kinds.add(requirement.media_kind)
            requirements.append(requirement)
        return tuple(requirements), tuple(
            sorted(findings, key=lambda item: (item.code, item.message))
        )

    @staticmethod
    def _validate_selected_media(
        task: ProductionTask,
        requirement: ProductionTaskOutputRequirement,
        selection: GeneratedMediaSelection,
        media: GeneratedMedia | None,
    ) -> ProductionTaskCompletionFinding | None:
        if media is None:
            return ProductionTaskCompletionFinding(
                code="selected-media-missing",
                message=f"Selected Generated Media does not exist: {selection.selected_media_id}.",
            )
        if (
            selection.production_id != task.production_id
            or selection.episode_id != task.episode_id
            or selection.production_task_id != task.task_id
            or media.scope.production_id != task.production_id
            or media.scope.episode_id != task.episode_id
            or media.scope.production_task_id != task.task_id
        ):
            return ProductionTaskCompletionFinding(
                code="selection-task-authority-mismatch",
                message="Selected Generated Media does not belong to the ProductionTask authority.",
            )
        if selection.kind is not requirement.media_kind or media.kind is not requirement.media_kind:
            return ProductionTaskCompletionFinding(
                code="selected-media-kind-mismatch",
                message=f"Selected media does not satisfy {requirement.contract!r}.",
            )
        if media.state is not GeneratedMediaState.APPROVED:
            return ProductionTaskCompletionFinding(
                code="selected-media-not-approved",
                message="Authoritative selected Generated Media must remain APPROVED.",
            )
        if selection.selected_revision != media.revision:
            return ProductionTaskCompletionFinding(
                code="selection-revision-mismatch",
                message="Generated Media selection revision does not match selected media.",
            )
        if not selection.selected_by.startswith("human:"):
            return ProductionTaskCompletionFinding(
                code="selection-not-human-authorised",
                message="Authoritative media selection must retain explicit human authority.",
            )
        metadata = dict(media.technical_metadata)
        if metadata.get("technical_validation.status", "").strip().casefold() != "passed":
            return ProductionTaskCompletionFinding(
                code="selected-media-not-technically-valid",
                message="Selected Generated Media must retain a passed technical validation.",
            )
        approval = next(
            (
                event
                for event in reversed(media.governance_history)
                if event.to_state is GeneratedMediaState.APPROVED
            ),
            None,
        )
        if approval is None or not approval.actor.startswith("human:"):
            return ProductionTaskCompletionFinding(
                code="selected-media-not-human-approved",
                message="Selected Generated Media must retain explicit human approval authority.",
            )
        provenance = dict(media.provenance.attributes)
        if provenance.get("authority_fingerprint") != task.authority.fingerprint:
            return ProductionTaskCompletionFinding(
                code="production-authority-fingerprint-mismatch",
                message="Selected Generated Media was produced under different task authority.",
            )
        return None

    def _completion_metadata(
        self,
        task: ProductionTask,
        evidence: tuple[ProductionTaskCompletionEvidence, ...],
        completed_at: datetime,
    ) -> tuple[tuple[str, str], ...]:
        retained = tuple(
            (key, value) for key, value in task.metadata if not key.startswith(self.METADATA_PREFIX)
        )
        values: list[tuple[str, str]] = [
            ("completion_reconciliation.status", "completed"),
            ("completion_reconciliation.completed_at", completed_at.isoformat()),
            ("completion_reconciliation.authority_fingerprint", task.authority.fingerprint),
        ]
        for index, item in enumerate(evidence, start=1):
            stem = f"completion_reconciliation.output.{index:03d}"
            values.extend(
                (
                    (f"{stem}.contract", item.contract),
                    (f"{stem}.kind", item.media_kind.value),
                    (f"{stem}.selection_id", item.selection_id),
                    (f"{stem}.media_id", item.media_id),
                    (f"{stem}.revision", str(item.revision)),
                )
            )
        return (*retained, *values)
