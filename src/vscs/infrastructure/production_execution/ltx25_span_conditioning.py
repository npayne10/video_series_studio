"""LTX-2.5 per-span conditioning authority for Phase 20.18.2.3.4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirementPlan,
)
from vscs.application.production_execution.package_compilation import (
    CompiledProductionPackage,
)
from vscs.application.production_execution.timed_reference_activation import (
    TimedCanonicalReferenceActivationError,
    TimedCanonicalReferenceActivationPlan,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)


class LTX25SpanConditioningError(RuntimeError):
    """Raised when LTX-2.5 span conditioning cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class LTX25SpanConditioning:
    """One exact LTX-2.5 I2V conditioning contract for a governed internal span."""

    span_id: str
    sequence_number: int
    global_start_frame: int
    global_through_frame: int
    governed_frame_count: int
    provider_frame_count: int
    conditioning_source_kind: str
    conditioning_frame_global_index: int
    conditioning_frame_is_emitted: bool
    preceding_boundary_global_frame_index: int | None
    preceding_boundary_frame_reemitted: bool
    active_reference_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    direct_provider_reference_ids: tuple[str, ...]
    introduction_requirement_id: str | None = None
    introduction_keyframe_id: str | None = None
    introduction_keyframe_path: str | None = None
    introduction_keyframe_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.span_id.strip():
            raise LTX25SpanConditioningError("LTX-2.5 span conditioning requires span_id")
        if self.sequence_number <= 0:
            raise LTX25SpanConditioningError("LTX-2.5 span sequence must be positive")
        if self.global_start_frame < 0 or self.global_through_frame < self.global_start_frame:
            raise LTX25SpanConditioningError("LTX-2.5 span global frame interval is invalid")
        expected_governed = self.global_through_frame - self.global_start_frame + 1
        if self.governed_frame_count != expected_governed:
            raise LTX25SpanConditioningError(
                "LTX-2.5 governed frame count does not match span interval"
            )
        if self.provider_frame_count < self.governed_frame_count:
            raise LTX25SpanConditioningError(
                "LTX-2.5 provider frame count cannot be smaller than governed frame count"
            )
        if (self.provider_frame_count - 1) % 8 != 0:
            raise LTX25SpanConditioningError(
                "LTX-2.5 provider frame count must satisfy (frames - 1) % 8 == 0"
            )
        if self.conditioning_frame_global_index != self.global_start_frame:
            raise LTX25SpanConditioningError(
                "Conditioning keyframe must represent the first emitted global frame of its span"
            )
        if self.conditioning_frame_is_emitted is not True:
            raise LTX25SpanConditioningError(
                "The governed conditioning keyframe must count as the first emitted span frame"
            )
        if self.preceding_boundary_frame_reemitted is not False:
            raise LTX25SpanConditioningError(
                "The preceding boundary frame must not be duplicated into the target span"
            )

        for field_name in (
            "active_reference_ids",
            "introduced_reference_ids",
            "direct_provider_reference_ids",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise LTX25SpanConditioningError(f"{field_name} cannot contain blank values")
            if len(set(values)) != len(values):
                raise LTX25SpanConditioningError(f"{field_name} cannot contain duplicates")
            object.__setattr__(self, field_name, values)

        if self.direct_provider_reference_ids:
            raise LTX25SpanConditioningError(
                "Phase 20.18.2.3.4 LTX-2.5 Candidate C must not inject direct multi-reference "
                "conditioning; identity changes are baked into governed keyframes"
            )
        if not set(self.introduced_reference_ids).issubset(set(self.active_reference_ids)):
            raise LTX25SpanConditioningError(
                "Introduced references must be active in the conditioned span"
            )

        if self.sequence_number == 1:
            if self.conditioning_source_kind != "shot_opening_authority":
                raise LTX25SpanConditioningError(
                    "First internal span must use existing governed Shot opening authority"
                )
            if self.preceding_boundary_global_frame_index is not None:
                raise LTX25SpanConditioningError(
                    "First internal span cannot have an internal preceding boundary"
                )
            if any(
                value is not None
                for value in (
                    self.introduction_requirement_id,
                    self.introduction_keyframe_id,
                    self.introduction_keyframe_path,
                    self.introduction_keyframe_sha256,
                )
            ):
                raise LTX25SpanConditioningError(
                    "First internal span cannot bind an Introduction Keyframe"
                )
        else:
            if self.conditioning_source_kind != "governed_introduction_keyframe":
                raise LTX25SpanConditioningError(
                    "Non-initial internal spans require a governed Introduction Keyframe"
                )
            if self.preceding_boundary_global_frame_index != self.global_start_frame - 1:
                raise LTX25SpanConditioningError(
                    "Non-initial span must condition immediately after its preceding boundary"
                )
            if not all(
                (
                    self.introduction_requirement_id,
                    self.introduction_keyframe_id,
                    self.introduction_keyframe_path,
                    self.introduction_keyframe_sha256,
                )
            ):
                raise LTX25SpanConditioningError(
                    "Non-initial span has incomplete governed Introduction Keyframe binding"
                )

    @property
    def provider_trim_frames(self) -> int:
        return self.provider_frame_count - self.governed_frame_count

    def to_dict(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "global_start_frame": self.global_start_frame,
            "global_through_frame": self.global_through_frame,
            "governed_frame_count": self.governed_frame_count,
            "provider_frame_count": self.provider_frame_count,
            "provider_trim_frames": self.provider_trim_frames,
            "conditioning_source_kind": self.conditioning_source_kind,
            "conditioning_frame_global_index": self.conditioning_frame_global_index,
            "conditioning_frame_is_emitted": self.conditioning_frame_is_emitted,
            "preceding_boundary_global_frame_index": self.preceding_boundary_global_frame_index,
            "preceding_boundary_frame_reemitted": self.preceding_boundary_frame_reemitted,
            "active_reference_ids": list(self.active_reference_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "direct_provider_reference_ids": list(self.direct_provider_reference_ids),
            "introduction_requirement_id": self.introduction_requirement_id,
            "introduction_keyframe_id": self.introduction_keyframe_id,
            "introduction_keyframe_path": self.introduction_keyframe_path,
            "introduction_keyframe_sha256": self.introduction_keyframe_sha256,
            "reference_conditioning_mode": "baked_into_governed_keyframe",
            "combined_identity_video_reference": False,
        }


@dataclass(frozen=True, slots=True)
class LTX25SpanProviderConditioningPlan:
    """Complete provider-conditioning topology for one multi-span editorial Shot."""

    shot_id: str
    source_package_fingerprint: str
    source_span_plan_fingerprint: str
    source_activation_plan_fingerprint: str
    source_requirement_plan_fingerprint: str
    spans: tuple[LTX25SpanConditioning, ...]
    provider_id: str = "ltx-2.5"
    mode: str = "governed_multi_span_keyframe_i2v"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise LTX25SpanConditioningError("Provider-conditioning plan requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        for field_name in (
            "source_package_fingerprint",
            "source_span_plan_fingerprint",
            "source_activation_plan_fingerprint",
            "source_requirement_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise LTX25SpanConditioningError(
                    f"Provider-conditioning plan requires {field_name}"
                )
            object.__setattr__(self, field_name, value)
        if not self.spans:
            raise LTX25SpanConditioningError(
                "Provider-conditioning plan requires at least one span"
            )
        expected_start = 0
        for index, span in enumerate(self.spans, start=1):
            if span.sequence_number != index:
                raise LTX25SpanConditioningError(
                    "Provider-conditioning span sequence is not contiguous"
                )
            if span.global_start_frame != expected_start:
                raise LTX25SpanConditioningError(
                    "Provider-conditioning spans contain a gap or overlap"
                )
            expected_start = span.global_through_frame + 1

    @property
    def governed_frame_count(self) -> int:
        return sum(span.governed_frame_count for span in self.spans)

    @property
    def plan_id(self) -> str:
        return f"LTX25-SPANPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

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
            "source_span_plan_fingerprint": self.source_span_plan_fingerprint,
            "source_activation_plan_fingerprint": self.source_activation_plan_fingerprint,
            "source_requirement_plan_fingerprint": self.source_requirement_plan_fingerprint,
            "governed_frame_count": self.governed_frame_count,
            "assembly_policy": "concatenate_normalized_span_outputs_in_sequence",
            "spans": [span.to_dict() for span in self.spans],
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload


class LTX25SpanProviderConditioningCompiler:
    """Bind governed Introduction Keyframes into provider-safe LTX-2.5 span contracts."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)

    def compile(self, compiled: CompiledProductionPackage) -> LTX25SpanProviderConditioningPlan:
        timed_raw = compiled.timed_asset_presence
        spans_raw = compiled.internal_render_spans
        activation_raw = compiled.timed_reference_activation
        requirements_raw = compiled.introduction_keyframe_requirements
        if not isinstance(timed_raw, dict):
            raise LTX25SpanConditioningError(
                "LTX-2.5 span conditioning requires Timed Asset Presence authority"
            )
        if not isinstance(spans_raw, dict):
            raise LTX25SpanConditioningError(
                "LTX-2.5 span conditioning requires Governed Internal Render Spans"
            )
        if not isinstance(activation_raw, dict):
            raise LTX25SpanConditioningError(
                "LTX-2.5 span conditioning requires Timed Canonical Reference Activation"
            )
        if not isinstance(requirements_raw, dict):
            raise LTX25SpanConditioningError(
                "LTX-2.5 span conditioning requires Introduction Keyframe requirements"
            )

        try:
            timed = TimedAssetPresencePlan.from_dict(timed_raw)
            spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
            activation = TimedCanonicalReferenceActivationPlan.from_dict(activation_raw)
            requirements = IntroductionKeyframeRequirementPlan.from_dict(requirements_raw)
            activation.require_sources(timed, spans, compiled.reference_plan)
            requirements.require_sources(spans, activation)
        except (
            TimedAssetPresenceError,
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
            GovernedIntroductionKeyframeError,
        ) as exc:
            raise LTX25SpanConditioningError(
                f"LTX-2.5 span conditioning source authority is invalid: {exc}"
            ) from exc

        activation_by_span = {item.span_id: item for item in activation.activations}
        requirement_by_target = {item.target_span_id: item for item in requirements.requirements}
        conditioned: list[LTX25SpanConditioning] = []
        for span in spans.spans:
            active = activation_by_span.get(span.span_id)
            if active is None:
                raise LTX25SpanConditioningError(
                    f"No timed reference activation exists for internal span {span.span_id}"
                )
            provider_frames = _provider_frame_count(span.frame_count)
            if span.sequence_number == 1:
                conditioned.append(
                    LTX25SpanConditioning(
                        span_id=span.span_id,
                        sequence_number=span.sequence_number,
                        global_start_frame=span.start_frame,
                        global_through_frame=span.through_frame,
                        governed_frame_count=span.frame_count,
                        provider_frame_count=provider_frames,
                        conditioning_source_kind="shot_opening_authority",
                        conditioning_frame_global_index=span.start_frame,
                        conditioning_frame_is_emitted=True,
                        preceding_boundary_global_frame_index=None,
                        preceding_boundary_frame_reemitted=False,
                        active_reference_ids=active.active_reference_ids,
                        introduced_reference_ids=active.introduced_reference_ids,
                        direct_provider_reference_ids=(),
                    )
                )
                continue

            requirement = requirement_by_target.get(span.span_id)
            if requirement is None:
                raise LTX25SpanConditioningError(
                    f"No Introduction Keyframe requirement exists for target span {span.span_id}"
                )
            try:
                keyframe = self.keyframes.require_approved(requirement)
            except GovernedIntroductionKeyframeError as exc:
                raise LTX25SpanConditioningError(
                    f"Target span {span.span_id} has no usable governed Introduction Keyframe: {exc}"
                ) from exc
            conditioned.append(
                LTX25SpanConditioning(
                    span_id=span.span_id,
                    sequence_number=span.sequence_number,
                    global_start_frame=span.start_frame,
                    global_through_frame=span.through_frame,
                    governed_frame_count=span.frame_count,
                    provider_frame_count=provider_frames,
                    conditioning_source_kind="governed_introduction_keyframe",
                    conditioning_frame_global_index=span.start_frame,
                    conditioning_frame_is_emitted=True,
                    preceding_boundary_global_frame_index=span.start_frame - 1,
                    preceding_boundary_frame_reemitted=False,
                    active_reference_ids=active.active_reference_ids,
                    introduced_reference_ids=active.introduced_reference_ids,
                    direct_provider_reference_ids=(),
                    introduction_requirement_id=requirement.requirement_id,
                    introduction_keyframe_id=keyframe.keyframe_id,
                    introduction_keyframe_path=str(self.keyframes.image_path(keyframe)),
                    introduction_keyframe_sha256=keyframe.image_sha256,
                )
            )

        plan = LTX25SpanProviderConditioningPlan(
            shot_id=compiled.shot_id,
            source_package_fingerprint=compiled.package_fingerprint,
            source_span_plan_fingerprint=spans.fingerprint,
            source_activation_plan_fingerprint=activation.fingerprint,
            source_requirement_plan_fingerprint=requirements.fingerprint,
            spans=tuple(conditioned),
        )
        if plan.governed_frame_count != compiled.frame_count:
            raise LTX25SpanConditioningError(
                "Provider-conditioned span frame total does not match governed Shot frame count"
            )
        return plan


def _provider_frame_count(governed_frames: int) -> int:
    if governed_frames <= 0:
        raise LTX25SpanConditioningError("Governed span frame count must be positive")
    candidate = governed_frames
    remainder = (candidate - 1) % 8
    if remainder:
        candidate += 8 - remainder
    return candidate


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
