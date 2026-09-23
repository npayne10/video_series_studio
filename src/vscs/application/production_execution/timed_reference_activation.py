"""Timed canonical-reference activation authority for Phase 20.18.2.3.3."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from vscs.application.acpp.reference_roles import ReferenceRole
from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanPlan,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresence,
    TimedAssetPresencePlan,
)


class TimedCanonicalReferenceActivationError(ValueError):
    """Raised when per-span canonical-reference authority is unsafe or inconsistent."""


_FRAME_STATE_ROLES = frozenset(
    {
        ReferenceRole.SCENE_COMPOSITION_ANCHOR.value,
        ReferenceRole.CONTINUITY_ANCHOR.value,
        ReferenceRole.START_FRAME_REFERENCE.value,
        ReferenceRole.END_FRAME_REFERENCE.value,
    }
)


@dataclass(frozen=True, slots=True)
class SpanCanonicalReferenceActivation:
    """Canonical references authorized for exactly one governed internal render span."""

    span_id: str
    sequence_number: int
    start_frame: int
    through_frame: int
    active_asset_ids: tuple[str, ...]
    active_reference_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...] = ()
    removed_reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        span_id = self.span_id.strip()
        if not span_id:
            raise TimedCanonicalReferenceActivationError(
                "Span canonical-reference activation requires span_id"
            )
        object.__setattr__(self, "span_id", span_id)
        if self.sequence_number <= 0:
            raise TimedCanonicalReferenceActivationError(
                "Span canonical-reference activation sequence must be positive"
            )
        if self.start_frame < 0 or self.through_frame < self.start_frame:
            raise TimedCanonicalReferenceActivationError(
                "Span canonical-reference activation has an invalid frame interval"
            )
        for field_name in (
            "active_asset_ids",
            "active_reference_ids",
            "introduced_reference_ids",
            "removed_reference_ids",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise TimedCanonicalReferenceActivationError(
                    f"{field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise TimedCanonicalReferenceActivationError(
                    f"{field_name} cannot contain duplicate values"
                )
            object.__setattr__(self, field_name, values)
        active = set(self.active_reference_ids)
        if not set(self.introduced_reference_ids).issubset(active):
            raise TimedCanonicalReferenceActivationError(
                "Introduced canonical references must be active in their target span"
            )
        if set(self.removed_reference_ids) & active:
            raise TimedCanonicalReferenceActivationError(
                "Removed canonical references cannot remain active in their target span"
            )

    @property
    def activation_id(self) -> str:
        payload = {
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "start_frame": self.start_frame,
            "through_frame": self.through_frame,
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "removed_reference_ids": list(self.removed_reference_ids),
        }
        return f"TCRA-{_fingerprint(payload)[:16].upper()}"

    def to_dict(self) -> dict[str, object]:
        return {
            "activation_id": self.activation_id,
            "span_id": self.span_id,
            "sequence_number": self.sequence_number,
            "start_frame": self.start_frame,
            "through_frame": self.through_frame,
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "removed_reference_ids": list(self.removed_reference_ids),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SpanCanonicalReferenceActivation:
        activation = cls(
            span_id=str(raw.get("span_id") or ""),
            sequence_number=_required_int(raw, "sequence_number"),
            start_frame=_required_int(raw, "start_frame"),
            through_frame=_required_int(raw, "through_frame"),
            active_asset_ids=_string_tuple(raw, "active_asset_ids"),
            active_reference_ids=_string_tuple(raw, "active_reference_ids"),
            introduced_reference_ids=_string_tuple(raw, "introduced_reference_ids"),
            removed_reference_ids=_string_tuple(raw, "removed_reference_ids"),
        )
        supplied_id = str(raw.get("activation_id") or "").strip()
        if supplied_id and supplied_id != activation.activation_id:
            raise TimedCanonicalReferenceActivationError(
                "Span canonical-reference activation identity does not match governed content"
            )
        return activation


@dataclass(frozen=True, slots=True)
class TimedCanonicalReferenceActivationPlan:
    """Provider-neutral reference activation derived from timed presence and span topology."""

    shot_id: str
    source_timed_asset_presence_plan_id: str
    source_timed_asset_presence_fingerprint: str
    source_internal_render_span_plan_id: str
    source_internal_render_span_fingerprint: str
    source_reference_plan_fingerprint: str | None
    frame_state_reference_ids: tuple[str, ...]
    activations: tuple[SpanCanonicalReferenceActivation, ...]
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation plan requires shot_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        if self.schema_version != "1.0":
            raise TimedCanonicalReferenceActivationError(
                f"Unsupported timed canonical-reference activation schema: {self.schema_version!r}"
            )
        if self.provider_neutral is not True:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation authority must be provider-neutral"
            )

        for field_name in (
            "source_timed_asset_presence_plan_id",
            "source_timed_asset_presence_fingerprint",
            "source_internal_render_span_plan_id",
            "source_internal_render_span_fingerprint",
        ):
            normalized = str(getattr(self, field_name)).strip()
            if not normalized:
                raise TimedCanonicalReferenceActivationError(
                    f"Timed canonical-reference activation requires {field_name}"
                )
            if field_name.endswith("fingerprint"):
                normalized = normalized.lower()
            object.__setattr__(self, field_name, normalized)

        if self.source_reference_plan_fingerprint is not None:
            fingerprint = self.source_reference_plan_fingerprint.strip().lower()
            if not fingerprint:
                raise TimedCanonicalReferenceActivationError(
                    "source_reference_plan_fingerprint cannot be blank"
                )
            object.__setattr__(self, "source_reference_plan_fingerprint", fingerprint)

        frame_state = tuple(str(value).strip() for value in self.frame_state_reference_ids)
        if any(not value for value in frame_state):
            raise TimedCanonicalReferenceActivationError(
                "frame_state_reference_ids cannot contain blank values"
            )
        if len(set(frame_state)) != len(frame_state):
            raise TimedCanonicalReferenceActivationError(
                "frame_state_reference_ids cannot contain duplicates"
            )
        object.__setattr__(self, "frame_state_reference_ids", frame_state)
        self._validate_topology()

    @property
    def activation_count(self) -> int:
        return len(self.activations)

    @property
    def plan_id(self) -> str:
        return f"TCRAPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_neutral": self.provider_neutral,
            "shot_id": self.shot_id,
            "source_timed_asset_presence": {
                "plan_id": self.source_timed_asset_presence_plan_id,
                "fingerprint": self.source_timed_asset_presence_fingerprint,
            },
            "source_internal_render_spans": {
                "plan_id": self.source_internal_render_span_plan_id,
                "fingerprint": self.source_internal_render_span_fingerprint,
            },
            "source_reference_plan_fingerprint": self.source_reference_plan_fingerprint,
            "frame_state_reference_ids": list(self.frame_state_reference_ids),
            "activation_count": self.activation_count,
            "activations": [activation.to_dict() for activation in self.activations],
        }

    def require_sources(
        self,
        timed_presence: TimedAssetPresencePlan,
        span_plan: GovernedInternalRenderSpanPlan,
        reference_plan: dict[str, Any] | None,
    ) -> None:
        span_plan.require_source(timed_presence)
        if timed_presence.shot_id != self.shot_id or span_plan.shot_id != self.shot_id:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation Shot identity changed"
            )
        if timed_presence.plan_id != self.source_timed_asset_presence_plan_id:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation source presence identity changed"
            )
        if timed_presence.fingerprint != self.source_timed_asset_presence_fingerprint:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation source presence fingerprint changed"
            )
        if span_plan.plan_id != self.source_internal_render_span_plan_id:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation source span identity changed"
            )
        if span_plan.fingerprint != self.source_internal_render_span_fingerprint:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation source span fingerprint changed"
            )
        reference_fingerprint = (
            _reference_plan_fingerprint(reference_plan) if reference_plan is not None else None
        )
        if reference_fingerprint != self.source_reference_plan_fingerprint:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation source ReferencePlan changed"
            )
        expected = TimedCanonicalReferenceActivationCompiler().compile(
            timed_presence,
            span_plan,
            reference_plan,
        )
        if expected.fingerprint != self.fingerprint:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation content no longer matches its sources"
            )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TimedCanonicalReferenceActivationPlan:
        presence = raw.get("source_timed_asset_presence")
        spans = raw.get("source_internal_render_spans")
        activations_raw = raw.get("activations")
        frame_state_raw = raw.get("frame_state_reference_ids", [])
        if not isinstance(presence, dict):
            raise TimedCanonicalReferenceActivationError(
                "source_timed_asset_presence must be an object"
            )
        if not isinstance(spans, dict):
            raise TimedCanonicalReferenceActivationError(
                "source_internal_render_spans must be an object"
            )
        if not isinstance(activations_raw, list):
            raise TimedCanonicalReferenceActivationError("activations must be an array")
        if not isinstance(frame_state_raw, list):
            raise TimedCanonicalReferenceActivationError(
                "frame_state_reference_ids must be an array"
            )
        activations = tuple(
            SpanCanonicalReferenceActivation.from_dict(dict(item))
            for item in activations_raw
            if isinstance(item, dict)
        )
        if len(activations) != len(activations_raw):
            raise TimedCanonicalReferenceActivationError(
                "Every activation entry must be an object"
            )
        reference_fingerprint_raw = raw.get("source_reference_plan_fingerprint")
        reference_fingerprint = (
            None
            if reference_fingerprint_raw is None
            else str(reference_fingerprint_raw)
        )
        provider_neutral = raw.get("provider_neutral", True)
        if not isinstance(provider_neutral, bool):
            raise TimedCanonicalReferenceActivationError(
                "provider_neutral must be a boolean"
            )

        plan = cls(
            shot_id=str(raw.get("shot_id") or ""),
            source_timed_asset_presence_plan_id=str(presence.get("plan_id") or ""),
            source_timed_asset_presence_fingerprint=str(presence.get("fingerprint") or ""),
            source_internal_render_span_plan_id=str(spans.get("plan_id") or ""),
            source_internal_render_span_fingerprint=str(spans.get("fingerprint") or ""),
            source_reference_plan_fingerprint=reference_fingerprint,
            frame_state_reference_ids=tuple(str(value) for value in frame_state_raw),
            activations=activations,
            schema_version=str(raw.get("schema_version") or "1.0"),
            provider_neutral=provider_neutral,
        )
        supplied_count = raw.get("activation_count")
        if supplied_count is not None and _integer_value(
            supplied_count, "activation_count"
        ) != plan.activation_count:
            raise TimedCanonicalReferenceActivationError(
                "activation_count does not match persisted activations"
            )
        supplied_id = str(raw.get("plan_id") or "").strip()
        if supplied_id and supplied_id != plan.plan_id:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation plan identity does not match content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != plan.fingerprint:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation fingerprint does not match content"
            )
        return plan

    def _validate_topology(self) -> None:
        if not self.activations:
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation plan requires at least one span activation"
            )
        for index, activation in enumerate(self.activations, start=1):
            if activation.sequence_number != index:
                raise TimedCanonicalReferenceActivationError(
                    "Timed canonical-reference activation sequence is not contiguous"
                )
        ids = [activation.activation_id for activation in self.activations]
        if len(set(ids)) != len(ids):
            raise TimedCanonicalReferenceActivationError(
                "Timed canonical-reference activation identities must be unique"
            )


class TimedCanonicalReferenceActivationCompiler:
    """Derive exact per-span canonical-reference sets from accepted VSCS authority."""

    def compile(
        self,
        timed_presence: TimedAssetPresencePlan,
        span_plan: GovernedInternalRenderSpanPlan,
        reference_plan: dict[str, Any] | None,
    ) -> TimedCanonicalReferenceActivationPlan:
        span_plan.require_source(timed_presence)
        references = _reference_records(reference_plan)
        references_by_id = {
            _required_text(reference, "reference_id"): reference for reference in references
        }
        if len(references_by_id) != len(references):
            raise TimedCanonicalReferenceActivationError(
                "Governed ReferencePlan contains duplicate reference IDs"
            )

        declared_ids: set[str] = set()
        for presence in timed_presence.presences:
            self._validate_presence_references(presence, references_by_id)
            declared_ids.update(presence.canonical_reference_ids)

        frame_state_ids = tuple(
            reference_id
            for reference_id, reference in references_by_id.items()
            if str(reference.get("role") or "") in _FRAME_STATE_ROLES
        )
        unscoped_supporting = tuple(
            reference_id
            for reference_id, reference in references_by_id.items()
            if reference_id not in declared_ids
            and str(reference.get("role") or "") not in _FRAME_STATE_ROLES
        )
        if span_plan.span_count > 1 and unscoped_supporting:
            raise TimedCanonicalReferenceActivationError(
                "Dynamic timed-reference activation cannot infer temporal scope for governed "
                "supporting references: "
                + ", ".join(unscoped_supporting)
            )

        presences_by_id = {
            presence.presence_id: presence for presence in timed_presence.presences
        }
        activations: list[SpanCanonicalReferenceActivation] = []
        for span in span_plan.spans:
            active = self._presences_for_ids(span.active_presence_ids, presences_by_id)
            introduced = self._presences_for_ids(
                span.introduced_presence_ids, presences_by_id
            )
            removed = self._presences_for_ids(span.removed_presence_ids, presences_by_id)
            active_reference_ids = _reference_ids(active)
            if span_plan.span_count == 1:
                active_reference_ids = tuple(
                    dict.fromkeys((*active_reference_ids, *unscoped_supporting))
                )
            activations.append(
                SpanCanonicalReferenceActivation(
                    span_id=span.span_id,
                    sequence_number=span.sequence_number,
                    start_frame=span.start_frame,
                    through_frame=span.through_frame,
                    active_asset_ids=span.active_asset_ids,
                    active_reference_ids=active_reference_ids,
                    introduced_reference_ids=_reference_ids(introduced),
                    removed_reference_ids=_reference_ids(removed),
                )
            )

        return TimedCanonicalReferenceActivationPlan(
            shot_id=timed_presence.shot_id,
            source_timed_asset_presence_plan_id=timed_presence.plan_id,
            source_timed_asset_presence_fingerprint=timed_presence.fingerprint,
            source_internal_render_span_plan_id=span_plan.plan_id,
            source_internal_render_span_fingerprint=span_plan.fingerprint,
            source_reference_plan_fingerprint=(
                _reference_plan_fingerprint(reference_plan)
                if reference_plan is not None
                else None
            ),
            frame_state_reference_ids=frame_state_ids,
            activations=tuple(activations),
        )

    @staticmethod
    def _validate_presence_references(
        presence: TimedAssetPresence,
        references_by_id: dict[str, dict[str, Any]],
    ) -> None:
        for reference_id in presence.canonical_reference_ids:
            reference = references_by_id.get(reference_id)
            if reference is None:
                raise TimedCanonicalReferenceActivationError(
                    f"Timed presence {presence.presence_id} requires canonical reference "
                    f"{reference_id}, but it is absent from the governed ReferencePlan"
                )
            role = str(reference.get("role") or "")
            if role in _FRAME_STATE_ROLES:
                raise TimedCanonicalReferenceActivationError(
                    f"Frame-state reference {reference_id} cannot be used as a timed canonical "
                    "asset reference"
                )
            asset_id = str(reference.get("asset_id") or "").strip()
            if not asset_id:
                raise TimedCanonicalReferenceActivationError(
                    f"Timed canonical reference {reference_id} has no governed asset_id"
                )
            if asset_id.upper() != presence.asset_id.upper():
                raise TimedCanonicalReferenceActivationError(
                    f"Timed canonical reference {reference_id} belongs to {asset_id}, not "
                    f"{presence.asset_id}"
                )

    @staticmethod
    def _presences_for_ids(
        presence_ids: tuple[str, ...],
        presences_by_id: dict[str, TimedAssetPresence],
    ) -> tuple[TimedAssetPresence, ...]:
        resolved: list[TimedAssetPresence] = []
        for presence_id in presence_ids:
            presence = presences_by_id.get(presence_id)
            if presence is None:
                raise TimedCanonicalReferenceActivationError(
                    f"Internal render span references unknown presence {presence_id}"
                )
            resolved.append(presence)
        return tuple(resolved)


def _reference_records(reference_plan: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if reference_plan is None:
        return ()
    status = str(reference_plan.get("status") or "").strip().lower()
    if status and status != "passed":
        raise TimedCanonicalReferenceActivationError(
            f"Governed ReferencePlan status must be passed, got {status!r}"
        )
    raw = reference_plan.get("references")
    if not isinstance(raw, list):
        raise TimedCanonicalReferenceActivationError(
            "Governed ReferencePlan references must be an array"
        )
    records = tuple(dict(item) for item in raw if isinstance(item, dict))
    if len(records) != len(raw):
        raise TimedCanonicalReferenceActivationError(
            "Every governed ReferencePlan reference must be an object"
        )
    return records


def _reference_ids(presences: tuple[TimedAssetPresence, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            reference_id
            for presence in presences
            for reference_id in presence.canonical_reference_ids
        )
    )


def _reference_plan_fingerprint(reference_plan: dict[str, Any]) -> str:
    return _fingerprint(reference_plan)


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise TimedCanonicalReferenceActivationError(
            f"Governed ReferencePlan reference is missing {key}"
        )
    return value


def _required_int(raw: dict[str, Any], key: str) -> int:
    if key not in raw:
        raise TimedCanonicalReferenceActivationError(
            f"Missing required integer field {key!r}"
        )
    return _integer_value(raw[key], key)


def _integer_value(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TimedCanonicalReferenceActivationError(
            f"{field_name} must be an integer"
        )
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise TimedCanonicalReferenceActivationError(
                f"{field_name} must be an integer"
            ) from exc
    raise TimedCanonicalReferenceActivationError(f"{field_name} must be an integer")


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list | tuple):
        raise TimedCanonicalReferenceActivationError(f"{key} must be an array")
    return tuple(str(item) for item in value)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
