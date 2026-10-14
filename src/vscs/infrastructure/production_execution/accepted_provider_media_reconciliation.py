"""Reconcile already-accepted provider production into Generated Media authority.

Phase 20.18.2.3.6.6b.5 closes the compatibility gap for real provider
productions that were functionally accepted before Generated Media ingestion and
ProductionTask completion reconciliation became authoritative.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from vscs.application.generated_media.persistence import GeneratedMediaPersistenceService
from vscs.application.generated_media.review import (
    GeneratedMediaReviewActor,
    GeneratedMediaReviewService,
)
from vscs.application.generated_media.selection import (
    GeneratedMediaSelection,
    GeneratedMediaSelectionRepository,
    GeneratedMediaSelectionService,
)
from vscs.application.generated_media.technical_validation import (
    GeneratedMediaTechnicalRequirements,
    GeneratedMediaTechnicalValidationService,
    TechnicalMediaInspector,
)
from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.production_tasks.repository import ProductionTaskRepository
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)
from vscs.infrastructure.generated_media import (
    FFprobeGeneratedMediaInspector,
    LocalGeneratedMediaFileStore,
)

from .minimax_h3_functional_acceptance import (
    FFprobeMiniMaxH3MediaProbe,
    MiniMaxH3MediaObservation,
    MiniMaxH3MediaProbe,
)
from .provider_production_adoption_store import (
    ProviderProductionAdoptionRecord,
    ProviderProductionAdoptionStore,
)


class AcceptedProviderProductionReconciliationError(RuntimeError):
    """Raised when accepted legacy production cannot be reconciled safely."""


@dataclass(frozen=True, slots=True)
class AcceptedProviderProductionFinding:
    """One fail-closed reconciliation finding."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.message.strip():
            raise ValueError("accepted-provider reconciliation finding requires code and message")


@dataclass(frozen=True, slots=True)
class AcceptedProviderProductionEvidence:
    """Exact accepted provider-production evidence for one ProductionTask."""

    task_id: str
    shot_id: str
    execution_profile: str
    provider_id: str
    provider_profile_id: str
    provider_profile_fingerprint: str
    execution_adapter_id: str
    plan_id: str
    plan_fingerprint: str
    source_package_fingerprint: str
    final_path: Path
    final_frame_count: int
    frames_per_second: int
    approved_by: str
    notes: str
    orchestration_path: Path
    functional_acceptance_path: Path
    observation: MiniMaxH3MediaObservation


@dataclass(frozen=True, slots=True)
class AcceptedProviderProductionAssessment:
    """Read-only eligibility assessment for the compatibility bridge."""

    task: ProductionTask
    evidence: AcceptedProviderProductionEvidence | None
    findings: tuple[AcceptedProviderProductionFinding, ...]
    already_reconciled: bool = False

    @property
    def eligible(self) -> bool:
        return self.evidence is not None and not self.findings and not self.already_reconciled


@dataclass(frozen=True, slots=True)
class AcceptedProviderProductionReconciliationResult:
    """Authoritative state created or confirmed by one reconciliation request."""

    task: ProductionTask
    media: GeneratedMedia
    selection: GeneratedMediaSelection
    adoption: ProviderProductionAdoptionRecord
    already_reconciled: bool


class AcceptedProviderProductionReconciliationService:
    """Backfill accepted provider output without fabricating provider execution."""

    PHASE = "20.18.2.3.6.6b.5"
    PROVENANCE_SOURCE = "accepted-provider-functional-acceptance"
    H3_ROOT = Path(".vscs") / "h3_span_orchestration"

    def __init__(
        self,
        project_directory: Path,
        tasks: ProductionTaskRepository,
        media: GeneratedMediaPersistenceService,
        selections: GeneratedMediaSelectionRepository,
        *,
        adoption_store: ProviderProductionAdoptionStore | None = None,
        media_probe: MiniMaxH3MediaProbe | None = None,
        technical_inspector: TechnicalMediaInspector | None = None,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.tasks = tasks
        self.media = media
        self.selections = selections
        self.adoptions = adoption_store or ProviderProductionAdoptionStore(
            self.project_directory
        )
        self.media_probe = media_probe or FFprobeMiniMaxH3MediaProbe()
        self.technical_inspector = technical_inspector or FFprobeGeneratedMediaInspector(
            self.project_directory
        )

    def assess(self, task_id: str) -> AcceptedProviderProductionAssessment:
        task = self._require_task(task_id)
        findings: list[AcceptedProviderProductionFinding] = []
        findings.extend(self._task_findings(task))

        existing_selections = self.selections.list_for_task(task.task_id)
        if existing_selections:
            reconciled = self._reconciled_media(task)
            selected_ids = {item.selected_media_id for item in existing_selections}
            selection_matches_reconciled = (
                len(existing_selections) == 1
                and reconciled is not None
                and selected_ids == {reconciled.media_id}
            )
            if selection_matches_reconciled and self._accepted_adoption(task) is not None:
                return AcceptedProviderProductionAssessment(
                    task=task,
                    evidence=None,
                    findings=(),
                    already_reconciled=True,
                )
            if not selection_matches_reconciled:
                findings.append(
                    AcceptedProviderProductionFinding(
                        "existing-authoritative-selection",
                        "ProductionTask already has authoritative Generated Media selection; "
                        "accepted-provider reconciliation will not replace it silently.",
                    )
                )

        evidence, evidence_findings = self._load_evidence(task)
        findings.extend(evidence_findings)
        return AcceptedProviderProductionAssessment(
            task=task,
            evidence=evidence,
            findings=tuple(sorted(findings, key=lambda item: (item.code, item.message))),
        )

    def reconcile(self, task_id: str) -> AcceptedProviderProductionReconciliationResult:
        assessment = self.assess(task_id)
        if assessment.already_reconciled:
            media = self._reconciled_media(assessment.task)
            if media is None:
                raise AcceptedProviderProductionReconciliationError(
                    "Reconciled Generated Media disappeared after assessment"
                )
            selections = self.selections.list_for_task(assessment.task.task_id)
            adoption = self._accepted_adoption(assessment.task)
            if len(selections) != 1 or adoption is None:
                raise AcceptedProviderProductionReconciliationError(
                    "Existing accepted-provider reconciliation is incomplete"
                )
            return AcceptedProviderProductionReconciliationResult(
                task=assessment.task,
                media=media,
                selection=selections[0],
                adoption=adoption,
                already_reconciled=True,
            )
        if not assessment.eligible or assessment.evidence is None:
            detail = "; ".join(
                f"{finding.code}: {finding.message}" for finding in assessment.findings
            )
            raise AcceptedProviderProductionReconciliationError(
                detail or "Accepted provider production is not eligible for reconciliation"
            )

        task = assessment.task
        evidence = assessment.evidence
        media = self._ensure_media(task, evidence)
        media = self._ensure_technical_validation(media, evidence)
        media = self._ensure_human_approval(media, evidence)

        existing = self.selections.list_for_task(task.task_id)
        if existing:
            if len(existing) != 1 or existing[0].selected_media_id != media.media_id:
                raise AcceptedProviderProductionReconciliationError(
                    "Authoritative selection appeared during reconciliation; refusing replacement"
                )
            selection = existing[0]
        else:
            actor = self._review_actor(evidence.approved_by)
            selection = GeneratedMediaSelectionService(self.media, self.selections).select(
                media.media_id,
                selected_by=actor,
                reason=(
                    "Reconciled previously accepted provider production from passed "
                    f"functional-acceptance evidence under Phase {self.PHASE}."
                ),
            )

        adoption = self._ensure_adoption(task, evidence)
        return AcceptedProviderProductionReconciliationResult(
            task=task,
            media=self._require_media(media.media_id),
            selection=selection,
            adoption=adoption,
            already_reconciled=False,
        )

    def _task_findings(
        self, task: ProductionTask
    ) -> tuple[AcceptedProviderProductionFinding, ...]:
        findings: list[AcceptedProviderProductionFinding] = []
        if task.task_type is not ProductionTaskType.VIDEO_GENERATION:
            findings.append(
                AcceptedProviderProductionFinding(
                    "task-type-not-video-generation",
                    "Accepted provider reconciliation currently requires VIDEO_GENERATION.",
                )
            )
        if "video/shot" not in task.expected_outputs:
            findings.append(
                AcceptedProviderProductionFinding(
                    "video-shot-output-not-required",
                    "ProductionTask does not require the canonical video/shot output.",
                )
            )
        if not task.shot_id:
            findings.append(
                AcceptedProviderProductionFinding(
                    "task-shot-missing",
                    "ProductionTask must retain a governed Shot ID.",
                )
            )
        if task.state not in {
            ProductionTaskState.READY,
            ProductionTaskState.RUNNING,
            ProductionTaskState.COMPLETED,
        }:
            findings.append(
                AcceptedProviderProductionFinding(
                    "task-state-not-reconcilable",
                    "Accepted provider reconciliation requires READY, RUNNING or COMPLETED "
                    f"state, not {task.state.value}.",
                )
            )
        return tuple(findings)

    def _load_evidence(
        self, task: ProductionTask
    ) -> tuple[
        AcceptedProviderProductionEvidence | None,
        tuple[AcceptedProviderProductionFinding, ...],
    ]:
        root = self.project_directory / self.H3_ROOT / task.task_id
        acceptance_paths = tuple(sorted(root.glob("*/functional_acceptance.json")))
        if not acceptance_paths:
            return None, (
                AcceptedProviderProductionFinding(
                    "functional-acceptance-missing",
                    "No provider functional-acceptance evidence exists for this ProductionTask.",
                ),
            )

        passed: list[tuple[Path, dict[str, object], dict[str, object]]] = []
        failed_or_incomplete = False
        for path in acceptance_paths:
            try:
                payload = self._read_json(path)
                report = payload.get("report")
                if not isinstance(report, dict):
                    failed_or_incomplete = True
                    continue
                report_dict = {str(key): value for key, value in report.items()}
                if (
                    str(report_dict.get("task_id") or "") == task.task_id
                    and str(report_dict.get("shot_id") or "") == (task.shot_id or "")
                    and str(report_dict.get("state") or "").casefold() == "passed"
                    and report_dict.get("passed") is True
                    and report_dict.get("technical_passed") is True
                    and report_dict.get("visual_passed") is True
                    and report_dict.get("visual_observation_present") is True
                    and str(report_dict.get("approved_by") or "").strip()
                ):
                    passed.append((path, payload, report_dict))
                else:
                    failed_or_incomplete = True
            except AcceptedProviderProductionReconciliationError:
                failed_or_incomplete = True

        if len(passed) != 1:
            code = "functional-acceptance-ambiguous" if len(passed) > 1 else (
                "functional-acceptance-not-passed"
                if failed_or_incomplete
                else "functional-acceptance-missing"
            )
            message = (
                "Multiple passed functional-acceptance records exist for the same task."
                if len(passed) > 1
                else "Provider functional acceptance is missing, failed, or incomplete."
            )
            return None, (AcceptedProviderProductionFinding(code, message),)

        acceptance_path, _payload, report = passed[0]
        plan_root = acceptance_path.parent
        orchestration_path = plan_root / "orchestration.json"
        if not orchestration_path.is_file():
            return None, (
                AcceptedProviderProductionFinding(
                    "orchestration-evidence-missing",
                    "Passed functional acceptance has no sibling orchestration manifest.",
                ),
            )
        try:
            manifest = self._read_json(orchestration_path)
        except AcceptedProviderProductionReconciliationError as exc:
            return None, (
                AcceptedProviderProductionFinding(
                    "orchestration-evidence-invalid",
                    str(exc),
                ),
            )

        mismatch = self._authority_mismatch(task, report, manifest, plan_root)
        if mismatch is not None:
            return None, (mismatch,)

        final_path, path_finding = self._accepted_final_path(
            str(report.get("final_path") or ""),
            plan_root,
        )
        if path_finding is not None or final_path is None:
            return None, (path_finding or AcceptedProviderProductionFinding(
                "accepted-media-path-invalid",
                "Accepted provider media path is invalid.",
            ),)

        try:
            observation = self.media_probe.observe(final_path)
        except Exception as exc:
            return None, (
                AcceptedProviderProductionFinding(
                    "accepted-media-probe-failed",
                    f"Unable to re-probe accepted provider media: {exc}",
                ),
            )

        frame_count = int(str(report.get("final_frame_count") or "0"))
        frames_per_second = int(str(report.get("frames_per_second") or "0"))
        if observation.frame_count != frame_count:
            return None, (
                AcceptedProviderProductionFinding(
                    "accepted-media-frame-count-mismatch",
                    f"Accepted media now has {observation.frame_count} frames; "
                    f"functional acceptance recorded {frame_count}.",
                ),
            )
        if observation.frames_per_second != frames_per_second:
            return None, (
                AcceptedProviderProductionFinding(
                    "accepted-media-frame-rate-mismatch",
                    f"Accepted media now has {observation.frames_per_second} fps; "
                    f"functional acceptance recorded {frames_per_second} fps.",
                ),
            )

        readiness = self.adoptions.readiness_for(task.task_id, "production")
        if readiness is None:
            return None, (
                AcceptedProviderProductionFinding(
                    "provider-readiness-missing",
                    "No persisted provider readiness exists for accepted production.",
                ),
            )
        if readiness.shot_id != (task.shot_id or ""):
            return None, (
                AcceptedProviderProductionFinding(
                    "provider-readiness-shot-mismatch",
                    "Provider readiness belongs to a different Shot.",
                ),
            )

        return AcceptedProviderProductionEvidence(
            task_id=task.task_id,
            shot_id=task.shot_id or "",
            execution_profile=readiness.execution_profile,
            provider_id=str(manifest.get("provider") or ""),
            provider_profile_id=readiness.provider_profile_id,
            provider_profile_fingerprint=readiness.provider_profile_fingerprint,
            execution_adapter_id=readiness.execution_adapter_id,
            plan_id=str(manifest.get("plan_id") or ""),
            plan_fingerprint=str(manifest.get("plan_fingerprint") or ""),
            source_package_fingerprint=str(manifest.get("source_package_fingerprint") or ""),
            final_path=final_path,
            final_frame_count=frame_count,
            frames_per_second=frames_per_second,
            approved_by=str(report.get("approved_by") or "").strip(),
            notes=str(report.get("notes") or "").strip(),
            orchestration_path=orchestration_path,
            functional_acceptance_path=acceptance_path,
            observation=observation,
        ), ()

    def _authority_mismatch(
        self,
        task: ProductionTask,
        report: dict[str, object],
        manifest: dict[str, object],
        plan_root: Path,
    ) -> AcceptedProviderProductionFinding | None:
        expected = {
            "task_id": task.task_id,
            "shot_id": task.shot_id or "",
        }
        for key, value in expected.items():
            if str(report.get(key) or "") != value or str(manifest.get(key) or "") != value:
                return AcceptedProviderProductionFinding(
                    f"{key.replace('_', '-')}-mismatch",
                    f"Functional acceptance or orchestration manifest {key} does not "
                    "match current ProductionTask authority.",
                )
        plan_id = str(manifest.get("plan_id") or "")
        if not plan_id or plan_root.name != plan_id:
            return AcceptedProviderProductionFinding(
                "provider-plan-mismatch",
                "Orchestration plan identity does not match its governed evidence directory.",
            )
        report_path = str(report.get("final_path") or "").strip()
        manifest_path = str(manifest.get("final_path") or "").strip()
        if report_path != manifest_path:
            return AcceptedProviderProductionFinding(
                "accepted-media-path-mismatch",
                "Functional acceptance and orchestration manifest disagree on final media path.",
            )
        for key in ("final_frame_count", "frames_per_second"):
            if int(str(report.get(key) or "0")) != int(str(manifest.get(key) or "0")):
                return AcceptedProviderProductionFinding(
                    f"{key.replace('_', '-')}-mismatch",
                    f"Functional acceptance and orchestration manifest disagree on {key}.",
                )
        return None

    def _accepted_final_path(
        self,
        raw_path: str,
        plan_root: Path,
    ) -> tuple[Path | None, AcceptedProviderProductionFinding | None]:
        if not raw_path.strip():
            return None, AcceptedProviderProductionFinding(
                "accepted-media-path-missing",
                "Passed functional acceptance does not identify final media.",
            )
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_directory / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_relative_to(self.project_directory):
            return None, AcceptedProviderProductionFinding(
                "accepted-media-path-escape",
                "Accepted provider media path escapes the VSCS project.",
            )
        if not candidate.is_relative_to(plan_root.resolve(strict=False)):
            return None, AcceptedProviderProductionFinding(
                "accepted-media-outside-plan",
                "Accepted provider media is not contained by its governed H3 plan directory.",
            )
        if not candidate.is_file():
            return None, AcceptedProviderProductionFinding(
                "accepted-media-missing",
                f"Accepted provider media does not exist: {candidate}",
            )
        return candidate, None

    def _ensure_media(
        self,
        task: ProductionTask,
        evidence: AcceptedProviderProductionEvidence,
    ) -> GeneratedMedia:
        media_id = self._media_id(evidence)
        existing = self.media.get(media_id)
        if existing is not None:
            self._validate_existing_media(existing, task, evidence)
            return existing

        source_root = evidence.functional_acceptance_path.parent
        source_relative = evidence.final_path.relative_to(source_root).as_posix()
        suffix = PurePosixPath(source_relative).suffix.casefold() or ".mp4"
        destination = "/".join(
            (
                "generated_media",
                self._safe_segment(task.production_id),
                self._safe_segment(task.episode_id),
                self._safe_segment(task.task_id),
                f"{media_id}{suffix}",
            )
        )
        managed_file = LocalGeneratedMediaFileStore(
            source_root,
            self.project_directory,
        ).ingest(source_relative, destination)
        media = GeneratedMedia(
            media_id=media_id,
            kind=GeneratedMediaKind.VIDEO,
            scope=GeneratedMediaScope(
                production_id=task.production_id,
                episode_id=task.episode_id,
                production_task_id=task.task_id,
                scene_id=task.scene_id,
                shot_id=task.shot_id,
            ),
            provenance=GeneratedMediaProvenance(
                execution_id=f"APR-{self._digest(evidence.task_id + '|' + evidence.plan_id)[:20]}",
                provider_id=evidence.provider_id,
                provider_job_id=evidence.plan_id,
                render_request_id=evidence.plan_id,
                render_output_id=evidence.final_path.name,
                workflow_id=evidence.provider_profile_id,
                attributes=self._provenance_attributes(task, evidence),
            ),
            file=managed_file,
            revision=self._next_video_revision(task.task_id),
        )
        return self.media.register(media)

    def _ensure_technical_validation(
        self,
        media: GeneratedMedia,
        evidence: AcceptedProviderProductionEvidence,
    ) -> GeneratedMedia:
        status = dict(media.technical_metadata).get(
            "technical_validation.status", ""
        ).strip().casefold()
        if status == "passed":
            return media
        result = GeneratedMediaTechnicalValidationService(
            self.media,
            self.technical_inspector,
            validator_id=f"vscs:accepted-provider-reconciliation:{self.PHASE}",
        ).validate(
            media.media_id,
            GeneratedMediaTechnicalRequirements(
                allowed_extensions=("mp4",),
                expected_width=evidence.observation.width,
                expected_height=evidence.observation.height,
                expected_frame_rate=float(evidence.frames_per_second),
                require_video=True,
            ),
        )
        if not result.passed:
            raise AcceptedProviderProductionReconciliationError(
                "Managed accepted provider media failed standard Generated Media technical validation"
            )
        return result.media

    def _ensure_human_approval(
        self,
        media: GeneratedMedia,
        evidence: AcceptedProviderProductionEvidence,
    ) -> GeneratedMedia:
        current = self._require_media(media.media_id)
        if current.state is GeneratedMediaState.APPROVED:
            return current
        actor = self._review_actor(evidence.approved_by)
        review = GeneratedMediaReviewService(self.media)
        reason = (
            "Preserve existing human acceptance from passed provider functional-acceptance "
            f"evidence under Phase {self.PHASE}."
        )
        if current.state is GeneratedMediaState.GENERATED:
            review.submit_for_review(
                current.media_id,
                submitted_by=actor,
                reason=reason,
            )
            current = self._require_media(current.media_id)
        if current.state is GeneratedMediaState.UNDER_REVIEW:
            return review.approve(
                current.media_id,
                reviewer=actor,
                reason=reason,
            ).media
        raise AcceptedProviderProductionReconciliationError(
            "Accepted provider media is in a governance state that cannot be reconciled: "
            f"{current.state.value}"
        )

    def _ensure_adoption(
        self,
        task: ProductionTask,
        evidence: AcceptedProviderProductionEvidence,
    ) -> ProviderProductionAdoptionRecord:
        readiness = self.adoptions.readiness_for(task.task_id, evidence.execution_profile)
        if readiness is None:
            raise AcceptedProviderProductionReconciliationError(
                "Provider readiness disappeared during accepted-production reconciliation"
            )
        existing = self.adoptions.adoption_for(task.task_id, evidence.execution_profile)
        if existing is not None:
            if existing.shot_id != evidence.shot_id:
                raise AcceptedProviderProductionReconciliationError(
                    "Existing provider adoption belongs to a different Shot"
                )
            if existing.final_path and Path(existing.final_path).resolve(strict=False) != evidence.final_path:
                raise AcceptedProviderProductionReconciliationError(
                    "Existing provider adoption points at different final media"
                )
            if (
                existing.final_frame_count is not None
                and existing.final_frame_count != evidence.final_frame_count
            ):
                raise AcceptedProviderProductionReconciliationError(
                    "Existing provider adoption has a different final frame count"
                )
        else:
            self.adoptions.record_generated(
                readiness,
                final_path=str(evidence.final_path),
                final_frame_count=evidence.final_frame_count,
                state="functional_acceptance_passed",
            )
        return self.adoptions.mark_accepted(
            task.task_id,
            evidence.execution_profile,
            approved_by=evidence.approved_by,
            final_path=str(evidence.final_path),
            final_frame_count=evidence.final_frame_count,
        )

    def _reconciled_media(self, task: ProductionTask) -> GeneratedMedia | None:
        matches = tuple(
            item
            for item in self.media.list_for_task(task.task_id)
            if dict(item.provenance.attributes).get("reconciliation_phase") == self.PHASE
        )
        if len(matches) > 1:
            raise AcceptedProviderProductionReconciliationError(
                "Multiple reconciled Generated Media records exist for one ProductionTask"
            )
        return matches[0] if matches else None

    def _accepted_adoption(
        self, task: ProductionTask
    ) -> ProviderProductionAdoptionRecord | None:
        readiness = self.adoptions.readiness_for(task.task_id, "production")
        if readiness is None:
            return None
        adoption = self.adoptions.adoption_for(task.task_id, readiness.execution_profile)
        if adoption is None or adoption.state != "accepted":
            return None
        return adoption

    def _validate_existing_media(
        self,
        media: GeneratedMedia,
        task: ProductionTask,
        evidence: AcceptedProviderProductionEvidence,
    ) -> None:
        if (
            media.scope.production_id != task.production_id
            or media.scope.episode_id != task.episode_id
            or media.scope.production_task_id != task.task_id
            or media.scope.shot_id != task.shot_id
        ):
            raise AcceptedProviderProductionReconciliationError(
                "Deterministic reconciled Generated Media belongs to different authority"
            )
        attributes = dict(media.provenance.attributes)
        expected = {
            "authority_fingerprint": task.authority.fingerprint,
            "reconciliation_phase": self.PHASE,
            "provenance_source": self.PROVENANCE_SOURCE,
            "h3_plan_id": evidence.plan_id,
        }
        for key, value in expected.items():
            if attributes.get(key) != value:
                raise AcceptedProviderProductionReconciliationError(
                    f"Existing reconciled Generated Media provenance mismatch: {key}"
                )

    def _provenance_attributes(
        self,
        task: ProductionTask,
        evidence: AcceptedProviderProductionEvidence,
    ) -> tuple[tuple[str, str], ...]:
        return (
            ("authority_fingerprint", task.authority.fingerprint),
            ("provenance_source", self.PROVENANCE_SOURCE),
            ("reconciliation_phase", self.PHASE),
            ("provider_profile_id", evidence.provider_profile_id),
            ("provider_profile_fingerprint", evidence.provider_profile_fingerprint),
            ("execution_adapter_id", evidence.execution_adapter_id),
            ("source_package_fingerprint", evidence.source_package_fingerprint),
            ("h3_plan_id", evidence.plan_id),
            ("h3_plan_fingerprint", evidence.plan_fingerprint),
            (
                "orchestration_evidence",
                evidence.orchestration_path.relative_to(self.project_directory).as_posix(),
            ),
            (
                "functional_acceptance_evidence",
                evidence.functional_acceptance_path.relative_to(self.project_directory).as_posix(),
            ),
            (
                "original_final_path",
                evidence.final_path.relative_to(self.project_directory).as_posix(),
            ),
            ("accepted_frame_count", str(evidence.final_frame_count)),
            ("accepted_frames_per_second", str(evidence.frames_per_second)),
            ("functional_acceptance_state", "passed"),
            ("functional_acceptance_approved_by", evidence.approved_by),
        )

    def _next_video_revision(self, task_id: str) -> int:
        revisions = tuple(
            item.revision
            for item in self.media.list_for_task(task_id)
            if item.kind is GeneratedMediaKind.VIDEO
        )
        return max(revisions, default=0) + 1

    def _require_task(self, task_id: str) -> ProductionTask:
        normalized = task_id.strip()
        if not normalized:
            raise AcceptedProviderProductionReconciliationError("task_id cannot be blank")
        task = self.tasks.get(normalized)
        if task is None:
            raise AcceptedProviderProductionReconciliationError(
                f"ProductionTask not found: {normalized}"
            )
        return task

    def _require_media(self, media_id: str) -> GeneratedMedia:
        media = self.media.get(media_id)
        if media is None:
            raise AcceptedProviderProductionReconciliationError(
                f"Generated Media not found after reconciliation: {media_id}"
            )
        return media

    @staticmethod
    def _review_actor(approved_by: str) -> GeneratedMediaReviewActor:
        actor = approved_by.strip()
        if not actor:
            raise AcceptedProviderProductionReconciliationError(
                "Passed functional acceptance does not retain a human approver"
            )
        return GeneratedMediaReviewActor(
            actor_id=actor,
            display_name=actor,
            authority_source="provider-functional-acceptance",
        )

    @staticmethod
    def _read_json(path: Path) -> dict[str, object]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AcceptedProviderProductionReconciliationError(
                f"Cannot read reconciliation evidence {path}: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise AcceptedProviderProductionReconciliationError(
                f"Reconciliation evidence root must be an object: {path}"
            )
        return {str(key): value for key, value in raw.items()}

    @classmethod
    def _media_id(cls, evidence: AcceptedProviderProductionEvidence) -> str:
        payload = (
            f"{cls.PROVENANCE_SOURCE}|{evidence.task_id}|"
            f"{evidence.plan_id}|{evidence.final_path.name}"
        )
        return f"GM-APR-{cls._digest(payload)[:20]}"

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()

    @staticmethod
    def _safe_segment(value: str) -> str:
        normalized = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in value.strip()
        )
        if not normalized:
            raise AcceptedProviderProductionReconciliationError(
                "Generated Media destination contains an empty scope segment"
            )
        return normalized
