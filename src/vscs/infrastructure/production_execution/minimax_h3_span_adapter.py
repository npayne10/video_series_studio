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
from vscs.application.production_execution.provider_prompt_validation import (
    ProviderPromptValidationError,
)
from vscs.application.production_execution.provider_span_governance import (
    ProviderSpanGovernanceCompiler,
    ProviderSpanGovernanceError,
)
from vscs.application.production_execution.provider_temporal_span_execution import (
    ProviderTemporalSpanExecutionCompiler,
)
from vscs.application.production_execution.span_scoped_provider_inputs import (
    SpanReferenceSlot,
    SpanScopedProviderCompilationError,
    SpanScopedProviderInputCompiler,
    SpanScopedProviderInputPlan,
    SpanScopedProviderInputs,
)

from .governed_shot_boundaries import (
    GovernedShotBoundaryError,
    GovernedShotBoundaryResolver,
)
from .minimax_h3_prompt_policy import MiniMaxH3PromptPolicyCompiler
from .minimax_h3_prompt_validation import MiniMaxH3PromptMetadataValidator
from .provider_policy_profiles import (
    MINIMAX_H3_EXECUTION_ADAPTER_ID,
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
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
    prompt_validation_id: str
    prompt_validation_fingerprint: str
    prompt_validated_rules: tuple[str, ...]
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
        if self.provider_frame_count % 17 != 5:
            raise MiniMaxH3SpanAdapterError("H3 provider frame count must satisfy frames % 17 == 5")
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
            "prompt_validation_id",
            "prompt_validation_fingerprint",
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
        rules = tuple(str(rule).strip() for rule in self.prompt_validated_rules)
        if not rules or any(not rule for rule in rules):
            raise MiniMaxH3SpanAdapterError(
                "H3 span execution requires prompt validation rules"
            )
        if len(set(rules)) != len(rules):
            raise MiniMaxH3SpanAdapterError(
                "H3 span execution prompt validation rules cannot contain duplicates"
            )
        object.__setattr__(self, "prompt_validated_rules", rules)

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
            "provider_profile_id": self.provider_profile_id,
            "provider_profile_fingerprint": self.provider_profile_fingerprint,
            "execution_adapter_id": self.execution_adapter_id,
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
            "prompt_validation_id": self.prompt_validation_id,
            "prompt_validation_fingerprint": self.prompt_validation_fingerprint,
            "prompt_validated_rules": list(self.prompt_validated_rules),
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
    provider_profile_id: str
    provider_profile_fingerprint: str
    execution_adapter_id: str
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
            "provider_profile_id",
            "provider_profile_fingerprint",
            "execution_adapter_id",
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
            compiled,
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
                compiled,
                span_inputs,
                span_input,
                global_start_frame=temporal.global_start_frame,
                global_through_frame=temporal.global_through_frame,
                guide_path=guide_path,
                guide_sha256=guide_sha256,
                guide_kind=guide_kind,
            )
            executions.append(execution)

        policy_profile = default_provider_policy_profile_registry().require(
            MINIMAX_H3_POLICY_PROFILE_ID
        )
        if policy_profile.execution_adapter_id != MINIMAX_H3_EXECUTION_ADAPTER_ID:
            raise MiniMaxH3SpanAdapterError(
                "Installed H3 provider profile is bound to the wrong execution adapter"
            )
        plan = MiniMaxH3SpanExecutionPlan(
            shot_id=compiled.shot_id,
            source_package_fingerprint=compiled.package_fingerprint,
            source_span_input_plan_fingerprint=span_inputs.fingerprint,
            spans=tuple(executions),
            provider_profile_id=policy_profile.profile_id,
            provider_profile_fingerprint=policy_profile.fingerprint,
            execution_adapter_id=policy_profile.execution_adapter_id,
            provider_id=policy_profile.provider_id,
        )
        if plan.governed_frame_count != compiled.frame_count:
            raise MiniMaxH3SpanAdapterError(
                "H3 span execution frame total does not match governed Shot frame count"
            )
        return plan

    def _execution_for_input(
        self,
        compiled: CompiledProductionPackage,
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
        reference_slots, positive_prompt = self._project_reference_slots(
            compiled,
            span_input,
        )
        try:
            governance_plan = ProviderSpanGovernanceCompiler().compile(compiled)
        except ProviderSpanGovernanceError as exc:
            raise MiniMaxH3SpanAdapterError(
                f"H3 prompt governance source authority is invalid: {exc}"
            ) from exc
        governance = next(
            (item for item in governance_plan.spans if item.span_id == span_input.span_id),
            None,
        )
        if governance is None:
            raise MiniMaxH3SpanAdapterError(
                f"No provider-span governance exists for H3 span {span_input.span_id}"
            )
        prompt_policy = MiniMaxH3PromptPolicyCompiler().compile(
            governance=governance,
            reference_slots=reference_slots,
            base_positive_prompt=positive_prompt,
            base_negative_prompt=span_input.negative_prompt,
            base_motion_prompt=span_input.motion_prompt,
        )
        provider_frame_count = _h3_provider_frame_count(governed_frames)
        try:
            prompt_validation = MiniMaxH3PromptMetadataValidator().validate(
                governance=governance,
                policy=prompt_policy,
                reference_slots=reference_slots,
                provider_frame_count=provider_frame_count,
                guide_frame_idx=0,
                guide_semantics="frame_state_anchor",
                temporal_asset_gate=False,
            )
        except ProviderPromptValidationError as exc:
            raise MiniMaxH3SpanAdapterError(f"H3 prompt/metadata validation failed: {exc}") from exc

        positive_prompt = prompt_policy.positive_prompt
        negative_prompt = prompt_policy.negative_prompt
        motion_prompt = prompt_policy.motion_prompt

        return MiniMaxH3SpanExecution(
            span_id=span_input.span_id,
            sequence_number=span_input.sequence_number,
            global_start_frame=global_start_frame,
            global_through_frame=global_through_frame,
            governed_frame_count=governed_frames,
            provider_frame_count=provider_frame_count,
            reference_slots=reference_slots,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            motion_prompt=motion_prompt,
            guide_source_kind=guide_kind,
            guide_image_path=str(guide_path),
            guide_image_sha256=guide_sha256,
            guide_frame_idx=0,
            source_span_input_id=span_input.input_id,
            source_span_input_plan_fingerprint=plan.fingerprint,
            prompt_validation_id=prompt_validation.validation_id,
            prompt_validation_fingerprint=prompt_validation.fingerprint,
            prompt_validated_rules=prompt_validation.validated_rules,
        )

    def _project_reference_slots(
        self,
        compiled: CompiledProductionPackage,
        span_input: SpanScopedProviderInputs,
    ) -> tuple[tuple[SpanReferenceSlot, ...], str]:
        """Project governed references into MiniMax H3's finite picture-slot budget."""
        references = self._reference_records(compiled)
        frame_state_ids = self._frame_state_reference_ids(compiled)
        active_asset_ids = set(span_input.active_asset_ids)
        asset_kinds = self._asset_kinds(compiled)

        anchors = tuple(
            reference
            for reference in references
            if self._text(reference.get("reference_id")) in frame_state_ids
            and self._text(reference.get("role")) == "scene_composition_anchor"
            and self._text(reference.get("priority")).casefold() == "required"
            and reference.get("provider_ready") is True
            and self._active_contained_environments(reference, active_asset_ids)
        )
        if not anchors:
            if len(span_input.reference_slots) > 5:
                raise MiniMaxH3SpanAdapterError(
                    "H3 reference projection exceeds five slots without a required "
                    "scene-composition anchor"
                )
            return span_input.reference_slots, span_input.positive_prompt
        if len(anchors) != 1:
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection requires exactly one active required "
                "scene-composition anchor"
            )

        anchor_reference = anchors[0]
        contained = self._active_contained_environments(anchor_reference, active_asset_ids)
        if len(contained) != 1:
            raise MiniMaxH3SpanAdapterError(
                "H3 scene-composition anchor must resolve exactly one active environment/location"
            )
        anchor_asset_id = contained[0]

        character_slots = tuple(
            slot
            for slot in span_input.reference_slots
            if asset_kinds.get(slot.asset_id) == "character"
        )
        planet_slots = tuple(
            slot
            for slot in span_input.reference_slots
            if asset_kinds.get(slot.asset_id) == "planet"
        )
        required_other_slots = tuple(
            slot
            for slot in span_input.reference_slots
            if slot not in character_slots
            and slot not in planet_slots
            and self._reference_priority(references, slot.reference_id) == "required"
        )

        projected_raw: list[SpanReferenceSlot] = list(character_slots)
        projected_raw.append(
            SpanReferenceSlot(
                picture_index=len(projected_raw) + 1,
                picture_tag=f"<Picture {len(projected_raw) + 1}>",
                reference_id=self._required_reference_text(anchor_reference, "reference_id"),
                asset_id=anchor_asset_id,
                role=self._required_reference_text(anchor_reference, "role"),
                source_path=self._required_reference_text(anchor_reference, "source_path"),
                semantic_label=self._frame_state_semantic_label(
                    compiled,
                    anchor_asset_id,
                    anchor_reference,
                ),
            )
        )
        projected_raw.extend(planet_slots)
        projected_raw.extend(required_other_slots)

        deduplicated: list[SpanReferenceSlot] = []
        seen_reference_ids: set[str] = set()
        for slot in projected_raw:
            if slot.reference_id in seen_reference_ids:
                continue
            deduplicated.append(slot)
            seen_reference_ids.add(slot.reference_id)

        if len(deduplicated) > 5:
            raise MiniMaxH3SpanAdapterError(
                "H3 governed reference projection cannot fit the five-slot provider budget"
            )

        projected = tuple(
            SpanReferenceSlot(
                picture_index=index,
                picture_tag=f"<Picture {index}>",
                reference_id=slot.reference_id,
                asset_id=slot.asset_id,
                role=slot.role,
                source_path=slot.source_path,
                semantic_label=slot.semantic_label,
            )
            for index, slot in enumerate(deduplicated, start=1)
        )
        projected_ids = {slot.reference_id for slot in projected}
        original_ids = {slot.reference_id for slot in span_input.reference_slots}
        if not {slot.reference_id for slot in character_slots}.issubset(projected_ids):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection removed an active character identity reference"
            )
        if not {slot.reference_id for slot in planet_slots}.issubset(projected_ids):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection removed an active planet reference"
            )
        if projected_ids & set(self._future_reference_ids(compiled, span_input.sequence_number)):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection introduced future canonical authority"
            )
        if not projected_ids - original_ids == {
            self._required_reference_text(anchor_reference, "reference_id")
        }:
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection introduced ungoverned supporting references"
            )

        positive_prompt = self._replace_reference_declarations(
            span_input,
            projected,
        )
        return projected, positive_prompt

    def _replace_reference_declarations(
        self,
        span_input: SpanScopedProviderInputs,
        projected: tuple[SpanReferenceSlot, ...],
    ) -> str:
        original_declaration = " ".join(
            f"{slot.picture_tag} is the authoritative reference for {slot.semantic_label}."
            for slot in span_input.reference_slots
        )
        positive = span_input.positive_prompt.strip()
        if not positive.startswith(original_declaration):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection cannot identify governed picture declarations"
            )
        remainder = positive[len(original_declaration) :].strip()
        projected_declaration = " ".join(
            f"{slot.picture_tag} is the authoritative reference for {slot.semantic_label}."
            for slot in projected
        )
        return " ".join(value for value in (projected_declaration, remainder) if value).strip()

    def _frame_state_reference_ids(
        self,
        compiled: CompiledProductionPackage,
    ) -> set[str]:
        raw = compiled.timed_reference_activation
        if not isinstance(raw, dict):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection requires timed reference activation authority"
            )
        values = raw.get("frame_state_reference_ids", [])
        if not isinstance(values, list):
            raise MiniMaxH3SpanAdapterError("H3 frame-state reference IDs must be an array")
        return {self._text(value) for value in values if self._text(value)}

    def _future_reference_ids(
        self,
        compiled: CompiledProductionPackage,
        sequence_number: int,
    ) -> tuple[str, ...]:
        temporal = ProviderTemporalSpanExecutionCompiler().compile(compiled)
        execution = next(
            (item for item in temporal.executions if item.sequence_number == sequence_number),
            None,
        )
        if execution is None:
            raise MiniMaxH3SpanAdapterError(
                f"No temporal execution exists for H3 sequence {sequence_number}"
            )
        return execution.future_reference_ids

    def _asset_kinds(self, compiled: CompiledProductionPackage) -> dict[str, str]:
        raw = compiled.timed_asset_presence
        if not isinstance(raw, dict):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection requires Timed Asset Presence authority"
            )
        presences = raw.get("presences", [])
        if not isinstance(presences, list):
            raise MiniMaxH3SpanAdapterError("H3 Timed Asset Presence records must be an array")
        kinds: dict[str, str] = {}
        for presence in presences:
            if not isinstance(presence, dict):
                continue
            asset_id = self._text(presence.get("asset_id")).upper()
            asset_kind = self._text(presence.get("asset_kind")).casefold()
            if asset_id and asset_kind:
                kinds[asset_id] = asset_kind
        return kinds

    def _frame_state_semantic_label(
        self,
        compiled: CompiledProductionPackage,
        asset_id: str,
        reference: dict[str, object],
    ) -> str:
        for source in (compiled.production_authority, compiled.composition_plan):
            if not isinstance(source, dict):
                continue
            assets = source.get("assets", [])
            if not isinstance(assets, list):
                continue
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                if self._text(asset.get("asset_id")).upper() != asset_id:
                    continue
                for key in (
                    "name",
                    "label",
                    "display_name",
                    "canonical_name",
                    "location_name",
                    "title",
                ):
                    value = self._text(asset.get(key))
                    if value:
                        return value
                requirement = self._text(asset.get("requirement"))
                if requirement:
                    prefix = requirement.split(" is required", 1)[0].strip()
                    if prefix and prefix != requirement:
                        return prefix
        label = self._text(reference.get("label"))
        if label and not label.casefold().startswith("shot composition"):
            return label
        return f"{asset_id} scene composition"

    def _active_contained_environments(
        self,
        reference: dict[str, object],
        active_asset_ids: set[str],
    ) -> tuple[str, ...]:
        raw = reference.get("contains_environments", [])
        if not isinstance(raw, list):
            raise MiniMaxH3SpanAdapterError(
                "H3 scene-composition anchor contains_environments must be an array"
            )
        return tuple(
            asset_id for value in raw if (asset_id := self._text(value).upper()) in active_asset_ids
        )

    def _reference_priority(
        self,
        references: tuple[dict[str, object], ...],
        reference_id: str,
    ) -> str:
        for reference in references:
            if self._text(reference.get("reference_id")) == reference_id:
                return self._text(reference.get("priority")).casefold()
        return ""

    def _reference_records(
        self,
        compiled: CompiledProductionPackage,
    ) -> tuple[dict[str, object], ...]:
        raw_plan = compiled.reference_plan
        if not isinstance(raw_plan, dict):
            raise MiniMaxH3SpanAdapterError(
                "H3 reference projection requires a governed ReferencePlan"
            )
        raw = raw_plan.get("references", [])
        if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
            raise MiniMaxH3SpanAdapterError(
                "H3 governed ReferencePlan references must be an array of objects"
            )
        return tuple(dict(item) for item in raw)

    def _required_reference_text(
        self,
        reference: dict[str, object],
        key: str,
    ) -> str:
        value = self._text(reference.get(key))
        if not value:
            raise MiniMaxH3SpanAdapterError(f"H3 scene-composition anchor requires {key}")
        return value

    @staticmethod
    def _text(value: object) -> str:
        return value.strip() if isinstance(value, str) else ""

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
            resolved = GovernedShotBoundaryResolver(self.project_directory).resolve_previous_for(
                compiled
            )
        except GovernedShotBoundaryError as exc:
            raise MiniMaxH3SpanAdapterError(
                f"H3 first span requires governed Shot opening image authority: {exc}"
            ) from exc
        return resolved.image_path, resolved.image_sha256


def _h3_provider_frame_count(governed_frames: int) -> int:
    """Return the smallest H3-native 17k+5 frame count covering the governed interval."""
    if governed_frames <= 0:
        raise MiniMaxH3SpanAdapterError("H3 governed frame count must be positive")
    candidate = governed_frames
    while candidate % 17 != 5:
        candidate += 1
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
