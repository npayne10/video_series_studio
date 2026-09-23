"""Governed internal render-span authority for Phase 20.18.2.3.2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any

from vscs.application.timed_asset_presence import (
    TimedAssetPresence,
    TimedAssetPresencePlan,
)


class GovernedInternalRenderSpanError(ValueError):
    """Raised when internal render-span authority is invalid or inconsistent."""


@dataclass(frozen=True, slots=True)
class GovernedInternalRenderSpan:
    """One contiguous provider-neutral render interval inside one editorial Shot."""

    shot_id: str
    sequence_number: int
    start_frame: int
    through_frame: int
    frames_per_second: int
    source_timed_asset_presence_fingerprint: str
    active_presence_ids: tuple[str, ...] = ()
    active_asset_ids: tuple[str, ...] = ()
    introduced_presence_ids: tuple[str, ...] = ()
    introduced_asset_ids: tuple[str, ...] = ()
    removed_presence_ids: tuple[str, ...] = ()
    removed_asset_ids: tuple[str, ...] = ()
    opening_internal_boundary_id: str | None = None
    closing_internal_boundary_id: str | None = None

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise GovernedInternalRenderSpanError("Internal render span requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        if self.sequence_number <= 0:
            raise GovernedInternalRenderSpanError("Internal render span sequence must be positive")
        if self.start_frame < 0:
            raise GovernedInternalRenderSpanError(
                "Internal render span start_frame cannot be negative"
            )
        if self.through_frame < self.start_frame:
            raise GovernedInternalRenderSpanError(
                "Internal render span through_frame cannot precede start_frame"
            )
        if self.frames_per_second <= 0:
            raise GovernedInternalRenderSpanError(
                "Internal render span frames_per_second must be positive"
            )
        fingerprint = self.source_timed_asset_presence_fingerprint.strip().lower()
        if not fingerprint:
            raise GovernedInternalRenderSpanError(
                "Internal render span requires source timed-presence fingerprint"
            )
        object.__setattr__(self, "source_timed_asset_presence_fingerprint", fingerprint)

        for field_name in (
            "active_presence_ids",
            "active_asset_ids",
            "introduced_presence_ids",
            "introduced_asset_ids",
            "removed_presence_ids",
            "removed_asset_ids",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise GovernedInternalRenderSpanError(
                    f"Internal render span {field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise GovernedInternalRenderSpanError(
                    f"Internal render span {field_name} cannot contain duplicates"
                )
            object.__setattr__(self, field_name, values)

        for field_name in (
            "opening_internal_boundary_id",
            "closing_internal_boundary_id",
        ):
            raw = getattr(self, field_name)
            if raw is not None:
                normalized = raw.strip()
                if not normalized:
                    raise GovernedInternalRenderSpanError(
                        f"Internal render span {field_name} cannot be blank"
                    )
                object.__setattr__(self, field_name, normalized)

    @property
    def frame_count(self) -> int:
        return self.through_frame - self.start_frame + 1

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.frames_per_second

    @property
    def span_id(self) -> str:
        payload = {
            "shot_id": self.shot_id,
            "sequence_number": self.sequence_number,
            "start_frame": self.start_frame,
            "through_frame": self.through_frame,
            "frames_per_second": self.frames_per_second,
            "source_timed_asset_presence_fingerprint": (
                self.source_timed_asset_presence_fingerprint
            ),
            "active_presence_ids": list(self.active_presence_ids),
            "active_asset_ids": list(self.active_asset_ids),
            "introduced_presence_ids": list(self.introduced_presence_ids),
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "removed_presence_ids": list(self.removed_presence_ids),
            "removed_asset_ids": list(self.removed_asset_ids),
        }
        digest = _fingerprint(payload)[:16].upper()
        return f"IRS-{self.shot_id}-{self.sequence_number:03d}-{digest}"

    def to_dict(self) -> dict[str, object]:
        return {
            "span_id": self.span_id,
            "shot_id": self.shot_id,
            "sequence_number": self.sequence_number,
            "start_frame": self.start_frame,
            "through_frame": self.through_frame,
            "frame_count": self.frame_count,
            "frames_per_second": self.frames_per_second,
            "duration_seconds": self.duration_seconds,
            "source_timed_asset_presence_fingerprint": (
                self.source_timed_asset_presence_fingerprint
            ),
            "active_presence_ids": list(self.active_presence_ids),
            "active_asset_ids": list(self.active_asset_ids),
            "introduced_presence_ids": list(self.introduced_presence_ids),
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "removed_presence_ids": list(self.removed_presence_ids),
            "removed_asset_ids": list(self.removed_asset_ids),
            "opening_internal_boundary_id": self.opening_internal_boundary_id,
            "closing_internal_boundary_id": self.closing_internal_boundary_id,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GovernedInternalRenderSpan:
        span = cls(
            shot_id=str(raw.get("shot_id") or ""),
            sequence_number=_required_int(raw, "sequence_number"),
            start_frame=_required_int(raw, "start_frame"),
            through_frame=_required_int(raw, "through_frame"),
            frames_per_second=_required_int(raw, "frames_per_second"),
            source_timed_asset_presence_fingerprint=str(
                raw.get("source_timed_asset_presence_fingerprint") or ""
            ),
            active_presence_ids=_string_tuple(raw, "active_presence_ids"),
            active_asset_ids=_string_tuple(raw, "active_asset_ids"),
            introduced_presence_ids=_string_tuple(raw, "introduced_presence_ids"),
            introduced_asset_ids=_string_tuple(raw, "introduced_asset_ids"),
            removed_presence_ids=_string_tuple(raw, "removed_presence_ids"),
            removed_asset_ids=_string_tuple(raw, "removed_asset_ids"),
            opening_internal_boundary_id=_optional_text(raw, "opening_internal_boundary_id"),
            closing_internal_boundary_id=_optional_text(raw, "closing_internal_boundary_id"),
        )
        supplied_id = str(raw.get("span_id") or "").strip()
        if supplied_id and supplied_id != span.span_id:
            raise GovernedInternalRenderSpanError(
                "Internal render span identity does not match governed content"
            )
        supplied_frames = raw.get("frame_count")
        if supplied_frames is not None and _integer_value(supplied_frames, "frame_count") != (
            span.frame_count
        ):
            raise GovernedInternalRenderSpanError(
                "Internal render span frame_count does not match its frame interval"
            )
        supplied_duration = raw.get("duration_seconds")
        if (
            supplied_duration is not None
            and abs(_number_value(supplied_duration, "duration_seconds") - span.duration_seconds)
            > 1e-9
        ):
            raise GovernedInternalRenderSpanError(
                "Internal render span duration_seconds does not match its frame interval"
            )
        return span


@dataclass(frozen=True, slots=True)
class GovernedInternalSpanBoundary:
    """Required continuity handoff between two adjacent internal render spans."""

    shot_id: str
    sequence_number: int
    source_span_id: str
    target_span_id: str
    source_global_frame_index: int
    target_global_frame_index: int
    source_local_frame_index: int
    target_local_frame_index: int
    source_timed_asset_presence_fingerprint: str

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise GovernedInternalRenderSpanError("Internal span boundary requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        if self.sequence_number <= 0:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary sequence must be positive"
            )
        if not self.source_span_id.strip() or not self.target_span_id.strip():
            raise GovernedInternalRenderSpanError(
                "Internal span boundary requires source and target span identities"
            )
        if self.source_global_frame_index < 0 or self.target_global_frame_index < 0:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary global frame indices cannot be negative"
            )
        if self.target_global_frame_index != self.source_global_frame_index + 1:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary must join consecutive global frames"
            )
        if self.source_local_frame_index < 0:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary source local frame cannot be negative"
            )
        if self.target_local_frame_index != 0:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary target local frame must be zero"
            )
        fingerprint = self.source_timed_asset_presence_fingerprint.strip().lower()
        if not fingerprint:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary requires source timed-presence fingerprint"
            )
        object.__setattr__(self, "source_timed_asset_presence_fingerprint", fingerprint)

    @property
    def boundary_id(self) -> str:
        payload = {
            "shot_id": self.shot_id,
            "sequence_number": self.sequence_number,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "source_timed_asset_presence_fingerprint": (
                self.source_timed_asset_presence_fingerprint
            ),
        }
        digest = _fingerprint(payload)[:16].upper()
        return f"IRB-{self.shot_id}-{self.sequence_number:03d}-{digest}"

    def to_dict(self) -> dict[str, object]:
        return {
            "boundary_id": self.boundary_id,
            "authority_kind": "governed_internal_span_boundary_requirement",
            "status": "required",
            "shot_id": self.shot_id,
            "sequence_number": self.sequence_number,
            "source_span_id": self.source_span_id,
            "target_span_id": self.target_span_id,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "source_local_frame_index": self.source_local_frame_index,
            "target_local_frame_index": self.target_local_frame_index,
            "source_timed_asset_presence_fingerprint": (
                self.source_timed_asset_presence_fingerprint
            ),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GovernedInternalSpanBoundary:
        boundary = cls(
            shot_id=str(raw.get("shot_id") or ""),
            sequence_number=_required_int(raw, "sequence_number"),
            source_span_id=str(raw.get("source_span_id") or ""),
            target_span_id=str(raw.get("target_span_id") or ""),
            source_global_frame_index=_required_int(raw, "source_global_frame_index"),
            target_global_frame_index=_required_int(raw, "target_global_frame_index"),
            source_local_frame_index=_required_int(raw, "source_local_frame_index"),
            target_local_frame_index=_required_int(raw, "target_local_frame_index"),
            source_timed_asset_presence_fingerprint=str(
                raw.get("source_timed_asset_presence_fingerprint") or ""
            ),
        )
        supplied_id = str(raw.get("boundary_id") or "").strip()
        if supplied_id and supplied_id != boundary.boundary_id:
            raise GovernedInternalRenderSpanError(
                "Internal span boundary identity does not match governed content"
            )
        authority_kind = str(raw.get("authority_kind") or "").strip()
        if authority_kind and authority_kind != "governed_internal_span_boundary_requirement":
            raise GovernedInternalRenderSpanError(
                "Internal span boundary authority kind is invalid"
            )
        status = str(raw.get("status") or "").strip()
        if status and status != "required":
            raise GovernedInternalRenderSpanError(
                "Phase 20.18.2.3.2 internal span boundaries must remain required until rendered"
            )
        return boundary


@dataclass(frozen=True, slots=True)
class GovernedInternalRenderSpanPlan:
    """Deterministic internal render topology derived from timed asset presence."""

    shot_id: str
    frames_per_second: int
    frame_count: int
    source_timed_asset_presence_plan_id: str
    source_timed_asset_presence_fingerprint: str
    change_frames: tuple[int, ...]
    spans: tuple[GovernedInternalRenderSpan, ...]
    boundaries: tuple[GovernedInternalSpanBoundary, ...]
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise GovernedInternalRenderSpanError("Internal render span plan requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        if self.schema_version != "1.0":
            raise GovernedInternalRenderSpanError(
                f"Unsupported internal render span schema: {self.schema_version!r}"
            )
        if self.provider_neutral is not True:
            raise GovernedInternalRenderSpanError(
                "Internal render span authority must remain provider-neutral"
            )
        if self.frames_per_second <= 0 or self.frame_count <= 0:
            raise GovernedInternalRenderSpanError(
                "Internal render span timing basis must be positive"
            )
        plan_id = self.source_timed_asset_presence_plan_id.strip()
        fingerprint = self.source_timed_asset_presence_fingerprint.strip().lower()
        if not plan_id or not fingerprint:
            raise GovernedInternalRenderSpanError(
                "Internal render spans require source timed-presence identity and fingerprint"
            )
        object.__setattr__(self, "source_timed_asset_presence_plan_id", plan_id)
        object.__setattr__(self, "source_timed_asset_presence_fingerprint", fingerprint)
        changes = tuple(self.change_frames)
        if tuple(sorted(set(changes))) != changes:
            raise GovernedInternalRenderSpanError(
                "Internal render span change_frames must be unique and ordered"
            )
        if any(frame <= 0 or frame >= self.frame_count for frame in changes):
            raise GovernedInternalRenderSpanError(
                "Internal render span change_frames must fall inside the governed Shot"
            )
        object.__setattr__(self, "change_frames", changes)
        self._validate_topology()

    @property
    def span_count(self) -> int:
        return len(self.spans)

    @property
    def plan_id(self) -> str:
        return f"IRSPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

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
            "timing_basis": {
                "frames_per_second": self.frames_per_second,
                "frame_count": self.frame_count,
            },
            "source_timed_asset_presence": {
                "plan_id": self.source_timed_asset_presence_plan_id,
                "fingerprint": self.source_timed_asset_presence_fingerprint,
            },
            "change_frames": list(self.change_frames),
            "span_count": self.span_count,
            "spans": [span.to_dict() for span in self.spans],
            "boundaries": [boundary.to_dict() for boundary in self.boundaries],
        }

    def require_source(self, source: TimedAssetPresencePlan) -> None:
        if source.shot_id != self.shot_id:
            raise GovernedInternalRenderSpanError(
                "Internal render span Shot identity does not match timed-presence authority"
            )
        if source.plan_id != self.source_timed_asset_presence_plan_id:
            raise GovernedInternalRenderSpanError(
                "Internal render span source timed-presence plan identity changed"
            )
        if source.fingerprint != self.source_timed_asset_presence_fingerprint:
            raise GovernedInternalRenderSpanError(
                "Internal render span source timed-presence fingerprint changed"
            )
        if source.frames_per_second != self.frames_per_second:
            raise GovernedInternalRenderSpanError(
                "Internal render span frame rate does not match timed-presence authority"
            )
        if source.frame_count != self.frame_count:
            raise GovernedInternalRenderSpanError(
                "Internal render span frame count does not match timed-presence authority"
            )
        if source.change_frames != self.change_frames:
            raise GovernedInternalRenderSpanError(
                "Internal render span change frames do not match timed-presence authority"
            )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> GovernedInternalRenderSpanPlan:
        timing = raw.get("timing_basis")
        if not isinstance(timing, dict):
            raise GovernedInternalRenderSpanError(
                "Internal render span timing_basis must be an object"
            )
        source = raw.get("source_timed_asset_presence")
        if not isinstance(source, dict):
            raise GovernedInternalRenderSpanError(
                "Internal render span source_timed_asset_presence must be an object"
            )
        spans_raw = raw.get("spans")
        boundaries_raw = raw.get("boundaries")
        changes_raw = raw.get("change_frames")
        if not isinstance(spans_raw, list):
            raise GovernedInternalRenderSpanError("Internal render spans must be an array")
        if not isinstance(boundaries_raw, list):
            raise GovernedInternalRenderSpanError("Internal render boundaries must be an array")
        if not isinstance(changes_raw, list):
            raise GovernedInternalRenderSpanError(
                "Internal render span change_frames must be an array"
            )
        spans = tuple(
            GovernedInternalRenderSpan.from_dict(dict(item))
            for item in spans_raw
            if isinstance(item, dict)
        )
        if len(spans) != len(spans_raw):
            raise GovernedInternalRenderSpanError(
                "Every internal render spans entry must be an object"
            )
        boundaries = tuple(
            GovernedInternalSpanBoundary.from_dict(dict(item))
            for item in boundaries_raw
            if isinstance(item, dict)
        )
        if len(boundaries) != len(boundaries_raw):
            raise GovernedInternalRenderSpanError(
                "Every internal render boundaries entry must be an object"
            )
        provider_neutral = raw.get("provider_neutral", True)
        if not isinstance(provider_neutral, bool):
            raise GovernedInternalRenderSpanError("provider_neutral must be a boolean")

        plan = cls(
            shot_id=str(raw.get("shot_id") or ""),
            frames_per_second=_required_int(timing, "frames_per_second"),
            frame_count=_required_int(timing, "frame_count"),
            source_timed_asset_presence_plan_id=str(source.get("plan_id") or ""),
            source_timed_asset_presence_fingerprint=str(source.get("fingerprint") or ""),
            change_frames=tuple(_integer_value(value, "change_frames") for value in changes_raw),
            spans=spans,
            boundaries=boundaries,
            schema_version=str(raw.get("schema_version") or "1.0"),
            provider_neutral=provider_neutral,
        )
        supplied_count = raw.get("span_count")
        if supplied_count is not None and _integer_value(supplied_count, "span_count") != (
            plan.span_count
        ):
            raise GovernedInternalRenderSpanError(
                "Internal render span_count does not match persisted spans"
            )
        supplied_id = str(raw.get("plan_id") or "").strip()
        if supplied_id and supplied_id != plan.plan_id:
            raise GovernedInternalRenderSpanError(
                "Internal render span plan identity does not match governed content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != plan.fingerprint:
            raise GovernedInternalRenderSpanError(
                "Internal render span fingerprint does not match governed content"
            )
        return plan

    def _validate_topology(self) -> None:
        if not self.spans:
            raise GovernedInternalRenderSpanError(
                "Internal render span plan must contain at least one span"
            )
        expected_start = 0
        expected_fingerprint = self.source_timed_asset_presence_fingerprint
        for index, span in enumerate(self.spans, start=1):
            if span.shot_id != self.shot_id:
                raise GovernedInternalRenderSpanError(
                    "Internal render span Shot identity does not match plan"
                )
            if span.sequence_number != index:
                raise GovernedInternalRenderSpanError(
                    "Internal render span sequence is not contiguous"
                )
            if span.start_frame != expected_start:
                raise GovernedInternalRenderSpanError(
                    "Internal render spans contain a frame gap or overlap"
                )
            if span.frames_per_second != self.frames_per_second:
                raise GovernedInternalRenderSpanError(
                    "Internal render span frame rate does not match plan"
                )
            if span.source_timed_asset_presence_fingerprint != expected_fingerprint:
                raise GovernedInternalRenderSpanError(
                    "Internal render span source fingerprint does not match plan"
                )
            expected_start = span.through_frame + 1
        if expected_start != self.frame_count:
            raise GovernedInternalRenderSpanError(
                "Internal render spans do not cover the full governed Shot"
            )

        expected_changes = tuple(span.start_frame for span in self.spans[1:])
        if expected_changes != self.change_frames:
            raise GovernedInternalRenderSpanError(
                "Internal render span starts do not match governed change_frames"
            )
        if len(self.boundaries) != len(self.spans) - 1:
            raise GovernedInternalRenderSpanError(
                "Internal render boundary count must equal span_count minus one"
            )

        by_id = {span.span_id: span for span in self.spans}
        if len(by_id) != len(self.spans):
            raise GovernedInternalRenderSpanError("Internal render span identities must be unique")
        boundary_ids = {boundary.boundary_id for boundary in self.boundaries}
        if len(boundary_ids) != len(self.boundaries):
            raise GovernedInternalRenderSpanError(
                "Internal render boundary identities must be unique"
            )

        for index, boundary in enumerate(self.boundaries):
            source = self.spans[index]
            target = self.spans[index + 1]
            if boundary.shot_id != self.shot_id:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary Shot identity does not match plan"
                )
            if boundary.sequence_number != index + 1:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary sequence is not contiguous"
                )
            if boundary.source_span_id != source.span_id:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary source span does not match topology"
                )
            if boundary.target_span_id != target.span_id:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary target span does not match topology"
                )
            if boundary.source_global_frame_index != source.through_frame:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary source global frame does not match source span"
                )
            if boundary.target_global_frame_index != target.start_frame:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary target global frame does not match target span"
                )
            if boundary.source_local_frame_index != source.frame_count - 1:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary source local frame is not source-span final frame"
                )
            if boundary.source_timed_asset_presence_fingerprint != expected_fingerprint:
                raise GovernedInternalRenderSpanError(
                    "Internal render boundary source fingerprint does not match plan"
                )
            if source.closing_internal_boundary_id != boundary.boundary_id:
                raise GovernedInternalRenderSpanError(
                    "Source span does not reference its governed internal closing boundary"
                )
            if target.opening_internal_boundary_id != boundary.boundary_id:
                raise GovernedInternalRenderSpanError(
                    "Target span does not reference its governed internal opening boundary"
                )

        if self.spans[0].opening_internal_boundary_id is not None:
            raise GovernedInternalRenderSpanError(
                "First internal render span cannot inherit an internal opening boundary"
            )
        if self.spans[-1].closing_internal_boundary_id is not None:
            raise GovernedInternalRenderSpanError(
                "Final internal render span cannot publish an internal closing boundary"
            )


class GovernedInternalRenderSpanCompiler:
    """Derive exact internal render topology from reviewed timed asset presence."""

    def compile(self, source: TimedAssetPresencePlan) -> GovernedInternalRenderSpanPlan:
        starts = (0, *source.change_frames)
        ends = (*source.change_frames, source.frame_count)
        spans: list[GovernedInternalRenderSpan] = []
        for sequence, (start_frame, end_exclusive) in enumerate(zip(starts, ends), start=1):
            through_frame = end_exclusive - 1
            active: tuple[TimedAssetPresence, ...] = source.active_at(start_frame)
            introduced: tuple[TimedAssetPresence, ...] = (
                tuple(item for item in source.presences if item.from_frame == start_frame)
                if start_frame > 0
                else ()
            )
            removed: tuple[TimedAssetPresence, ...] = (
                tuple(item for item in source.presences if item.through_frame == start_frame - 1)
                if start_frame > 0
                else ()
            )
            spans.append(
                GovernedInternalRenderSpan(
                    shot_id=source.shot_id,
                    sequence_number=sequence,
                    start_frame=start_frame,
                    through_frame=through_frame,
                    frames_per_second=source.frames_per_second,
                    source_timed_asset_presence_fingerprint=source.fingerprint,
                    active_presence_ids=_presence_ids(active),
                    active_asset_ids=_asset_ids(active),
                    introduced_presence_ids=_presence_ids(introduced),
                    introduced_asset_ids=_asset_ids(introduced),
                    removed_presence_ids=_presence_ids(removed),
                    removed_asset_ids=_asset_ids(removed),
                )
            )

        boundaries: list[GovernedInternalSpanBoundary] = []
        for index in range(len(spans) - 1):
            source_span = spans[index]
            target_span = spans[index + 1]
            boundary = GovernedInternalSpanBoundary(
                shot_id=source.shot_id,
                sequence_number=index + 1,
                source_span_id=source_span.span_id,
                target_span_id=target_span.span_id,
                source_global_frame_index=source_span.through_frame,
                target_global_frame_index=target_span.start_frame,
                source_local_frame_index=source_span.frame_count - 1,
                target_local_frame_index=0,
                source_timed_asset_presence_fingerprint=source.fingerprint,
            )
            boundaries.append(boundary)
            spans[index] = replace(
                source_span,
                closing_internal_boundary_id=boundary.boundary_id,
            )
            spans[index + 1] = replace(
                target_span,
                opening_internal_boundary_id=boundary.boundary_id,
            )

        return GovernedInternalRenderSpanPlan(
            shot_id=source.shot_id,
            frames_per_second=source.frames_per_second,
            frame_count=source.frame_count,
            source_timed_asset_presence_plan_id=source.plan_id,
            source_timed_asset_presence_fingerprint=source.fingerprint,
            change_frames=source.change_frames,
            spans=tuple(spans),
            boundaries=tuple(boundaries),
        )


def _presence_ids(presences: tuple[TimedAssetPresence, ...]) -> tuple[str, ...]:
    return tuple(item.presence_id for item in presences)


def _asset_ids(presences: tuple[TimedAssetPresence, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.asset_id for item in presences))


def _required_int(raw: dict[str, Any], key: str) -> int:
    if key not in raw:
        raise GovernedInternalRenderSpanError(f"Missing required integer field {key!r}")
    return _integer_value(raw[key], key)


def _integer_value(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise GovernedInternalRenderSpanError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise GovernedInternalRenderSpanError(f"{field_name} must be an integer") from exc
    raise GovernedInternalRenderSpanError(f"{field_name} must be an integer")


def _number_value(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise GovernedInternalRenderSpanError(f"{field_name} must be numeric")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise GovernedInternalRenderSpanError(f"{field_name} must be numeric") from exc
    raise GovernedInternalRenderSpanError(f"{field_name} must be numeric")


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list | tuple):
        raise GovernedInternalRenderSpanError(f"{key} must be an array")
    return tuple(str(item) for item in value)


def _optional_text(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    return str(value)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
