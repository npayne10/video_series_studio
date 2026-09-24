"""Functional-acceptance service for governed timed internal spans."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vscs.application.production_execution import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirement,
    IntroductionKeyframeRequirementPlan,
    TimedSpanAcceptanceError,
    TimedSpanAcceptanceEvaluator,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    TimedSpanAcceptanceStore,
)
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
            package_set = LTX25TimedSpanAcceptancePackageBuilder(
                self.project_directory
            ).build(compiled_package_path)
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
                "Visual QC requires the current Governed Introduction Keyframe first: "
                f"{exc}"
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
            raise TimedSpanFunctionalAcceptanceServiceError(
                f"{label} does not exist: {candidate}"
            )
        return candidate

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
