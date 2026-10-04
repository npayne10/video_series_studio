"""MiniMax H3 isolated-span execution planning for Phase 20.18.2.3.6.4c."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.production_execution.introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirementPlan,
)
from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.production_execution.provider_temporal_span_execution import (
    ProviderTemporalSpanExecutionCompiler,
)
from .governed_shot_boundaries import (
    GovernedShotBoundaryError,
    GovernedShotBoundaryResolver,
)

from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanReferenceSlot,
    SpanScopedProviderCompilationError,
    SpanScopedProviderInputCompiler,
    SpanScopedProviderInputPlan,
    SpanScopedProviderInputs,
)


class MiniMaxH3SpanAdapterError(RuntimeError):
    """Raised when governed span authority cannot become a safe H3 Ref2VA job plan."""


@dataclass(frozen=True, slots=True)
class MiniMaxH3SpanExecution:
    """One isolated MiniMax H3 Ref2VA provider job."""

    span_id: str
    sequence_number: int
    global_start_frame: int
    global_through_frame: int
    governed_frame_count: int
    provider_frame_count: int
    reference_slots: tuple[SpanReferenceSlot, ...]
    positive_prompt: str
    negative_prompt: str
    motion_prompt: str
    guide_source_kind: str
    guide_image_path: str
    guide_image_sha256: str
    guide_frame_idx: int
    source_span_input_id: str
    source_span_input_plan_fingerprint: str
    provider_id: str = "minimax-h3-ref2va"
    mode: str = "governed_isolated_span_ref2va"
    normalization_policy: str = "retain_first_governed_frames"
    reference_image_size: str = "match"

    def __post_init__(self) -> None:
        if not self.span_id.strip():
            raise MiniMaxH3SpanAdapterError("H3 span execution requires span_id")
        if self.sequence_number <= 0:
            raise MiniMaxH3SpanAdapterError("H3 span sequence must be positive")
        if self.global_start_frame < 0 or self.global_through_frame < self.global_start_frame:
            raise MiniMaxH3SpanAdapterError("H3 span has an invalid global frame interval")
        expected_governed = self.global_through_frame - self.global_start_frame + 1
        if self.governed_frame_count != expected_governed:
            raise MiniMaxH3SpanAdapterError(
                "H3 governed frame count does not match the span interval"
            )
        if self.provider_frame_count < self.governed_frame_count:
            raise MiniMaxH3SpanAdapterError(
                "H3 provider frame count cannot be smaller than governed frame count"
            )
        if (self.provider_frame_count + 1) % 8 != 0:
            raise MiniMaxH3SpanAdapterError(
                "H3 provider frame count must satisfy (frames + 1) % 8 == 0"
            )
        if self.guide_frame_idx != 0:
            raise MiniMaxH3SpanAdapterError("H3 isolated spans may use only a local frame-0 guide")
        expected_guide_kind = (
            "shot_opening_authority"
            if self.sequence_number == 1
            else "governed_introduction_keyframe"
        )
        if self.guide_source_kind != expected_guide_kind:
            raise MiniMaxH3SpanAdapterError("H3 guide source kind does not match span sequence")
        for field_name in (
            "positive_prompt",
            "negative_prompt",
            "motion_prompt",
            "guide_image_path",
            "guide_image_sha256",
            "source_span_input_id",
            "source_span_input_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise MiniMaxH3SpanAdapterError(f"H3 span execution requires {field_name}")
            object.__setattr__(self, field_name, value)
        checksum = self.guide_image_sha256.lower()
        if len(checksum) != 64 or any(
            character not in "0123456789abcdef" for character in checksum
        ):
            raise MiniMaxH3SpanAdapterError("H3 guide image SHA-256 is invalid")
        object.__setattr__(self, "guide_image_sha256", checksum)
        if self.normalization_policy != "retain_first_governed_frames":
            raise MiniMaxH3SpanAdapterError("Unsupported H3 span normalization policy")
        if self.reference_image_size != "match":
            raise MiniMaxH3SpanAdapterError(
                "H3 governed span adapter requires ref_image_size=match"
            )

    @property
    def provider_trim_frames(self) -> int:
        return self.provider_frame_count - self.governed_frame_count

    @property
    def job_id(self) -> str:
        return f"H3SPAN-{self.sequence_number:03d}-{_fingerprint(self._authority_payload())[:12].upper()}"

    @property
    def reference_slot_fingerprint(self) -> str:
        return _fingerprint([slot.to_dict() for slot in self.reference_slots])

    @property
    def prompt_fingerprint(self) -> str:
        return _fingerprint(
            {
                "positive_prompt": self.positive_prompt,
                "negative_prompt": self.negative_prompt,
                "motion_prompt": self.motion_prompt,
            }
        )

    def _authority_payload(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "mode": self.mode,
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "global_start_frame": self.global_start_frame,
            "global_through_frame": self.global_through_frame,
            "governed_frame_count": self.governed_frame_count,
            "provider_frame_count": self.provider_frame_count,
            "reference_slots": [slot.to_dict() for slot in self.reference_slots],
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "motion_prompt": self.motion_prompt,
            "guide_source_kind": self.guide_source_kind,
            "guide_image_path": self.guide_image_path,
            "guide_image_sha256": self.guide_image_sha256,
            "guide_frame_idx": self.guide_frame_idx,
            "source_span_input_id": self.source_span_input_id,
            "source_span_input_plan_fingerprint": self.source_span_input_plan_fingerprint,
            "normalization_policy": self.normalization_policy,
            "reference_image_size": self.reference_image_size,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["job_id"] = self.job_id
        payload["provider_trim_frames"] = self.provider_trim_frames
        payload["reference_slot_fingerprint"] = self.reference_slot_fingerprint
        payload["prompt_fingerprint"] = self.prompt_fingerprint
        payload["guide_semantics"] = "frame_state_anchor"
        payload["temporal_asset_gate"] = False
        return payload


@dataclass(frozen=True, slots=True)
class MiniMaxH3SpanExecutionPlan:
    """Complete isolated H3 execution topology for one editorial Shot."""

    shot_id: str
    source_package_fingerprint: str
    source_span_input_plan_fingerprint: str
    spans: tuple[MiniMaxH3SpanExecution, ...]
    provider_id: str = "minimax-h3-ref2va"
    mode: str = "governed_isolated_span_ref2va"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise MiniMaxH3SpanAdapterError("H3 span execution plan requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        for field_name in (
            "source_package_fingerprint",
            "source_span_input_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise MiniMaxH3SpanAdapterError(f"H3 span execution plan requires {field_name}")
            object.__setattr__(self, field_name, value)
        if not self.spans:
            raise MiniMaxH3SpanAdapterError("H3 span execution plan requires at least one span")
        expected_start = 0
        for index, span in enumerate(self.spans, start=1):
            if span.sequence_number != index:
                raise MiniMaxH3SpanAdapterError("H3 span execution sequence is not contiguous")
            if span.global_start_frame != expected_start:
                raise MiniMaxH3SpanAdapterError("H3 span executions contain a gap or overlap")
            if span.source_span_input_plan_fingerprint != self.source_span_input_plan_fingerprint:
                raise MiniMaxH3SpanAdapterError(
                    "H3 span execution source input fingerprint is inconsistent"
                )
            expected_start = span.global_through_frame + 1

    @property
    def governed_frame_count(self) -> int:
        return sum(span.governed_frame_count for span in self.spans)

    @property
    def plan_id(self) -> str:
        return f"H3SPANPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_id": self.provider_id,
            "mode": self.mode,
            "shot_id": self.shot_id,
            "source_package_fingerprint": self.source_package_fingerprint,
            "source_span_input_plan_fingerprint": self.source_span_input_plan_fingerprint,
            "governed_frame_count": self.governed_frame_count,
            "assembly_policy": "concatenate_normalized_span_outputs_in_sequence",
            "spans": [span.to_dict() for span in self.spans],
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload

    def require_source(
        self,
        compiled: CompiledProductionPackage,
        project_directory: Path,
    ) -> None:
        if compiled.package_fingerprint.strip().lower() != self.source_package_fingerprint:
            raise MiniMaxH3SpanAdapterError("H3 span execution source package fingerprint changed")
        expected = MiniMaxH3SpanAdapterCompiler(project_directory).compile(compiled)
        if expected.fingerprint != self.fingerprint:
            raise MiniMaxH3SpanAdapterError(
                "H3 span execution plan no longer matches governed source authority"
            )


class MiniMaxH3SpanAdapterCompiler:
    """Compile provider-specific isolated H3 jobs from 6.4a/6.4b authority."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)

    def compile_execution(
        self,
        compiled: CompiledProductionPackage,
        *,
        sequence_number: int,
    ) -> MiniMaxH3SpanExecution:
        """Compile one isolated H3 span without requiring future-span visual authority."""
        if sequence_number <= 0:
            raise MiniMaxH3SpanAdapterError("H3 span sequence must be positive")
        try:
            span_inputs = SpanScopedProviderInputCompiler().compile(compiled)
        except SpanScopedProviderCompilationError as exc:
            raise MiniMaxH3SpanAdapterError(
                f"H3 span adapter source authority is invalid: {exc}"
            ) from exc

        span_input = next(
            (
                candidate
                for candidate in span_inputs.spans
                if candidate.sequence_number == sequence_number
            ),
            None,
        )
        if span_input is None:
            raise MiniMaxH3SpanAdapterError(
                f"No governed H3 span exists for sequence {sequence_number}"
            )

        temporal_plan = ProviderTemporalSpanExecutionCompiler().compile(compiled)
        temporal = next(
            (
                candidate
                for candidate in temporal_plan.executions
                if candidate.span_id == span_input.span_id
            ),
            None,
        )
        if temporal is None:
            raise MiniMaxH3SpanAdapterError(
                f"No temporal execution authority exists for H3 span {span_input.span_id}"
            )

        if sequence_number == 1:
            guide_path, guide_sha256 = self._resolve_opening_authority(compiled)
            guide_kind = "shot_opening_authority"
        else:
            requirements = self._requirements(compiled)
            requirement = next(
                (
                    candidate
                    for candidate in requirements.requirements
                    if candidate.target_span_id == span_input.span_id
                ),
                None,
            )
            if requirement is None:
                raise MiniMaxH3SpanAdapterError(
                    f"No Introduction Keyframe requirement exists for H3 span {span_input.span_id}"
                )
            try:
                keyframe = self.keyframes.require_approved(requirement)
            except GovernedIntroductionKeyframeError as exc:
                raise MiniMaxH3SpanAdapterError(
                    f"H3 span {span_input.span_id} has no approved Introduction Keyframe: {exc}"
                ) from exc
            guide_path = self.keyframes.image_path(keyframe)
            guide_sha256 = keyframe.image_sha256
            guide_kind = "governed_introduction_keyframe"

        return self._execution_for_input(
            span_inputs,
            span_input,
            global_start_frame=temporal.global_start_frame,
            global_through_frame=temporal.global_through_frame,
            guide_path=guide_path,
            guide_sha256=guide_sha256,
            guide_kind=guide_kind,
        )

    def compile(self, compiled: CompiledProductionPackage) -> MiniMaxH3SpanExecutionPlan:
        try:
            span_inputs = SpanScopedProviderInputCompiler().compile(compiled)
        except SpanScopedProviderCompilationError as exc:
            raise MiniMaxH3SpanAdapterError(
                f"H3 span adapter source authority is invalid: {exc}"
            ) from exc

        requirements = self._requirements(compiled)
        requirement_by_target = {
            requirement.target_span_id: requirement for requirement in requirements.requirements
        }

        temporal_plan = ProviderTemporalSpanExecutionCompiler().compile(compiled)
        temporal_by_span = {execution.span_id: execution for execution in temporal_plan.executions}

        executions: list[MiniMaxH3SpanExecution] = []
        for span_input in span_inputs.spans:
            temporal = temporal_by_span.get(span_input.span_id)
            if temporal is None:
                raise MiniMaxH3SpanAdapterError(
                    f"No temporal execution authority exists for H3 span {span_input.span_id}"
                )
            if span_input.sequence_number == 1:
                guide_path, guide_sha256 = self._resolve_opening_authority(compiled)
                guide_kind = "shot_opening_authority"
            else:
                requirement = requirement_by_target.get(span_input.span_id)
                if requirement is None:
                    raise MiniMaxH3SpanAdapterError(
                        f"No Introduction Keyframe requirement exists for H3 span {span_input.span_id}"
                    )
                try:
                    keyframe = self.keyframes.require_approved(requirement)
                except GovernedIntroductionKeyframeError as exc:
                    raise MiniMaxH3SpanAdapterError(
                        f"H3 span {span_input.span_id} has no approved Introduction Keyframe: {exc}"
                    ) from exc
                guide_path = self.keyframes.image_path(keyframe)
                guide_sha256 = keyframe.image_sha256
                guide_kind = "governed_introduction_keyframe"

            execution = self._execution_for_input(
                span_inputs,
                span_input,
                global_start_frame=temporal.global_start_frame,
                global_through_frame=temporal.global_through_frame,
                guide_path=guide_path,
                guide_sha256=guide_sha256,
                guide_kind=guide_kind,
            )
            executions.append(execution)

        plan = MiniMaxH3SpanExecutionPlan(
            shot_id=compiled.shot_id,
            source_package_fingerprint=compiled.package_fingerprint,
            source_span_input_plan_fingerprint=span_inputs.fingerprint,
            spans=tuple(executions),
        )
        if plan.governed_frame_count != compiled.frame_count:
            raise MiniMaxH3SpanAdapterError(
                "H3 span execution frame total does not match governed Shot frame count"
            )
        return plan

    def _execution_for_input(
        self,
        plan: SpanScopedProviderInputPlan,
        span_input: SpanScopedProviderInputs,
        *,
        global_start_frame: int,
        global_through_frame: int,
        guide_path: Path,
        guide_sha256: str,
        guide_kind: str,
    ) -> MiniMaxH3SpanExecution:
        governed_frames = global_through_frame - global_start_frame + 1
        return MiniMaxH3SpanExecution(
            span_id=span_input.span_id,
            sequence_number=span_input.sequence_number,
            global_start_frame=global_start_frame,
            global_through_frame=global_through_frame,
            governed_frame_count=governed_frames,
            provider_frame_count=_h3_provider_frame_count(governed_frames),
            reference_slots=span_input.reference_slots,
            positive_prompt=span_input.positive_prompt,
            negative_prompt=span_input.negative_prompt,
            motion_prompt=span_input.motion_prompt,
            guide_source_kind=guide_kind,
            guide_image_path=str(guide_path),
            guide_image_sha256=guide_sha256,
            guide_frame_idx=0,
            source_span_input_id=span_input.input_id,
            source_span_input_plan_fingerprint=plan.fingerprint,
        )

    def _requirements(
        self,
        compiled: CompiledProductionPackage,
    ) -> IntroductionKeyframeRequirementPlan:
        raw = compiled.introduction_keyframe_requirements
        if not isinstance(raw, dict):
            raise MiniMaxH3SpanAdapterError(
                "H3 span adapter requires Introduction Keyframe requirements"
            )
        try:
            return IntroductionKeyframeRequirementPlan.from_dict(raw)
        except GovernedIntroductionKeyframeError as exc:
            raise MiniMaxH3SpanAdapterError(
                f"H3 Introduction Keyframe requirements are invalid: {exc}"
            ) from exc

    def _resolve_opening_authority(
        self,
        compiled: CompiledProductionPackage,
    ) -> tuple[Path, str]:
        value = str(compiled.previous_approved_final_frame or "").strip()
        if value:
            candidate = Path(value).expanduser()
            if not candidate.is_absolute():
                candidate = self.project_directory / candidate
            candidate = candidate.resolve(strict=False)
            if not candidate.is_file():
                raise MiniMaxH3SpanAdapterError(
                    f"H3 governed Shot opening image does not exist: {candidate}"
                )
            return candidate, _file_sha256(candidate)

        try:
            resolved = GovernedShotBoundaryResolver(
                self.project_directory
            ).resolve_previous_for(compiled)
        except GovernedShotBoundaryError as exc:
            raise MiniMaxH3SpanAdapterError(
                f"H3 first span requires governed Shot opening image authority: {exc}"
            ) from exc
        return resolved.image_path, resolved.image_sha256


def _h3_provider_frame_count(governed_frames: int) -> int:
    """Return the smallest H3-native frame count covering the governed interval."""
    if governed_frames <= 0:
        raise MiniMaxH3SpanAdapterError("H3 governed frame count must be positive")
    candidate = governed_frames
    remainder = (candidate + 1) % 8
    if remainder:
        candidate += 8 - remainder
    return candidate


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
