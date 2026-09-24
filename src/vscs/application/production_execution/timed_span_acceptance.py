"""Operator-facing QC and functional-acceptance authority for Phase 20.18.2.3.5."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirementPlan,
)
from .internal_render_spans import (
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)


class TimedSpanAcceptanceError(RuntimeError):
    """Raised when governed timed-span functional acceptance is invalid or stale."""


class TimedSpanAcceptanceState(StrEnum):
    """Operator-visible Phase 20.18.2.3.5 acceptance state."""

    NOT_APPLICABLE = "not_applicable"
    KEYFRAME_REQUIRED = "keyframe_required"
    OUTPUTS_REQUIRED = "outputs_required"
    QC_REQUIRED = "qc_required"
    ACCEPTED = "accepted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TimedSpanVisualQCRecord:
    """Human visual QC for one exact internal introduction boundary."""

    shot_id: str
    requirement_id: str
    boundary_id: str
    source_global_frame_index: int
    target_global_frame_index: int
    introduced_asset_ids: tuple[str, ...]
    absent_before_boundary: bool
    present_from_target_frame: bool
    source_continuity_preserved: bool
    no_unapproved_assets: bool
    approved_by: str
    approved_at: str
    notes: str = ""
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise TimedSpanAcceptanceError("Timed-span QC requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        for field_name in ("requirement_id", "boundary_id", "approved_by", "approved_at"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise TimedSpanAcceptanceError(f"Timed-span QC requires {field_name}")
            object.__setattr__(self, field_name, value)
        if self.source_global_frame_index < 0:
            raise TimedSpanAcceptanceError("Timed-span QC source frame cannot be negative")
        if self.target_global_frame_index != self.source_global_frame_index + 1:
            raise TimedSpanAcceptanceError(
                "Timed-span QC target frame must immediately follow its source boundary"
            )
        assets = tuple(str(value).strip() for value in self.introduced_asset_ids)
        if any(not value for value in assets) or len(set(assets)) != len(assets):
            raise TimedSpanAcceptanceError(
                "Timed-span QC introduced_asset_ids must be unique non-blank values"
            )
        object.__setattr__(self, "introduced_asset_ids", assets)

    @property
    def passed(self) -> bool:
        return all(
            (
                self.absent_before_boundary,
                self.present_from_target_frame,
                self.source_continuity_preserved,
                self.no_unapproved_assets,
            )
        )

    @property
    def record_id(self) -> str:
        return f"TSQC-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "shot_id": self.shot_id,
            "requirement_id": self.requirement_id,
            "boundary_id": self.boundary_id,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "absent_before_boundary": self.absent_before_boundary,
            "present_from_target_frame": self.present_from_target_frame,
            "source_continuity_preserved": self.source_continuity_preserved,
            "no_unapproved_assets": self.no_unapproved_assets,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "notes": self.notes,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["record_id"] = self.record_id
        payload["passed"] = self.passed
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TimedSpanVisualQCRecord:
        record = cls(
            shot_id=str(raw.get("shot_id") or ""),
            requirement_id=str(raw.get("requirement_id") or ""),
            boundary_id=str(raw.get("boundary_id") or ""),
            source_global_frame_index=_required_int(raw, "source_global_frame_index"),
            target_global_frame_index=_required_int(raw, "target_global_frame_index"),
            introduced_asset_ids=_string_tuple(raw, "introduced_asset_ids"),
            absent_before_boundary=_required_bool(raw, "absent_before_boundary"),
            present_from_target_frame=_required_bool(raw, "present_from_target_frame"),
            source_continuity_preserved=_required_bool(raw, "source_continuity_preserved"),
            no_unapproved_assets=_required_bool(raw, "no_unapproved_assets"),
            approved_by=str(raw.get("approved_by") or ""),
            approved_at=str(raw.get("approved_at") or ""),
            notes=str(raw.get("notes") or ""),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied_id = str(raw.get("record_id") or "").strip()
        if supplied_id and supplied_id != record.record_id:
            raise TimedSpanAcceptanceError(
                "Timed-span QC record identity does not match governed content"
            )
        supplied_passed = raw.get("passed")
        if supplied_passed is not None and supplied_passed is not record.passed:
            raise TimedSpanAcceptanceError(
                "Timed-span QC persisted pass state does not match its observations"
            )
        return record


@dataclass(frozen=True, slots=True)
class TimedSpanAssemblyEvidence:
    """Verified normalized span outputs and final assembled Shot evidence."""

    shot_id: str
    source_span_plan_id: str
    source_span_plan_fingerprint: str
    span_ids: tuple[str, ...]
    span_paths: tuple[str, ...]
    span_frame_counts: tuple[int, ...]
    final_path: str
    final_frame_count: int
    width: int
    height: int
    frames_per_second: int
    final_sha256: str
    recorded_at: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise TimedSpanAcceptanceError("Timed-span assembly evidence requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        if not self.source_span_plan_id.strip() or not self.source_span_plan_fingerprint.strip():
            raise TimedSpanAcceptanceError(
                "Timed-span assembly evidence requires source span-plan identity and fingerprint"
            )
        object.__setattr__(
            self,
            "source_span_plan_fingerprint",
            self.source_span_plan_fingerprint.strip().lower(),
        )
        if not self.span_ids or len(self.span_ids) != len(self.span_paths):
            raise TimedSpanAcceptanceError(
                "Timed-span assembly evidence requires one path per span"
            )
        if len(self.span_ids) != len(self.span_frame_counts):
            raise TimedSpanAcceptanceError(
                "Timed-span assembly evidence requires one frame count per span"
            )
        if len(set(self.span_ids)) != len(self.span_ids):
            raise TimedSpanAcceptanceError("Timed-span assembly span IDs must be unique")
        if any(count <= 0 for count in self.span_frame_counts):
            raise TimedSpanAcceptanceError("Timed-span assembly frame counts must be positive")
        if self.final_frame_count <= 0:
            raise TimedSpanAcceptanceError("Timed-span final frame count must be positive")
        if self.width <= 0 or self.height <= 0 or self.frames_per_second <= 0:
            raise TimedSpanAcceptanceError(
                "Timed-span assembly dimensions and frame rate must be positive"
            )
        if not self.final_path.strip() or not self.final_sha256.strip() or not self.recorded_at.strip():
            raise TimedSpanAcceptanceError(
                "Timed-span assembly final path, checksum, and timestamp are required"
            )
        object.__setattr__(self, "final_sha256", self.final_sha256.strip().lower())

    @property
    def evidence_id(self) -> str:
        return f"TSAE-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "shot_id": self.shot_id,
            "source_span_plan_id": self.source_span_plan_id,
            "source_span_plan_fingerprint": self.source_span_plan_fingerprint,
            "span_ids": list(self.span_ids),
            "span_paths": list(self.span_paths),
            "span_frame_counts": list(self.span_frame_counts),
            "final_path": self.final_path,
            "final_frame_count": self.final_frame_count,
            "width": self.width,
            "height": self.height,
            "frames_per_second": self.frames_per_second,
            "final_sha256": self.final_sha256,
            "recorded_at": self.recorded_at,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["evidence_id"] = self.evidence_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TimedSpanAssemblyEvidence:
        evidence = cls(
            shot_id=str(raw.get("shot_id") or ""),
            source_span_plan_id=str(raw.get("source_span_plan_id") or ""),
            source_span_plan_fingerprint=str(raw.get("source_span_plan_fingerprint") or ""),
            span_ids=_string_tuple(raw, "span_ids"),
            span_paths=_string_tuple(raw, "span_paths"),
            span_frame_counts=_int_tuple(raw, "span_frame_counts"),
            final_path=str(raw.get("final_path") or ""),
            final_frame_count=_required_int(raw, "final_frame_count"),
            width=_required_int(raw, "width"),
            height=_required_int(raw, "height"),
            frames_per_second=_required_int(raw, "frames_per_second"),
            final_sha256=str(raw.get("final_sha256") or ""),
            recorded_at=str(raw.get("recorded_at") or ""),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied_id = str(raw.get("evidence_id") or "").strip()
        if supplied_id and supplied_id != evidence.evidence_id:
            raise TimedSpanAcceptanceError(
                "Timed-span assembly evidence identity does not match governed content"
            )
        return evidence


@dataclass(frozen=True, slots=True)
class TimedSpanAcceptanceStatus:
    """Operator summary for one current compiled dynamic Shot."""

    shot_id: str
    state: TimedSpanAcceptanceState
    span_count: int
    boundary_count: int
    requirement_count: int
    approved_keyframe_count: int
    qc_passed_count: int
    assembly_present: bool
    final_frame_count: int | None = None
    message: str = ""

    @property
    def applicable(self) -> bool:
        return self.state is not TimedSpanAcceptanceState.NOT_APPLICABLE

    @property
    def accepted(self) -> bool:
        return self.state is TimedSpanAcceptanceState.ACCEPTED


class TimedSpanAcceptanceStore:
    """Persist human QC and assembly evidence without changing production authority."""

    RELATIVE_PATH = Path(".vscs") / "timed_span_acceptance.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def qc_for_requirement(self, requirement_id: str) -> TimedSpanVisualQCRecord | None:
        for raw in self._root().get("qc_records", []):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("requirement_id") or "").strip() == requirement_id.strip():
                return TimedSpanVisualQCRecord.from_dict(raw)
        return None

    def save_qc(self, record: TimedSpanVisualQCRecord) -> TimedSpanVisualQCRecord:
        root = self._root()
        records = [
            dict(item)
            for item in root.get("qc_records", [])
            if isinstance(item, dict)
            and str(item.get("requirement_id") or "").strip() != record.requirement_id
        ]
        records.append(record.to_dict())
        root["qc_records"] = records
        self._write(root)
        stored = self.qc_for_requirement(record.requirement_id)
        assert stored is not None
        return stored

    def assembly_for_shot(self, shot_id: str) -> TimedSpanAssemblyEvidence | None:
        normalized = shot_id.strip().upper()
        for raw in self._root().get("assemblies", []):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("shot_id") or "").strip().upper() == normalized:
                return TimedSpanAssemblyEvidence.from_dict(raw)
        return None

    def save_assembly(self, evidence: TimedSpanAssemblyEvidence) -> TimedSpanAssemblyEvidence:
        root = self._root()
        assemblies = [
            dict(item)
            for item in root.get("assemblies", [])
            if isinstance(item, dict)
            and str(item.get("shot_id") or "").strip().upper() != evidence.shot_id
        ]
        assemblies.append(evidence.to_dict())
        root["assemblies"] = assemblies
        self._write(root)
        stored = self.assembly_for_shot(evidence.shot_id)
        assert stored is not None
        return stored

    def _root(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema_version": "1.0", "qc_records": [], "assemblies": []}
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise TimedSpanAcceptanceError(
                f"Cannot read timed-span acceptance authority: {exc}"
            ) from exc
        if not isinstance(root, dict):
            raise TimedSpanAcceptanceError("Timed-span acceptance store root must be an object")
        qc = root.get("qc_records", [])
        assemblies = root.get("assemblies", [])
        if not isinstance(qc, list) or not isinstance(assemblies, list):
            raise TimedSpanAcceptanceError("Timed-span acceptance store is invalid")
        return dict(root)

    def _write(self, root: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(root, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class TimedSpanAcceptanceEvaluator:
    """Evaluate current 3.1-3.5 authority into one operator-visible acceptance state."""

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)
        self.acceptance = TimedSpanAcceptanceStore(self.project_directory)

    def evaluate(self, compiled_package: dict[str, Any]) -> TimedSpanAcceptanceStatus:
        shot_id = _shot_id(compiled_package)
        spans_raw = compiled_package.get("internal_render_spans")
        requirements_raw = compiled_package.get("introduction_keyframe_requirements")
        if not isinstance(spans_raw, dict):
            return TimedSpanAcceptanceStatus(
                shot_id=shot_id,
                state=TimedSpanAcceptanceState.NOT_APPLICABLE,
                span_count=1,
                boundary_count=0,
                requirement_count=0,
                approved_keyframe_count=0,
                qc_passed_count=0,
                assembly_present=False,
                message="Shot has no governed internal render-span authority.",
            )
        try:
            spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
        except GovernedInternalRenderSpanError as exc:
            return self._failed(shot_id, f"Internal render-span authority is invalid: {exc}")
        if spans.span_count <= 1:
            return TimedSpanAcceptanceStatus(
                shot_id=shot_id,
                state=TimedSpanAcceptanceState.NOT_APPLICABLE,
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
                requirement_count=0,
                approved_keyframe_count=0,
                qc_passed_count=0,
                assembly_present=False,
                message="Shot is monolithic and does not require timed-span acceptance.",
            )
        if not isinstance(requirements_raw, dict):
            return self._failed(
                shot_id,
                "Dynamic Shot has no Governed Introduction Keyframe requirement authority.",
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
            )
        try:
            requirements = IntroductionKeyframeRequirementPlan.from_dict(requirements_raw)
        except GovernedIntroductionKeyframeError as exc:
            return self._failed(
                shot_id,
                f"Introduction Keyframe requirement authority is invalid: {exc}",
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
            )
        if requirements.requirement_count != len(spans.boundaries):
            return self._failed(
                shot_id,
                "Each internal boundary must have exactly one Introduction Keyframe requirement.",
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
                requirement_count=requirements.requirement_count,
            )

        approved = 0
        qc_passed = 0
        for requirement in requirements.requirements:
            try:
                self.keyframes.require_approved(requirement)
                approved += 1
            except GovernedIntroductionKeyframeError:
                continue
            qc = self.acceptance.qc_for_requirement(requirement.requirement_id)
            if qc is not None and self._qc_matches(requirement, qc) and qc.passed:
                qc_passed += 1

        assembly = self.acceptance.assembly_for_shot(shot_id)
        assembly_valid = assembly is not None and self._assembly_matches(spans, assembly)
        if approved < requirements.requirement_count:
            return TimedSpanAcceptanceStatus(
                shot_id=shot_id,
                state=TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
                requirement_count=requirements.requirement_count,
                approved_keyframe_count=approved,
                qc_passed_count=qc_passed,
                assembly_present=assembly_valid,
                final_frame_count=assembly.final_frame_count if assembly_valid else None,
                message=(
                    f"{requirements.requirement_count - approved} governed Introduction "
                    "Keyframe approval(s) remain."
                ),
            )
        if not assembly_valid:
            return TimedSpanAcceptanceStatus(
                shot_id=shot_id,
                state=TimedSpanAcceptanceState.OUTPUTS_REQUIRED,
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
                requirement_count=requirements.requirement_count,
                approved_keyframe_count=approved,
                qc_passed_count=qc_passed,
                assembly_present=False,
                message="Normalized span outputs must be verified and assembled.",
            )
        if qc_passed < requirements.requirement_count:
            return TimedSpanAcceptanceStatus(
                shot_id=shot_id,
                state=TimedSpanAcceptanceState.QC_REQUIRED,
                span_count=spans.span_count,
                boundary_count=len(spans.boundaries),
                requirement_count=requirements.requirement_count,
                approved_keyframe_count=approved,
                qc_passed_count=qc_passed,
                assembly_present=True,
                final_frame_count=assembly.final_frame_count,
                message=(
                    f"{requirements.requirement_count - qc_passed} visual introduction-boundary "
                    "QC approval(s) remain."
                ),
            )
        return TimedSpanAcceptanceStatus(
            shot_id=shot_id,
            state=TimedSpanAcceptanceState.ACCEPTED,
            span_count=spans.span_count,
            boundary_count=len(spans.boundaries),
            requirement_count=requirements.requirement_count,
            approved_keyframe_count=approved,
            qc_passed_count=qc_passed,
            assembly_present=True,
            final_frame_count=assembly.final_frame_count,
            message="Timed-span functional acceptance passed.",
        )

    @staticmethod
    def make_qc_record(
        requirement: Any,
        *,
        absent_before_boundary: bool,
        present_from_target_frame: bool,
        source_continuity_preserved: bool,
        no_unapproved_assets: bool,
        approved_by: str,
        notes: str = "",
        approved_at: str | None = None,
    ) -> TimedSpanVisualQCRecord:
        return TimedSpanVisualQCRecord(
            shot_id=requirement.shot_id,
            requirement_id=requirement.requirement_id,
            boundary_id=requirement.boundary_id,
            source_global_frame_index=requirement.source_global_frame_index,
            target_global_frame_index=requirement.target_global_frame_index,
            introduced_asset_ids=requirement.introduced_asset_ids,
            absent_before_boundary=absent_before_boundary,
            present_from_target_frame=present_from_target_frame,
            source_continuity_preserved=source_continuity_preserved,
            no_unapproved_assets=no_unapproved_assets,
            approved_by=approved_by.strip(),
            approved_at=approved_at or datetime.now(UTC).isoformat(),
            notes=notes.strip(),
        )

    @staticmethod
    def _qc_matches(requirement: Any, record: TimedSpanVisualQCRecord) -> bool:
        return (
            record.shot_id == requirement.shot_id
            and record.requirement_id == requirement.requirement_id
            and record.boundary_id == requirement.boundary_id
            and record.source_global_frame_index == requirement.source_global_frame_index
            and record.target_global_frame_index == requirement.target_global_frame_index
            and record.introduced_asset_ids == requirement.introduced_asset_ids
        )

    @staticmethod
    def _assembly_matches(
        spans: GovernedInternalRenderSpanPlan,
        evidence: TimedSpanAssemblyEvidence,
    ) -> bool:
        return (
            evidence.shot_id == spans.shot_id
            and evidence.source_span_plan_id == spans.plan_id
            and evidence.source_span_plan_fingerprint == spans.fingerprint
            and evidence.span_ids == tuple(span.span_id for span in spans.spans)
            and evidence.span_frame_counts == tuple(span.frame_count for span in spans.spans)
            and evidence.final_frame_count == spans.frame_count
            and evidence.width > 0
            and evidence.height > 0
            and evidence.frames_per_second == spans.frames_per_second
        )

    @staticmethod
    def _failed(
        shot_id: str,
        message: str,
        *,
        span_count: int = 0,
        boundary_count: int = 0,
        requirement_count: int = 0,
    ) -> TimedSpanAcceptanceStatus:
        return TimedSpanAcceptanceStatus(
            shot_id=shot_id,
            state=TimedSpanAcceptanceState.FAILED,
            span_count=span_count,
            boundary_count=boundary_count,
            requirement_count=requirement_count,
            approved_keyframe_count=0,
            qc_passed_count=0,
            assembly_present=False,
            message=message,
        )


def _shot_id(compiled_package: dict[str, Any]) -> str:
    raw = compiled_package.get("shot_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().upper()
    manifest = compiled_package.get("_vscs_manifest")
    if isinstance(manifest, dict):
        value = str(manifest.get("shot_id") or "").strip().upper()
        if value:
            return value
    composition = compiled_package.get("composition_plan")
    if isinstance(composition, dict):
        value = str(composition.get("shot_id") or "").strip().upper()
        if value:
            return value
    return "SHOT-UNKNOWN"


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise TimedSpanAcceptanceError(f"{key} must be an integer")


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if isinstance(value, bool):
        return value
    raise TimedSpanAcceptanceError(f"{key} must be a boolean")


def _string_tuple(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list | tuple):
        raise TimedSpanAcceptanceError(f"{key} must be an array")
    result = tuple(str(item).strip() for item in value)
    if any(not item for item in result):
        raise TimedSpanAcceptanceError(f"{key} cannot contain blank values")
    return result


def _int_tuple(raw: dict[str, Any], key: str) -> tuple[int, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list | tuple):
        raise TimedSpanAcceptanceError(f"{key} must be an array")
    result: list[int] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            raise TimedSpanAcceptanceError(f"{key} must contain integers")
        result.append(item)
    return tuple(result)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
