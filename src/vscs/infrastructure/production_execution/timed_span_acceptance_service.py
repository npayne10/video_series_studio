"""Functional-acceptance service for governed timed internal spans."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.production_execution import (
    INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
    AutomatedIntroductionBoundaryStore,
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionIdentityCandidateStatus,
    IntroductionIdentityDecision,
    IntroductionIdentityReviewStore,
    IntroductionInjectionBoundaryStore,
    IntroductionInjectionCandidateStatus,
    IntroductionInjectionDecision,
    IntroductionInjectionReviewStore,
    IntroductionKeyframeRequirement,
    IntroductionKeyframeRequirementPlan,
    TimedSpanAcceptanceError,
    TimedSpanAcceptanceEvaluator,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    TimedSpanAcceptanceStore,
)
from vscs.application.timed_asset_presence import TimedAssetPresencePlan

from .timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
    TimedSpanAcceptancePackageError,
)
from .timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    GovernedSpanAssemblyRuntimeError,
)


class TimedSpanFunctionalAcceptanceServiceError(RuntimeError):
    """Raised when an operator acceptance action cannot proceed safely."""


class TimedSpanFunctionalAcceptanceService:
    """Coordinate keyframe approval, assembly evidence, and human visual QC."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)
        self.acceptance = TimedSpanAcceptanceStore(self.project_directory)
        self.boundaries = AutomatedIntroductionBoundaryStore(self.project_directory)
        self.identity_reviews = IntroductionIdentityReviewStore(self.project_directory)
        self.injection_boundaries = IntroductionInjectionBoundaryStore(self.project_directory)
        self.injection_reviews = IntroductionInjectionReviewStore(self.project_directory)
        self.evaluator = TimedSpanAcceptanceEvaluator(self.project_directory)

    def status(self, compiled_package_path: Path | None) -> TimedSpanAcceptanceStatus:
        if compiled_package_path is None or not Path(compiled_package_path).is_file():
            return TimedSpanAcceptanceStatus(
                shot_id="SHOT-UNKNOWN",
                state=TimedSpanAcceptanceState.PACKAGE_REQUIRED,
                span_count=0,
                boundary_count=0,
                requirement_count=0,
                approved_keyframe_count=0,
                qc_passed_count=0,
                assembly_present=False,
                message="Compile the current Production Package before timed-span acceptance.",
            )
        raw = self._read_package(compiled_package_path)
        return self.evaluator.evaluate(raw)

    def requirements(
        self,
        compiled_package_path: Path,
    ) -> tuple[IntroductionKeyframeRequirement, ...]:
        raw = self._read_package(compiled_package_path)
        requirements_raw = raw.get("introduction_keyframe_requirements")
        if not isinstance(requirements_raw, dict):
            return ()
        try:
            return IntroductionKeyframeRequirementPlan.from_dict(requirements_raw).requirements
        except GovernedIntroductionKeyframeError as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"Introduction Keyframe requirements are invalid: {exc}"
            ) from exc

    def identity_gate_required(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str | None = None,
    ) -> bool:
        raw = self._read_package(compiled_package_path)
        timed_raw = raw.get("timed_asset_presence")
        if not isinstance(timed_raw, dict):
            return False
        try:
            timed = TimedAssetPresencePlan.from_dict(timed_raw)
        except Exception:
            return False
        requirements = self.requirements(compiled_package_path)
        selected = tuple(
            requirement
            for requirement in requirements
            if requirement_id is None or requirement.requirement_id == requirement_id.strip()
        )
        return any(
            self.evaluator._requires_identity_gate(requirement, timed) for requirement in selected
        )

    def identity_candidate(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str | None = None,
    ) -> IntroductionIdentityCandidateStatus | None:
        requirements = self.requirements(compiled_package_path)
        selected = tuple(
            requirement
            for requirement in requirements
            if requirement_id is None or requirement.requirement_id == requirement_id.strip()
        )
        for requirement in selected:
            result = self.boundaries.latest_result_for_requirement(requirement.requirement_id)
            if result is None:
                continue
            request = self.boundaries.request_for_id(result.request_id)
            if request is None or request.requirement_id != requirement.requirement_id:
                continue
            review = self.identity_reviews.review_for_result(result.result_id)
            return IntroductionIdentityCandidateStatus(
                requirement_id=requirement.requirement_id,
                result_id=result.result_id,
                image_path=result.image_path,
                image_sha256=result.image_sha256,
                introduced_asset_ids=request.introduced_asset_ids,
                introduced_reference_ids=request.introduced_reference_ids,
                introduced_reference_paths=request.introduced_reference_paths,
                introduced_reference_sha256=request.introduced_reference_sha256,
                target_global_frame_index=request.target_global_frame_index,
                attempt_number=self.identity_reviews.rejected_count(requirement.requirement_id)
                + (
                    0
                    if review is not None
                    and review.decision is IntroductionIdentityDecision.REJECTED
                    else 1
                ),
                decision=None if review is None else review.decision,
            )
        return None

    def approve_identity_candidate(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str,
        approved_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        requirement = self._require_requirement(compiled_package_path, requirement_id)
        candidate = self.identity_candidate(
            compiled_package_path,
            requirement_id=requirement.requirement_id,
        )
        if candidate is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "No synthesized identity candidate exists for this requirement."
            )
        if not candidate.pending:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "The latest identity candidate has already been reviewed."
            )
        result = self.boundaries.latest_result_for_requirement(requirement.requirement_id)
        if result is None or result.result_id != candidate.result_id:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Identity candidate changed before approval."
            )
        request = self.boundaries.request_for_id(result.request_id)
        if request is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Identity candidate has no current synthesis request."
            )
        actor = approved_by.strip()
        if not actor:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Identity candidate approval requires a human reviewer."
            )
        image = self._project_file(Path(result.image_path), "identity candidate image")
        source = self._project_file(
            Path(result.source_boundary_image_path),
            "identity candidate source boundary",
        )
        if self._sha256(image) != result.image_sha256:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Identity candidate image checksum changed before approval."
            )
        if self._sha256(source) != result.source_boundary_image_sha256:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Identity candidate source-boundary checksum changed before approval."
            )
        for reference_id, raw_path, checksum in zip(
            request.introduced_reference_ids,
            request.introduced_reference_paths,
            request.introduced_reference_sha256,
            strict=True,
        ):
            reference = self._project_file(
                Path(raw_path),
                f"canonical identity reference {reference_id}",
            )
            if self._sha256(reference) != checksum:
                raise TimedSpanFunctionalAcceptanceServiceError(
                    f"Canonical identity reference checksum changed: {reference_id}"
                )

        record = self.keyframes.create_record(
            requirement,
            image_path=image.relative_to(self.project_directory).as_posix(),
            image_sha256=result.image_sha256,
            source_boundary_image_path=source.relative_to(self.project_directory).as_posix(),
            source_boundary_image_sha256=result.source_boundary_image_sha256,
            approved_by=actor,
            approved_at=datetime.now(UTC).isoformat(),
            acceptance_criteria=INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
            approval_mode="human",
        )
        try:
            self.keyframes.save(record, requirement)
            self.identity_reviews.record(
                requirement_id=requirement.requirement_id,
                result_id=result.result_id,
                image_sha256=result.image_sha256,
                decision=IntroductionIdentityDecision.APPROVED,
                reviewed_by=actor,
                notes=notes,
            )
            self.acceptance.invalidate_qc(
                requirement.requirement_id,
                reason="Introduction identity authority changed after human approval.",
            )
            self.acceptance.invalidate_assembly(
                requirement.shot_id,
                reason="Introduction identity authority changed after human approval.",
            )
        except Exception as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(str(exc)) from exc
        return self.status(compiled_package_path)

    def reject_identity_candidate(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str,
        rejected_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        requirement = self._require_requirement(compiled_package_path, requirement_id)
        candidate = self.identity_candidate(
            compiled_package_path,
            requirement_id=requirement.requirement_id,
        )
        if candidate is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "No synthesized identity candidate exists for this requirement."
            )
        if not candidate.pending:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "The latest identity candidate has already been reviewed."
            )
        actor = rejected_by.strip()
        if not actor:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Identity candidate rejection requires a human reviewer."
            )
        self.identity_reviews.record(
            requirement_id=requirement.requirement_id,
            result_id=candidate.result_id,
            image_sha256=candidate.image_sha256,
            decision=IntroductionIdentityDecision.REJECTED,
            reviewed_by=actor,
            notes=notes,
        )
        self.acceptance.invalidate_qc(
            requirement.requirement_id,
            reason="Introduction identity candidate was rejected.",
        )
        self.acceptance.invalidate_assembly(
            requirement.shot_id,
            reason="Introduction identity candidate was rejected.",
        )
        return self.status(compiled_package_path)

    def injection_candidate(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str | None = None,
    ) -> IntroductionInjectionCandidateStatus | None:
        requirements = self.requirements(compiled_package_path)
        selected = tuple(
            requirement
            for requirement in requirements
            if requirement_id is None or requirement.requirement_id == requirement_id.strip()
        )
        for requirement in selected:
            result = self.injection_boundaries.latest_result_for_requirement(
                requirement.requirement_id
            )
            if result is None:
                continue
            request = self.injection_boundaries.request_for_id(result.request_id)
            if request is None or request.requirement_id != requirement.requirement_id:
                continue
            if result.canonical_asset_id != request.canonical_asset.authority_id:
                raise TimedSpanFunctionalAcceptanceServiceError(
                    "Injection candidate canonical asset authority does not match its request."
                )
            if result.injection_region_id != request.injection_region.region_id:
                raise TimedSpanFunctionalAcceptanceServiceError(
                    "Injection candidate region authority does not match its request."
                )
            review = self.injection_reviews.review_for_result(result.result_id)
            return IntroductionInjectionCandidateStatus(
                requirement_id=requirement.requirement_id,
                request_id=request.request_id,
                result_id=result.result_id,
                source_boundary_image_path=request.source_boundary_image_path,
                source_boundary_image_sha256=request.source_boundary_image_sha256,
                image_path=result.image_path,
                image_sha256=result.image_sha256,
                canonical_asset=request.canonical_asset,
                injection_region=request.injection_region,
                target_global_frame_index=request.target_global_frame_index,
                attempt_number=result.attempt_number,
                decision=None if review is None else review.decision,
            )
        return None

    def approve_injection_candidate(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str,
        approved_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        requirement = self._require_requirement(compiled_package_path, requirement_id)
        candidate = self.injection_candidate(
            compiled_package_path,
            requirement_id=requirement.requirement_id,
        )
        if candidate is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "No identity-locked injection candidate exists for this requirement."
            )
        if not candidate.pending:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "The latest injection candidate has already been reviewed."
            )
        result = self.injection_boundaries.latest_result_for_requirement(requirement.requirement_id)
        if result is None or result.result_id != candidate.result_id:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Injection candidate changed before approval."
            )
        request = self.injection_boundaries.request_for_id(result.request_id)
        if request is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Injection candidate has no immutable injection request."
            )
        actor = approved_by.strip()
        if not actor:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Injection candidate approval requires a human reviewer."
            )

        image = self._project_file(Path(result.image_path), "injection candidate image")
        source = self._project_file(
            Path(request.source_boundary_image_path),
            "injection candidate source boundary",
        )
        if self._sha256(image) != result.image_sha256:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Injection candidate image checksum changed before approval."
            )
        if self._sha256(source) != request.source_boundary_image_sha256:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Injection candidate source-boundary checksum changed before approval."
            )
        for reference_id, raw_path, checksum in zip(
            request.canonical_asset.reference_ids,
            request.canonical_asset.reference_paths,
            request.canonical_asset.reference_sha256,
            strict=True,
        ):
            reference = self._project_file(
                Path(raw_path),
                f"canonical injection reference {reference_id}",
            )
            if self._sha256(reference) != checksum:
                raise TimedSpanFunctionalAcceptanceServiceError(
                    f"Canonical injection reference checksum changed: {reference_id}"
                )

        record = self.keyframes.create_record(
            requirement,
            image_path=image.relative_to(self.project_directory).as_posix(),
            image_sha256=result.image_sha256,
            source_boundary_image_path=source.relative_to(self.project_directory).as_posix(),
            source_boundary_image_sha256=request.source_boundary_image_sha256,
            approved_by=actor,
            approved_at=datetime.now(UTC).isoformat(),
            acceptance_criteria=INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
            approval_mode="human",
        )
        try:
            self.keyframes.save(record, requirement)
            self.injection_reviews.record(
                requirement_id=requirement.requirement_id,
                result_id=result.result_id,
                image_sha256=result.image_sha256,
                decision=IntroductionInjectionDecision.APPROVED,
                reviewed_by=actor,
                notes=notes,
            )
            self.acceptance.invalidate_qc(
                requirement.requirement_id,
                reason="Identity-locked injection authority changed after human approval.",
            )
            self.acceptance.invalidate_assembly(
                requirement.shot_id,
                reason="Identity-locked injection authority changed after human approval.",
            )
        except Exception as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(str(exc)) from exc
        return self.status(compiled_package_path)

    def reject_injection_candidate(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str,
        rejected_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        requirement = self._require_requirement(compiled_package_path, requirement_id)
        candidate = self.injection_candidate(
            compiled_package_path,
            requirement_id=requirement.requirement_id,
        )
        if candidate is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "No identity-locked injection candidate exists for this requirement."
            )
        if not candidate.pending:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "The latest injection candidate has already been reviewed."
            )
        actor = rejected_by.strip()
        if not actor:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Injection candidate rejection requires a human reviewer."
            )
        self.injection_reviews.record(
            requirement_id=requirement.requirement_id,
            result_id=candidate.result_id,
            image_sha256=candidate.image_sha256,
            decision=IntroductionInjectionDecision.REJECTED,
            reviewed_by=actor,
            notes=notes,
        )
        self.acceptance.invalidate_qc(
            requirement.requirement_id,
            reason="Identity-locked injection candidate was rejected.",
        )
        self.acceptance.invalidate_assembly(
            requirement.shot_id,
            reason="Identity-locked injection candidate was rejected.",
        )
        return self.status(compiled_package_path)

    def approve_introduction_keyframe(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str,
        image_path: Path,
        source_boundary_image_path: Path,
        approved_by: str,
        approved_at: str,
    ) -> TimedSpanAcceptanceStatus:
        requirement = self._require_requirement(compiled_package_path, requirement_id)
        image = self._project_file(image_path, "Introduction Keyframe")
        source = self._project_file(source_boundary_image_path, "source boundary image")
        actor = approved_by.strip()
        timestamp = approved_at.strip()
        if not actor or not timestamp:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Introduction Keyframe approval requires approved_by and approved_at"
            )
        record = self.keyframes.create_record(
            requirement,
            image_path=image.relative_to(self.project_directory).as_posix(),
            image_sha256=self._sha256(image),
            source_boundary_image_path=source.relative_to(self.project_directory).as_posix(),
            source_boundary_image_sha256=self._sha256(source),
            approved_by=actor,
            approved_at=timestamp,
        )
        try:
            self.keyframes.save(record, requirement)
        except GovernedIntroductionKeyframeError as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(str(exc)) from exc
        return self.status(compiled_package_path)

    def build_span_packages(
        self,
        compiled_package_path: Path,
    ) -> tuple[Path, ...]:
        try:
            package_set = LTX25TimedSpanAcceptancePackageBuilder(self.project_directory).build(
                compiled_package_path
            )
        except TimedSpanAcceptancePackageError as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(str(exc)) from exc
        return package_set.package_paths

    def assemble_outputs(
        self,
        compiled_package_path: Path,
        *,
        span_paths: tuple[Path, ...],
        output_path: Path,
    ) -> TimedSpanAcceptanceStatus:
        raw = self._read_package(compiled_package_path)
        try:
            GovernedSpanAssemblyRuntime(self.project_directory).assemble(
                raw,
                tuple(Path(path) for path in span_paths),
                Path(output_path),
            )
        except GovernedSpanAssemblyRuntimeError as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(str(exc)) from exc
        return self.status(compiled_package_path)

    def record_visual_qc(
        self,
        compiled_package_path: Path,
        *,
        requirement_id: str,
        absent_before_boundary: bool,
        present_from_target_frame: bool,
        source_continuity_preserved: bool,
        no_unapproved_assets: bool,
        approved_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        requirement = self._require_requirement(compiled_package_path, requirement_id)
        try:
            self.keyframes.require_approved(requirement)
        except GovernedIntroductionKeyframeError as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"Visual QC requires the current Governed Introduction Keyframe first: {exc}"
            ) from exc

        current = self.status(compiled_package_path)
        if not current.assembly_present:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Visual QC requires verified normalized span assembly evidence first."
            )

        try:
            record = self.evaluator.make_qc_record(
                requirement,
                absent_before_boundary=absent_before_boundary,
                present_from_target_frame=present_from_target_frame,
                source_continuity_preserved=source_continuity_preserved,
                no_unapproved_assets=no_unapproved_assets,
                approved_by=approved_by,
                notes=notes,
            )
            self.acceptance.save_qc(record)
        except TimedSpanAcceptanceError as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(str(exc)) from exc
        return self.status(compiled_package_path)

    def _require_requirement(
        self,
        compiled_package_path: Path,
        requirement_id: str,
    ) -> IntroductionKeyframeRequirement:
        normalized = requirement_id.strip()
        if not normalized:
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Select an Introduction Keyframe requirement"
            )
        requirements = self.requirements(compiled_package_path)
        requirement = next(
            (item for item in requirements if item.requirement_id == normalized),
            None,
        )
        if requirement is None:
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"Introduction Keyframe requirement is not current: {normalized}"
            )
        return requirement

    def _read_package(self, path: Path) -> dict[str, Any]:
        candidate = Path(path).expanduser().resolve(strict=False)
        if not candidate.is_file():
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"Compiled Production Package does not exist: {candidate}"
            )
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"Cannot read compiled Production Package: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise TimedSpanFunctionalAcceptanceServiceError(
                "Compiled Production Package root must be an object"
            )
        return raw

    def _project_file(self, value: Path, label: str) -> Path:
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_directory / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_relative_to(self.project_directory):
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"{label} must remain inside the VSCS project"
            )
        if not candidate.is_file():
            raise TimedSpanFunctionalAcceptanceServiceError(f"{label} does not exist: {candidate}")
        return candidate

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
