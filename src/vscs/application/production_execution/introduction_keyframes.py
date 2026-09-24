"""Governed introduction-keyframe authority for Phase 20.18.2.3.4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .internal_render_spans import GovernedInternalRenderSpanPlan
from .timed_reference_activation import TimedCanonicalReferenceActivationPlan


class GovernedIntroductionKeyframeError(RuntimeError):
    """Raised when introduction-keyframe authority is missing, stale, or unsafe."""


INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA = (
    "source_boundary_continuity_preserved",
    "target_span_first_emitted_frame_correct",
    "introduced_assets_present",
    "active_identities_preserved",
    "no_unapproved_assets_introduced",
    "composition_physically_plausible",
)


@dataclass(frozen=True, slots=True)
class IntroductionKeyframeRequirement:
    """Required human-approved opening frame for one non-initial internal span."""

    shot_id: str
    boundary_id: str
    source_span_id: str
    target_span_id: str
    source_global_frame_index: int
    target_global_frame_index: int
    target_through_frame: int
    active_asset_ids: tuple[str, ...]
    active_reference_ids: tuple[str, ...]
    introduced_asset_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    source_span_plan_fingerprint: str
    source_activation_plan_fingerprint: str

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement requires shot_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        for field_name in ("boundary_id", "source_span_id", "target_span_id"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise GovernedIntroductionKeyframeError(
                    f"Introduction-keyframe requirement requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

        if self.source_global_frame_index < 0:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe source frame cannot be negative"
            )
        if self.target_global_frame_index != self.source_global_frame_index + 1:
            raise GovernedIntroductionKeyframeError(
                "Introduction keyframe must represent the first frame after its source boundary"
            )
        if self.target_through_frame < self.target_global_frame_index:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe target interval is invalid"
            )

        for field_name in (
            "active_asset_ids",
            "active_reference_ids",
            "introduced_asset_ids",
            "introduced_reference_ids",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise GovernedIntroductionKeyframeError(
                    f"Introduction-keyframe {field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise GovernedIntroductionKeyframeError(
                    f"Introduction-keyframe {field_name} cannot contain duplicates"
                )
            object.__setattr__(self, field_name, values)

        if not set(self.introduced_asset_ids).issubset(set(self.active_asset_ids)):
            raise GovernedIntroductionKeyframeError(
                "Introduced assets must be active in the target span"
            )
        if not set(self.introduced_reference_ids).issubset(set(self.active_reference_ids)):
            raise GovernedIntroductionKeyframeError(
                "Introduced references must be active in the target span"
            )

        for field_name in (
            "source_span_plan_fingerprint",
            "source_activation_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise GovernedIntroductionKeyframeError(
                    f"Introduction-keyframe requirement requires {field_name}"
                )
            object.__setattr__(self, field_name, value)

    @property
    def target_frame_count(self) -> int:
        return self.target_through_frame - self.target_global_frame_index + 1

    @property
    def requirement_id(self) -> str:
        return f"GIKR-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "shot_id": self.shot_id,
            "boundary_id": self.boundary_id,
            "source_span_id": self.source_span_id,
            "target_span_id": self.target_span_id,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "target_through_frame": self.target_through_frame,
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "source_span_plan_fingerprint": self.source_span_plan_fingerprint,
            "source_activation_plan_fingerprint": self.source_activation_plan_fingerprint,
            "conditioning_semantics": {
                "conditioning_frame_global_index": self.target_global_frame_index,
                "conditioning_frame_is_emitted": True,
                "preceding_boundary_frame_global_index": self.source_global_frame_index,
                "preceding_boundary_frame_reemitted_in_target_span": False,
            },
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["requirement_id"] = self.requirement_id
        payload["target_frame_count"] = self.target_frame_count
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IntroductionKeyframeRequirement:
        requirement = cls(
            shot_id=str(raw.get("shot_id") or ""),
            boundary_id=str(raw.get("boundary_id") or ""),
            source_span_id=str(raw.get("source_span_id") or ""),
            target_span_id=str(raw.get("target_span_id") or ""),
            source_global_frame_index=_required_int(raw, "source_global_frame_index"),
            target_global_frame_index=_required_int(raw, "target_global_frame_index"),
            target_through_frame=_required_int(raw, "target_through_frame"),
            active_asset_ids=_string_tuple(raw, "active_asset_ids"),
            active_reference_ids=_string_tuple(raw, "active_reference_ids"),
            introduced_asset_ids=_string_tuple(raw, "introduced_asset_ids"),
            introduced_reference_ids=_string_tuple(raw, "introduced_reference_ids"),
            source_span_plan_fingerprint=str(raw.get("source_span_plan_fingerprint") or ""),
            source_activation_plan_fingerprint=str(
                raw.get("source_activation_plan_fingerprint") or ""
            ),
        )
        supplied_id = str(raw.get("requirement_id") or "").strip()
        if supplied_id and supplied_id != requirement.requirement_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement identity does not match governed content"
            )
        supplied_count = raw.get("target_frame_count")
        if supplied_count is not None and _integer_value(
            supplied_count, "target_frame_count"
        ) != requirement.target_frame_count:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe target_frame_count does not match target interval"
            )
        semantics = raw.get("conditioning_semantics")
        if semantics is not None:
            if not isinstance(semantics, dict):
                raise GovernedIntroductionKeyframeError(
                    "Introduction-keyframe conditioning_semantics must be an object"
                )
            expected = requirement._authority_payload()["conditioning_semantics"]
            if semantics != expected:
                raise GovernedIntroductionKeyframeError(
                    "Introduction-keyframe conditioning semantics were changed"
                )
        return requirement


@dataclass(frozen=True, slots=True)
class IntroductionKeyframeRequirementPlan:
    """Deterministic requirements for every non-initial internal render span."""

    shot_id: str
    source_span_plan_id: str
    source_span_plan_fingerprint: str
    source_activation_plan_id: str
    source_activation_plan_fingerprint: str
    requirements: tuple[IntroductionKeyframeRequirement, ...]
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement plan requires shot_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        if self.schema_version != "1.0":
            raise GovernedIntroductionKeyframeError(
                f"Unsupported introduction-keyframe requirement schema: {self.schema_version!r}"
            )
        if self.provider_neutral is not True:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement authority must remain provider-neutral"
            )
        for field_name in (
            "source_span_plan_id",
            "source_span_plan_fingerprint",
            "source_activation_plan_id",
            "source_activation_plan_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise GovernedIntroductionKeyframeError(
                    f"Introduction-keyframe requirement plan requires {field_name}"
                )
            if field_name.endswith("fingerprint"):
                value = value.lower()
            object.__setattr__(self, field_name, value)
        ids = [item.requirement_id for item in self.requirements]
        if len(set(ids)) != len(ids):
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement identities must be unique"
            )

    @property
    def requirement_count(self) -> int:
        return len(self.requirements)

    @property
    def plan_id(self) -> str:
        return f"GIKRPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self._authority_payload())

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "provider_neutral": self.provider_neutral,
            "shot_id": self.shot_id,
            "source_internal_render_spans": {
                "plan_id": self.source_span_plan_id,
                "fingerprint": self.source_span_plan_fingerprint,
            },
            "source_timed_reference_activation": {
                "plan_id": self.source_activation_plan_id,
                "fingerprint": self.source_activation_plan_fingerprint,
            },
            "requirement_count": self.requirement_count,
            "requirements": [item.to_dict() for item in self.requirements],
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["plan_id"] = self.plan_id
        payload["fingerprint"] = self.fingerprint
        return payload

    def require_sources(
        self,
        spans: GovernedInternalRenderSpanPlan,
        activation: TimedCanonicalReferenceActivationPlan,
    ) -> None:
        if spans.shot_id != self.shot_id or activation.shot_id != self.shot_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement Shot identity changed"
            )
        if spans.plan_id != self.source_span_plan_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe source span plan identity changed"
            )
        if spans.fingerprint != self.source_span_plan_fingerprint:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe source span plan fingerprint changed"
            )
        if activation.plan_id != self.source_activation_plan_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe source activation identity changed"
            )
        if activation.fingerprint != self.source_activation_plan_fingerprint:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe source activation fingerprint changed"
            )
        expected = GovernedIntroductionKeyframeRequirementCompiler().compile(
            spans,
            activation,
        )
        if expected.fingerprint != self.fingerprint:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirements no longer match source authority"
            )

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IntroductionKeyframeRequirementPlan:
        spans = raw.get("source_internal_render_spans")
        activation = raw.get("source_timed_reference_activation")
        requirements_raw = raw.get("requirements")
        if not isinstance(spans, dict):
            raise GovernedIntroductionKeyframeError(
                "source_internal_render_spans must be an object"
            )
        if not isinstance(activation, dict):
            raise GovernedIntroductionKeyframeError(
                "source_timed_reference_activation must be an object"
            )
        if not isinstance(requirements_raw, list):
            raise GovernedIntroductionKeyframeError("requirements must be an array")
        requirements = tuple(
            IntroductionKeyframeRequirement.from_dict(dict(item))
            for item in requirements_raw
            if isinstance(item, dict)
        )
        if len(requirements) != len(requirements_raw):
            raise GovernedIntroductionKeyframeError(
                "Every introduction-keyframe requirement must be an object"
            )
        provider_neutral = raw.get("provider_neutral", True)
        if not isinstance(provider_neutral, bool):
            raise GovernedIntroductionKeyframeError("provider_neutral must be a boolean")
        plan = cls(
            shot_id=str(raw.get("shot_id") or ""),
            source_span_plan_id=str(spans.get("plan_id") or ""),
            source_span_plan_fingerprint=str(spans.get("fingerprint") or ""),
            source_activation_plan_id=str(activation.get("plan_id") or ""),
            source_activation_plan_fingerprint=str(activation.get("fingerprint") or ""),
            requirements=requirements,
            schema_version=str(raw.get("schema_version") or "1.0"),
            provider_neutral=provider_neutral,
        )
        supplied_count = raw.get("requirement_count")
        if supplied_count is not None and _integer_value(
            supplied_count, "requirement_count"
        ) != plan.requirement_count:
            raise GovernedIntroductionKeyframeError(
                "requirement_count does not match persisted requirements"
            )
        supplied_id = str(raw.get("plan_id") or "").strip()
        if supplied_id and supplied_id != plan.plan_id:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement plan identity does not match content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != plan.fingerprint:
            raise GovernedIntroductionKeyframeError(
                "Introduction-keyframe requirement fingerprint does not match content"
            )
        return plan


class GovernedIntroductionKeyframeRequirementCompiler:
    """Derive one introduction-keyframe requirement per internal span transition."""

    def compile(
        self,
        spans: GovernedInternalRenderSpanPlan,
        activation: TimedCanonicalReferenceActivationPlan,
    ) -> IntroductionKeyframeRequirementPlan:
        if spans.shot_id != activation.shot_id:
            raise GovernedIntroductionKeyframeError(
                "Span and reference-activation Shot identities do not match"
            )
        if len(spans.spans) != len(activation.activations):
            raise GovernedIntroductionKeyframeError(
                "Span and reference-activation counts do not match"
            )
        activation_by_span = {
            item.span_id: item for item in activation.activations
        }
        requirements: list[IntroductionKeyframeRequirement] = []
        for boundary in spans.boundaries:
            target = next(
                (item for item in spans.spans if item.span_id == boundary.target_span_id),
                None,
            )
            if target is None:
                raise GovernedIntroductionKeyframeError(
                    f"Internal boundary {boundary.boundary_id} has no target span"
                )
            target_activation = activation_by_span.get(target.span_id)
            if target_activation is None:
                raise GovernedIntroductionKeyframeError(
                    f"Target span {target.span_id} has no timed reference activation"
                )
            if target_activation.start_frame != target.start_frame:
                raise GovernedIntroductionKeyframeError(
                    "Target span activation does not begin on the target span opening frame"
                )
            requirements.append(
                IntroductionKeyframeRequirement(
                    shot_id=spans.shot_id,
                    boundary_id=boundary.boundary_id,
                    source_span_id=boundary.source_span_id,
                    target_span_id=boundary.target_span_id,
                    source_global_frame_index=boundary.source_global_frame_index,
                    target_global_frame_index=boundary.target_global_frame_index,
                    target_through_frame=target.through_frame,
                    active_asset_ids=target.active_asset_ids,
                    active_reference_ids=target_activation.active_reference_ids,
                    introduced_asset_ids=target.introduced_asset_ids,
                    introduced_reference_ids=target_activation.introduced_reference_ids,
                    source_span_plan_fingerprint=spans.fingerprint,
                    source_activation_plan_fingerprint=activation.fingerprint,
                )
            )
        return IntroductionKeyframeRequirementPlan(
            shot_id=spans.shot_id,
            source_span_plan_id=spans.plan_id,
            source_span_plan_fingerprint=spans.fingerprint,
            source_activation_plan_id=activation.plan_id,
            source_activation_plan_fingerprint=activation.fingerprint,
            requirements=tuple(requirements),
        )


@dataclass(frozen=True, slots=True)
class GovernedIntroductionKeyframe:
    """Human-approved image representing the first emitted frame of one target span."""

    keyframe_id: str
    requirement_id: str
    shot_id: str
    boundary_id: str
    target_span_id: str
    target_global_frame_index: int
    image_path: str
    image_sha256: str
    source_boundary_image_path: str
    source_boundary_image_sha256: str
    active_reference_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    approved_by: str
    approved_at: str
    acceptance_criteria: tuple[str, ...]
    status: str = "approved"
    schema_version: str = "1.0"

    @property
    def approved(self) -> bool:
        return (
            self.status == "approved"
            and bool(self.approved_by.strip())
            and bool(self.approved_at.strip())
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "keyframe_id": self.keyframe_id,
            "requirement_id": self.requirement_id,
            "shot_id": self.shot_id,
            "boundary_id": self.boundary_id,
            "target_span_id": self.target_span_id,
            "target_global_frame_index": self.target_global_frame_index,
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "source_boundary_image_path": self.source_boundary_image_path,
            "source_boundary_image_sha256": self.source_boundary_image_sha256,
            "active_reference_ids": list(self.active_reference_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "acceptance_criteria": list(self.acceptance_criteria),
            "status": self.status,
        }


class GovernedIntroductionKeyframeStore:
    """Persist and verify human-approved internal introduction keyframes."""

    RELATIVE_PATH = Path(".vscs") / "governed_introduction_keyframes.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def get(self, requirement_id: str) -> GovernedIntroductionKeyframe | None:
        normalized = requirement_id.strip()
        for raw in self._records():
            if str(raw.get("requirement_id") or "").strip() == normalized:
                return self._from_dict(raw)
        return None

    def require_approved(
        self,
        requirement: IntroductionKeyframeRequirement,
    ) -> GovernedIntroductionKeyframe:
        record = self.get(requirement.requirement_id)
        if record is None:
            raise GovernedIntroductionKeyframeError(
                f"No governed Introduction Keyframe is registered for {requirement.requirement_id}."
            )
        if not record.approved:
            raise GovernedIntroductionKeyframeError(
                f"Governed Introduction Keyframe {record.keyframe_id} is not approved."
            )
        self._require_matches(record, requirement)
        required = set(INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA)
        missing = sorted(required - set(record.acceptance_criteria))
        if missing:
            raise GovernedIntroductionKeyframeError(
                "Governed Introduction Keyframe approval does not cover: "
                + ", ".join(missing)
            )
        self._verify_file(record.image_path, record.image_sha256, "Introduction Keyframe")
        self._verify_file(
            record.source_boundary_image_path,
            record.source_boundary_image_sha256,
            "source boundary image",
        )
        return record

    def save(
        self,
        record: GovernedIntroductionKeyframe,
        requirement: IntroductionKeyframeRequirement,
    ) -> GovernedIntroductionKeyframe:
        self._require_matches(record, requirement)
        self._verify_file(record.image_path, record.image_sha256, "Introduction Keyframe")
        self._verify_file(
            record.source_boundary_image_path,
            record.source_boundary_image_sha256,
            "source boundary image",
        )
        records = [
            raw
            for raw in self._records()
            if str(raw.get("requirement_id") or "").strip() != requirement.requirement_id
        ]
        records.append(record.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {"schema_version": "1.0", "introduction_keyframes": records},
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return self.require_approved(requirement)

    def image_path(self, record: GovernedIntroductionKeyframe) -> Path:
        return self._resolve_project_file(record.image_path)

    @staticmethod
    def create_record(
        requirement: IntroductionKeyframeRequirement,
        *,
        image_path: str,
        image_sha256: str,
        source_boundary_image_path: str,
        source_boundary_image_sha256: str,
        approved_by: str,
        approved_at: str,
        acceptance_criteria: tuple[str, ...] = INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
    ) -> GovernedIntroductionKeyframe:
        payload = {
            "requirement_id": requirement.requirement_id,
            "image_sha256": image_sha256.strip().lower(),
            "source_boundary_image_sha256": source_boundary_image_sha256.strip().lower(),
            "approved_by": approved_by.strip(),
            "approved_at": approved_at.strip(),
        }
        keyframe_id = f"GIK-{_fingerprint(payload)[:16].upper()}"
        return GovernedIntroductionKeyframe(
            keyframe_id=keyframe_id,
            requirement_id=requirement.requirement_id,
            shot_id=requirement.shot_id,
            boundary_id=requirement.boundary_id,
            target_span_id=requirement.target_span_id,
            target_global_frame_index=requirement.target_global_frame_index,
            image_path=image_path.strip(),
            image_sha256=image_sha256.strip().lower(),
            source_boundary_image_path=source_boundary_image_path.strip(),
            source_boundary_image_sha256=source_boundary_image_sha256.strip().lower(),
            active_reference_ids=requirement.active_reference_ids,
            introduced_reference_ids=requirement.introduced_reference_ids,
            approved_by=approved_by.strip(),
            approved_at=approved_at.strip(),
            acceptance_criteria=acceptance_criteria,
        )

    def _require_matches(
        self,
        record: GovernedIntroductionKeyframe,
        requirement: IntroductionKeyframeRequirement,
    ) -> None:
        expected = (
            requirement.requirement_id,
            requirement.shot_id,
            requirement.boundary_id,
            requirement.target_span_id,
            requirement.target_global_frame_index,
            requirement.active_reference_ids,
            requirement.introduced_reference_ids,
        )
        actual = (
            record.requirement_id,
            record.shot_id.strip().upper(),
            record.boundary_id,
            record.target_span_id,
            record.target_global_frame_index,
            record.active_reference_ids,
            record.introduced_reference_ids,
        )
        if actual != expected:
            raise GovernedIntroductionKeyframeError(
                "Governed Introduction Keyframe is stale against its current requirement"
            )

    def _verify_file(self, value: str, checksum: str, label: str) -> None:
        path = self._resolve_project_file(value)
        if not path.is_file():
            raise GovernedIntroductionKeyframeError(f"{label} does not exist: {path}")
        if self._sha256(path) != checksum:
            raise GovernedIntroductionKeyframeError(
                f"{label} checksum no longer matches approved authority"
            )

    def _resolve_project_file(self, value: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.project_directory):
            raise GovernedIntroductionKeyframeError(
                "Governed Introduction Keyframe files must remain inside the project"
            )
        return resolved

    def _records(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GovernedIntroductionKeyframeError(
                f"Cannot read governed Introduction Keyframe authority: {exc}"
            ) from exc
        raw = root.get("introduction_keyframes", []) if isinstance(root, dict) else None
        if not isinstance(raw, list):
            raise GovernedIntroductionKeyframeError(
                "Governed Introduction Keyframe authority store is invalid"
            )
        return [dict(item) for item in raw if isinstance(item, dict)]

    @staticmethod
    def _from_dict(raw: dict[str, object]) -> GovernedIntroductionKeyframe:
        return GovernedIntroductionKeyframe(
            keyframe_id=str(raw.get("keyframe_id") or "").strip(),
            requirement_id=str(raw.get("requirement_id") or "").strip(),
            shot_id=str(raw.get("shot_id") or "").strip().upper(),
            boundary_id=str(raw.get("boundary_id") or "").strip(),
            target_span_id=str(raw.get("target_span_id") or "").strip(),
            target_global_frame_index=_required_int(raw, "target_global_frame_index"),
            image_path=str(raw.get("image_path") or "").strip(),
            image_sha256=str(raw.get("image_sha256") or "").strip().lower(),
            source_boundary_image_path=str(
                raw.get("source_boundary_image_path") or ""
            ).strip(),
            source_boundary_image_sha256=str(
                raw.get("source_boundary_image_sha256") or ""
            ).strip().lower(),
            active_reference_ids=_string_tuple(raw, "active_reference_ids"),
            introduced_reference_ids=_string_tuple(raw, "introduced_reference_ids"),
            approved_by=str(raw.get("approved_by") or "").strip(),
            approved_at=str(raw.get("approved_at") or "").strip(),
            acceptance_criteria=_string_tuple(raw, "acceptance_criteria"),
            status=str(raw.get("status") or "").strip().lower(),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


def _required_int(raw: dict[str, Any] | dict[str, object], key: str) -> int:
    if key not in raw:
        raise GovernedIntroductionKeyframeError(f"Missing required integer field {key!r}")
    return _integer_value(raw[key], key)


def _integer_value(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise GovernedIntroductionKeyframeError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise GovernedIntroductionKeyframeError(
                f"{field_name} must be an integer"
            ) from exc
    raise GovernedIntroductionKeyframeError(f"{field_name} must be an integer")


def _string_tuple(
    raw: dict[str, Any] | dict[str, object],
    key: str,
) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list | tuple):
        raise GovernedIntroductionKeyframeError(f"{key} must be an array")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
