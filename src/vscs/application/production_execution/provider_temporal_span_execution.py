"""Provider-neutral temporal span execution authority for Phase 20.18.2.3.6.4a."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.production_execution.timed_reference_activation import (
    TimedCanonicalReferenceActivationError,
    TimedCanonicalReferenceActivationPlan,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)


class ProviderTemporalSpanExecutionError(ValueError):
    """Raised when provider temporal-span execution authority is unsafe or stale."""


@dataclass(frozen=True, slots=True)
class ProviderTemporalSpanExecution:
    """Provider-neutral execution authority for exactly one governed internal span."""

    shot_id: str
    span_id: str
    sequence_number: int
    global_start_frame: int
    global_through_frame: int
    governed_frame_count: int
    active_asset_ids: tuple[str, ...]
    active_reference_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    removed_reference_ids: tuple[str, ...]
    future_reference_ids: tuple[str, ...]
    opening_authority_kind: str
    opening_frame_global_index: int
    assembly_sequence: int
    source_package_fingerprint: str
    source_span_plan_fingerprint: str
    source_activation_plan_fingerprint: str
    normalization_policy: str = "retain_exact_governed_frame_interval"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        span_id = self.span_id.strip()
        if not shot_id or not span_id:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution requires shot_id and span_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        object.__setattr__(self, "span_id", span_id)

        if self.sequence_number <= 0 or self.assembly_sequence != self.sequence_number:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution sequence and assembly order must be positive and equal"
            )
        if self.global_start_frame < 0 or self.global_through_frame < self.global_start_frame:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution has an invalid global frame interval"
            )
        expected_frames = self.global_through_frame - self.global_start_frame + 1
        if self.governed_frame_count != expected_frames:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution governed frame count does not match its interval"
            )
        if self.opening_frame_global_index != self.global_start_frame:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution opening authority must bind the first governed frame"
            )

        expected_opening_kind = (
            "shot_opening_authority"
            if self.sequence_number == 1
            else "governed_introduction_keyframe_required"
        )
        if self.opening_authority_kind != expected_opening_kind:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution opening authority kind does not match span sequence"
            )
        if self.normalization_policy != "retain_exact_governed_frame_interval":
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution normalization policy is unsupported"
            )

        for field_name in (
            "active_asset_ids",
            "active_reference_ids",
            "introduced_reference_ids",
            "removed_reference_ids",
            "future_reference_ids",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise ProviderTemporalSpanExecutionError(
                    f"Temporal span execution {field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise ProviderTemporalSpanExecutionError(
                    f"Temporal span execution {field_name} cannot contain duplicates"
                )
            object.__setattr__(self, field_name, values)

        active = set(self.active_reference_ids)
        introduced = set(self.introduced_reference_ids)
        removed = set(self.removed_reference_ids)
        future = set(self.future_reference_ids)
        if not introduced.issubset(active):
            raise ProviderTemporalSpanExecutionError(
                "Introduced references must be active in their target span"
            )
        if removed & active:
            raise ProviderTemporalSpanExecutionError(
                "Removed references cannot remain active in their target span"
            )
        if active & future:
            raise ProviderTemporalSpanExecutionError(
                "Future references must be structurally absent from the current provider span"
            )

        for field_name in (
            "source_package_fingerprint",
            "source_span_plan_fingerprint",
            "source_activation_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise ProviderTemporalSpanExecutionError(
                    f"Temporal span execution requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

    @property
    def execution_id(self) -> str:
        return f"PTSE-{self.shot_id}-{self.sequence_number:03d}-{_fingerprint(self._authority_payload())[:12].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "shot_id": self.shot_id,
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "global_start_frame": self.global_start_frame,
            "global_through_frame": self.global_through_frame,
            "governed_frame_count": self.governed_frame_count,
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "removed_reference_ids": list(self.removed_reference_ids),
            "future_reference_ids": list(self.future_reference_ids),
            "opening_authority_kind": self.opening_authority_kind,
            "opening_frame_global_index": self.opening_frame_global_index,
            "assembly_sequence": self.assembly_sequence,
            "source_package_fingerprint": self.source_package_fingerprint,
            "source_span_plan_fingerprint": self.source_span_plan_fingerprint,
            "source_activation_plan_fingerprint": self.source_activation_plan_fingerprint,
            "normalization_policy": self.normalization_policy,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["execution_id"] = self.execution_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ProviderTemporalSpanExecution:
        execution = cls(
            shot_id=str(raw.get("shot_id") or ""),
            span_id=str(raw.get("span_id") or ""),
            sequence_number=_required_int(raw, "sequence_number"),
            global_start_frame=_required_int(raw, "global_start_frame"),
            global_through_frame=_required_int(raw, "global_through_frame"),
            governed_frame_count=_required_int(raw, "governed_frame_count"),
            active_asset_ids=_string_tuple(raw, "active_asset_ids"),
            active_reference_ids=_string_tuple(raw, "active_reference_ids"),
            introduced_reference_ids=_string_tuple(raw, "introduced_reference_ids"),
            removed_reference_ids=_string_tuple(raw, "removed_reference_ids"),
            future_reference_ids=_string_tuple(raw, "future_reference_ids"),
            opening_authority_kind=str(raw.get("opening_authority_kind") or ""),
            opening_frame_global_index=_required_int(raw, "opening_frame_global_index"),
            assembly_sequence=_required_int(raw, "assembly_sequence"),
            source_package_fingerprint=str(raw.get("source_package_fingerprint") or ""),
            source_span_plan_fingerprint=str(raw.get("source_span_plan_fingerprint") or ""),
            source_activation_plan_fingerprint=str(
                raw.get("source_activation_plan_fingerprint") or ""
            ),
            normalization_policy=str(
                raw.get("normalization_policy") or "retain_exact_governed_frame_interval"
            ),
        )
        supplied_id = str(raw.get("execution_id") or "").strip()
        if supplied_id and supplied_id != execution.execution_id:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution identity does not match governed content"
            )
        return execution


@dataclass(frozen=True, slots=True)
class ProviderTemporalSpanExecutionPlan:
    """Complete provider-neutral temporal execution authority for one editorial Shot."""

    shot_id: str
    source_package_fingerprint: str
    source_timed_asset_presence_fingerprint: str
    source_span_plan_fingerprint: str
    source_activation_plan_fingerprint: str
    frame_count: int
    executions: tuple[ProviderTemporalSpanExecution, ...]
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan requires shot_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        if self.schema_version != "1.0" or self.provider_neutral is not True:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan must remain provider-neutral schema 1.0"
            )
        if self.frame_count <= 0 or not self.executions:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan requires positive frames and at least one span"
            )
        for field_name in (
            "source_package_fingerprint",
            "source_timed_asset_presence_fingerprint",
            "source_span_plan_fingerprint",
            "source_activation_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise ProviderTemporalSpanExecutionError(
                    f"Temporal span execution plan requires {field_name}"
                )
            object.__setattr__(self, field_name, value)
        self._validate_topology()

    @property
    def execution_count(self) -> int:
        return len(self.executions)

    @property
    def plan_id(self) -> str:
        return f"PTSEPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_neutral": self.provider_neutral,
            "shot_id": self.shot_id,
            "source_package_fingerprint": self.source_package_fingerprint,
            "source_timed_asset_presence_fingerprint": (
                self.source_timed_asset_presence_fingerprint
            ),
            "source_span_plan_fingerprint": self.source_span_plan_fingerprint,
            "source_activation_plan_fingerprint": self.source_activation_plan_fingerprint,
            "frame_count": self.frame_count,
            "execution_count": self.execution_count,
            "executions": [execution.to_dict() for execution in self.executions],
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ProviderTemporalSpanExecutionPlan:
        executions_raw = raw.get("executions")
        if not isinstance(executions_raw, list):
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan executions must be an array"
            )
        executions = tuple(
            ProviderTemporalSpanExecution.from_dict(dict(item))
            for item in executions_raw
            if isinstance(item, dict)
        )
        if len(executions) != len(executions_raw):
            raise ProviderTemporalSpanExecutionError(
                "Every temporal span execution entry must be an object"
            )
        provider_neutral = raw.get("provider_neutral", True)
        if not isinstance(provider_neutral, bool):
            raise ProviderTemporalSpanExecutionError("provider_neutral must be a boolean")
        plan = cls(
            shot_id=str(raw.get("shot_id") or ""),
            source_package_fingerprint=str(raw.get("source_package_fingerprint") or ""),
            source_timed_asset_presence_fingerprint=str(
                raw.get("source_timed_asset_presence_fingerprint") or ""
            ),
            source_span_plan_fingerprint=str(raw.get("source_span_plan_fingerprint") or ""),
            source_activation_plan_fingerprint=str(
                raw.get("source_activation_plan_fingerprint") or ""
            ),
            frame_count=_required_int(raw, "frame_count"),
            executions=executions,
            schema_version=str(raw.get("schema_version") or "1.0"),
            provider_neutral=provider_neutral,
        )
        supplied_count = raw.get("execution_count")
        if (
            supplied_count is not None
            and _integer_value(supplied_count, "execution_count") != plan.execution_count
        ):
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution_count does not match persisted executions"
            )
        supplied_id = str(raw.get("plan_id") or "").strip()
        if supplied_id and supplied_id != plan.plan_id:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan identity does not match governed content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != plan.fingerprint:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan fingerprint does not match governed content"
            )
        return plan

    def require_source(self, compiled: CompiledProductionPackage) -> None:
        if compiled.package_fingerprint.strip().lower() != self.source_package_fingerprint:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution source package fingerprint changed"
            )
        expected = ProviderTemporalSpanExecutionCompiler().compile(compiled)
        if expected.fingerprint != self.fingerprint:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution authority no longer matches compiled sources"
            )

    def _validate_topology(self) -> None:
        expected_start = 0
        total = 0
        for index, execution in enumerate(self.executions, start=1):
            if execution.shot_id != self.shot_id:
                raise ProviderTemporalSpanExecutionError(
                    "Temporal span execution Shot identity changed inside the plan"
                )
            if execution.sequence_number != index:
                raise ProviderTemporalSpanExecutionError(
                    "Temporal span execution sequence is not contiguous"
                )
            if execution.global_start_frame != expected_start:
                raise ProviderTemporalSpanExecutionError(
                    "Temporal span executions contain a gap or overlap"
                )
            if execution.source_package_fingerprint != self.source_package_fingerprint:
                raise ProviderTemporalSpanExecutionError(
                    "Temporal span execution source package fingerprint is inconsistent"
                )
            if execution.source_span_plan_fingerprint != self.source_span_plan_fingerprint:
                raise ProviderTemporalSpanExecutionError(
                    "Temporal span execution source span fingerprint is inconsistent"
                )
            if execution.source_activation_plan_fingerprint != (
                self.source_activation_plan_fingerprint
            ):
                raise ProviderTemporalSpanExecutionError(
                    "Temporal span execution source activation fingerprint is inconsistent"
                )
            expected_start = execution.global_through_frame + 1
            total += execution.governed_frame_count
        if total != self.frame_count or expected_start != self.frame_count:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution plan does not cover the governed Shot exactly once"
            )


class ProviderTemporalSpanExecutionCompiler:
    """Compile provider-neutral execution spans from accepted temporal authority."""

    def compile(
        self,
        compiled: CompiledProductionPackage,
    ) -> ProviderTemporalSpanExecutionPlan:
        if not isinstance(compiled.timed_asset_presence, dict):
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution requires Timed Asset Presence authority"
            )
        if not isinstance(compiled.internal_render_spans, dict):
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution requires Governed Internal Render Spans"
            )
        if not isinstance(compiled.timed_reference_activation, dict):
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution requires Timed Canonical Reference Activation"
            )

        try:
            timed = TimedAssetPresencePlan.from_dict(compiled.timed_asset_presence)
            spans = GovernedInternalRenderSpanPlan.from_dict(compiled.internal_render_spans)
            activation = TimedCanonicalReferenceActivationPlan.from_dict(
                compiled.timed_reference_activation
            )
            spans.require_source(timed)
            activation.require_sources(timed, spans, compiled.reference_plan)
        except (
            TimedAssetPresenceError,
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
        ) as exc:
            raise ProviderTemporalSpanExecutionError(
                f"Temporal span execution source authority is invalid: {exc}"
            ) from exc

        if (
            compiled.shot_id.strip().upper() != timed.shot_id
            or spans.shot_id != timed.shot_id
            or activation.shot_id != timed.shot_id
        ):
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution Shot identity does not match compiled authority"
            )
        if compiled.frame_count != timed.frame_count:
            raise ProviderTemporalSpanExecutionError(
                "Temporal span execution frame count does not match compiled Shot"
            )

        activation_by_span = {item.span_id: item for item in activation.activations}
        executions: list[ProviderTemporalSpanExecution] = []
        for index, span in enumerate(spans.spans):
            current = activation_by_span.get(span.span_id)
            if current is None:
                raise ProviderTemporalSpanExecutionError(
                    f"No timed reference activation exists for internal span {span.span_id}"
                )
            future_reference_ids = _future_reference_ids(
                activation.activations[index + 1 :],
                current.active_reference_ids,
            )
            executions.append(
                ProviderTemporalSpanExecution(
                    shot_id=timed.shot_id,
                    span_id=span.span_id,
                    sequence_number=span.sequence_number,
                    global_start_frame=span.start_frame,
                    global_through_frame=span.through_frame,
                    governed_frame_count=span.frame_count,
                    active_asset_ids=current.active_asset_ids,
                    active_reference_ids=current.active_reference_ids,
                    introduced_reference_ids=current.introduced_reference_ids,
                    removed_reference_ids=current.removed_reference_ids,
                    future_reference_ids=future_reference_ids,
                    opening_authority_kind=(
                        "shot_opening_authority"
                        if span.sequence_number == 1
                        else "governed_introduction_keyframe_required"
                    ),
                    opening_frame_global_index=span.start_frame,
                    assembly_sequence=span.sequence_number,
                    source_package_fingerprint=compiled.package_fingerprint,
                    source_span_plan_fingerprint=spans.fingerprint,
                    source_activation_plan_fingerprint=activation.fingerprint,
                )
            )

        plan = ProviderTemporalSpanExecutionPlan(
            shot_id=timed.shot_id,
            source_package_fingerprint=compiled.package_fingerprint,
            source_timed_asset_presence_fingerprint=timed.fingerprint,
            source_span_plan_fingerprint=spans.fingerprint,
            source_activation_plan_fingerprint=activation.fingerprint,
            frame_count=timed.frame_count,
            executions=tuple(executions),
        )
        return plan


def _future_reference_ids(
    later_activations: tuple[Any, ...],
    active_reference_ids: tuple[str, ...],
) -> tuple[str, ...]:
    active = set(active_reference_ids)
    ordered: list[str] = []
    seen: set[str] = set()
    for activation in later_activations:
        for reference_id in activation.active_reference_ids:
            if reference_id in active or reference_id in seen:
                continue
            ordered.append(reference_id)
            seen.add(reference_id)
    return tuple(ordered)


def _required_int(raw: dict[str, Any], key: str) -> int:
    if key not in raw:
        raise ProviderTemporalSpanExecutionError(f"Missing required integer field: {key}")
    return _integer_value(raw[key], key)


def _integer_value(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ProviderTemporalSpanExecutionError(f"{field_name} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderTemporalSpanExecutionError(f"{field_name} must be an integer") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ProviderTemporalSpanExecutionError(f"{field_name} must be an integer")
    return number


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ProviderTemporalSpanExecutionError(f"{key} must be an array")
    return tuple(str(item) for item in value)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
