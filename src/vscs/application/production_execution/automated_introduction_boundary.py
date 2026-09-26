"""Automated internal-boundary synthesis authority for Phase 20.18.2.3.6."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .introduction_keyframes import IntroductionKeyframeRequirement


class AutomatedIntroductionBoundaryError(RuntimeError):
    """Raised when automated introduction-boundary authority is invalid or stale."""


class IntroductionBoundaryStrategy(StrEnum):
    """Provider-neutral strategy selected for one governed asset introduction."""

    DIRECT_PROVIDER_REFERENCE = "direct_provider_reference"
    SYNTHESIZED_KEYFRAME = "synthesized_keyframe"
    MANUAL_FALLBACK = "manual_fallback"


class AutomatedBoundaryValidationState(StrEnum):
    """Machine-verifiable state of one synthesized introduction image."""

    PASSED = "passed"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IntroductionBoundaryProviderCapabilities:
    """Capabilities used to choose the least-manual governed introduction strategy."""

    provider_id: str
    direct_timed_reference_asset_kinds: frozenset[str] = frozenset()
    supports_reference_aware_image_synthesis: bool = False

    def strategy_for(self, introduced_asset_kinds: tuple[str, ...]) -> IntroductionBoundaryStrategy:
        normalized = tuple(value.strip().casefold() for value in introduced_asset_kinds)
        if normalized and all(
            value in self.direct_timed_reference_asset_kinds for value in normalized
        ):
            return IntroductionBoundaryStrategy.DIRECT_PROVIDER_REFERENCE
        if self.supports_reference_aware_image_synthesis:
            return IntroductionBoundaryStrategy.SYNTHESIZED_KEYFRAME
        return IntroductionBoundaryStrategy.MANUAL_FALLBACK


@dataclass(frozen=True, slots=True)
class AutomatedIntroductionBoundaryRequest:
    """Exact source/target authority for automated frame synthesis."""

    shot_id: str
    requirement_id: str
    boundary_id: str
    source_span_id: str
    target_span_id: str
    source_global_frame_index: int
    target_global_frame_index: int
    source_boundary_image_path: str
    source_boundary_image_sha256: str
    introduced_asset_ids: tuple[str, ...]
    introduced_asset_kinds: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    introduced_reference_paths: tuple[str, ...]
    introduced_reference_sha256: tuple[str, ...]
    active_asset_ids: tuple[str, ...]
    active_reference_ids: tuple[str, ...]
    width: int
    height: int
    positive_prompt: str
    negative_prompt: str
    seed: int
    source_package_fingerprint: str
    strategy: IntroductionBoundaryStrategy = IntroductionBoundaryStrategy.SYNTHESIZED_KEYFRAME
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction boundary requires shot_id"
            )
        object.__setattr__(self, "shot_id", shot_id)
        for field_name in (
            "requirement_id",
            "boundary_id",
            "source_span_id",
            "target_span_id",
            "source_boundary_image_path",
            "source_boundary_image_sha256",
            "source_package_fingerprint",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise AutomatedIntroductionBoundaryError(
                    f"Automated introduction boundary requires {field_name}"
                )
            if field_name.endswith("sha256") or field_name.endswith("fingerprint"):
                value = value.lower()
            object.__setattr__(self, field_name, value)
        if self.source_global_frame_index < 0:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction source frame cannot be negative"
            )
        if self.target_global_frame_index != self.source_global_frame_index + 1:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction target frame must immediately follow source boundary"
            )
        if self.width <= 0 or self.height <= 0:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction target dimensions must be positive"
            )
        if self.seed < 0:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction synthesis seed cannot be negative"
            )
        for field_name in (
            "introduced_asset_ids",
            "introduced_asset_kinds",
            "introduced_reference_ids",
            "introduced_reference_paths",
            "introduced_reference_sha256",
            "active_asset_ids",
            "active_reference_ids",
        ):
            values = tuple(str(value).strip() for value in getattr(self, field_name))
            if any(not value for value in values):
                raise AutomatedIntroductionBoundaryError(
                    f"Automated introduction {field_name} cannot contain blank values"
                )
            if len(set(values)) != len(values):
                raise AutomatedIntroductionBoundaryError(
                    f"Automated introduction {field_name} cannot contain duplicates"
                )
            object.__setattr__(self, field_name, values)
        if not self.introduced_asset_ids:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction requires at least one introduced asset"
            )
        if len(self.introduced_asset_ids) != len(self.introduced_asset_kinds):
            raise AutomatedIntroductionBoundaryError(
                "Introduced asset IDs and kinds must have matching cardinality"
            )
        if not (
            len(self.introduced_reference_ids)
            == len(self.introduced_reference_paths)
            == len(self.introduced_reference_sha256)
        ):
            raise AutomatedIntroductionBoundaryError(
                "Introduced reference IDs, paths and checksums must have matching cardinality"
            )
        if not set(self.introduced_asset_ids).issubset(set(self.active_asset_ids)):
            raise AutomatedIntroductionBoundaryError(
                "Introduced assets must be active in the target span"
            )
        if not set(self.introduced_reference_ids).issubset(set(self.active_reference_ids)):
            raise AutomatedIntroductionBoundaryError(
                "Introduced references must be active in the target span"
            )
        if self.strategy is IntroductionBoundaryStrategy.SYNTHESIZED_KEYFRAME:
            if not self.introduced_reference_ids:
                raise AutomatedIntroductionBoundaryError(
                    "Synthesized introduction boundary requires canonical introduced references"
                )
            if not self.positive_prompt.strip() or not self.negative_prompt.strip():
                raise AutomatedIntroductionBoundaryError(
                    "Synthesized introduction boundary requires positive and negative prompts"
                )

    @property
    def request_id(self) -> str:
        return f"AIBR-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "shot_id": self.shot_id,
            "requirement_id": self.requirement_id,
            "boundary_id": self.boundary_id,
            "source_span_id": self.source_span_id,
            "target_span_id": self.target_span_id,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "source_boundary_image_path": self.source_boundary_image_path,
            "source_boundary_image_sha256": self.source_boundary_image_sha256,
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "introduced_asset_kinds": list(self.introduced_asset_kinds),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "introduced_reference_paths": list(self.introduced_reference_paths),
            "introduced_reference_sha256": list(self.introduced_reference_sha256),
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "width": self.width,
            "height": self.height,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "seed": self.seed,
            "source_package_fingerprint": self.source_package_fingerprint,
            "strategy": self.strategy.value,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["request_id"] = self.request_id
        return payload


@dataclass(frozen=True, slots=True)
class AutomatedIntroductionBoundaryResult:
    """Provider result and machine-verifiable evidence for one synthesized boundary frame."""

    request_id: str
    requirement_id: str
    image_path: str
    image_sha256: str
    provider_name: str
    model: str
    source_boundary_image_path: str
    source_boundary_image_sha256: str
    introduced_reference_ids: tuple[str, ...]
    width: int
    height: int
    generated_at: str
    validation_state: AutomatedBoundaryValidationState
    validation_findings: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "requirement_id",
            "image_path",
            "image_sha256",
            "provider_name",
            "source_boundary_image_path",
            "source_boundary_image_sha256",
            "generated_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise AutomatedIntroductionBoundaryError(
                    f"Automated introduction result requires {field_name}"
                )
            if field_name.endswith("sha256"):
                value = value.lower()
            object.__setattr__(self, field_name, value)
        refs = tuple(str(value).strip() for value in self.introduced_reference_ids)
        if any(not value for value in refs) or len(set(refs)) != len(refs):
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction result reference IDs must be unique and non-blank"
            )
        object.__setattr__(self, "introduced_reference_ids", refs)
        findings = tuple(
            str(value).strip() for value in self.validation_findings if str(value).strip()
        )
        object.__setattr__(self, "validation_findings", findings)
        if self.width <= 0 or self.height <= 0:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction result dimensions must be positive"
            )

    @property
    def result_id(self) -> str:
        return f"AIBS-{_fingerprint(self._authority_payload())[:16].upper()}"

    @property
    def usable_without_manual_image_authoring(self) -> bool:
        return self.validation_state in {
            AutomatedBoundaryValidationState.PASSED,
            AutomatedBoundaryValidationState.HUMAN_REVIEW_REQUIRED,
        }

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "requirement_id": self.requirement_id,
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "provider_name": self.provider_name,
            "model": self.model,
            "source_boundary_image_path": self.source_boundary_image_path,
            "source_boundary_image_sha256": self.source_boundary_image_sha256,
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "width": self.width,
            "height": self.height,
            "generated_at": self.generated_at,
            "validation_state": self.validation_state.value,
            "validation_findings": list(self.validation_findings),
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["result_id"] = self.result_id
        return payload


class AutomatedIntroductionBoundaryStore:
    """Append-only audit store for automatic source extraction and synthesis."""

    RELATIVE_PATH = Path(".vscs") / "automated_introduction_boundaries.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def save_request(
        self,
        request: AutomatedIntroductionBoundaryRequest,
    ) -> AutomatedIntroductionBoundaryRequest:
        root = self._root()
        rows = [dict(item) for item in root.get("requests", []) if isinstance(item, dict)]
        if not any(str(item.get("request_id") or "") == request.request_id for item in rows):
            rows.append(request.to_dict())
        root["requests"] = rows
        self._write(root)
        return request

    def save_result(
        self,
        result: AutomatedIntroductionBoundaryResult,
    ) -> AutomatedIntroductionBoundaryResult:
        root = self._root()
        rows = [dict(item) for item in root.get("results", []) if isinstance(item, dict)]
        if not any(str(item.get("result_id") or "") == result.result_id for item in rows):
            rows.append(result.to_dict())
        root["results"] = rows
        self._write(root)
        return result

    def latest_result_for_requirement(
        self,
        requirement_id: str,
    ) -> AutomatedIntroductionBoundaryResult | None:
        normalized = requirement_id.strip()
        for raw in reversed(self._root().get("results", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("requirement_id") or "").strip() != normalized:
                continue
            return AutomatedIntroductionBoundaryResult(
                request_id=str(raw.get("request_id") or ""),
                requirement_id=str(raw.get("requirement_id") or ""),
                image_path=str(raw.get("image_path") or ""),
                image_sha256=str(raw.get("image_sha256") or ""),
                provider_name=str(raw.get("provider_name") or ""),
                model=str(raw.get("model") or ""),
                source_boundary_image_path=str(raw.get("source_boundary_image_path") or ""),
                source_boundary_image_sha256=str(raw.get("source_boundary_image_sha256") or ""),
                introduced_reference_ids=tuple(
                    str(value) for value in raw.get("introduced_reference_ids", [])
                ),
                width=int(raw.get("width") or 0),
                height=int(raw.get("height") or 0),
                generated_at=str(raw.get("generated_at") or ""),
                validation_state=AutomatedBoundaryValidationState(
                    str(raw.get("validation_state") or "")
                ),
                validation_findings=tuple(
                    str(value) for value in raw.get("validation_findings", [])
                ),
                schema_version=str(raw.get("schema_version") or "1.0"),
            )
        return None

    def _root(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema_version": "1.0", "requests": [], "results": []}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedIntroductionBoundaryError(
                f"Cannot read automated introduction-boundary store: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction-boundary store root must be an object"
            )
        return dict(raw)

    def _write(self, root: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(root, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def request_from_requirement(
    requirement: IntroductionKeyframeRequirement,
    *,
    source_boundary_image_path: Path,
    source_boundary_image_sha256: str,
    reference_plan: dict[str, Any],
    timed_asset_presence: dict[str, Any],
    width: int,
    height: int,
    source_package_fingerprint: str,
    seed: int,
) -> AutomatedIntroductionBoundaryRequest:
    """Compile one synthesis request from existing governed structural authority."""
    references_raw = reference_plan.get("references")
    if not isinstance(references_raw, list):
        raise AutomatedIntroductionBoundaryError(
            "Automated introduction synthesis requires governed ReferencePlan references"
        )
    references = {
        str(item.get("reference_id") or "").strip(): item
        for item in references_raw
        if isinstance(item, dict) and str(item.get("reference_id") or "").strip()
    }
    introduced_paths: list[str] = []
    introduced_sha256: list[str] = []
    for reference_id in requirement.introduced_reference_ids:
        reference = references.get(reference_id)
        if reference is None:
            raise AutomatedIntroductionBoundaryError(
                f"Introduced governed reference is missing from ReferencePlan: {reference_id}"
            )
        source_path = str(reference.get("source_path") or "").strip()
        if not source_path:
            raise AutomatedIntroductionBoundaryError(
                f"Introduced governed reference has no source_path: {reference_id}"
            )
        checksum = str(reference.get("file_checksum") or "").strip().lower()
        if not checksum:
            raise AutomatedIntroductionBoundaryError(
                f"Introduced governed reference has no file_checksum: {reference_id}"
            )
        introduced_paths.append(source_path)
        introduced_sha256.append(checksum)

    presences_raw = timed_asset_presence.get("presences")
    if not isinstance(presences_raw, list):
        raise AutomatedIntroductionBoundaryError(
            "Automated introduction synthesis requires Timed Asset Presence intervals"
        )
    presence_by_asset = {
        str(item.get("asset_id") or "").strip(): item
        for item in presences_raw
        if isinstance(item, dict) and str(item.get("asset_id") or "").strip()
    }
    introduced_kinds = tuple(
        str(presence_by_asset.get(asset_id, {}).get("asset_kind") or "other").strip()
        for asset_id in requirement.introduced_asset_ids
    )
    introduction_events = tuple(
        str(presence_by_asset.get(asset_id, {}).get("introduction") or "appear").strip().casefold()
        for asset_id in requirement.introduced_asset_ids
    )
    labels = tuple(
        str(references[reference_id].get("label") or reference_id).strip()
        for reference_id in requirement.introduced_reference_ids
    )
    subject_text = ", ".join(labels)
    if introduction_events and all(event == "enter" for event in introduction_events):
        transition_instruction = (
            "This is an ENTER transition, not an appearance. Show the introduced character only "
            "in the first visible phase of the physical entrance: just becoming visible from a plausible "
            "edge, doorway, or access route, with part of the body still outside the established "
            "scene and a natural walking-in pose. Do not place the character fully arrived, "
            "centered, standing still, or suddenly materialized in the scene."
        )
    else:
        transition_instruction = (
            "The introduced asset must be newly visible from this frame and naturally integrated "
            "into the existing scene."
        )
    positive = (
        "Edit the source boundary frame minimally. Preserve the existing camera, framing, "
        "lighting, environment, existing people and objects, identities, positions, scale, "
        "wardrobe, and spatial continuity. Introduce the exact canonical asset shown in the "
        f"supplied reference image at this governed transition: {subject_text}. "
        f"{transition_instruction} "
        "Do not replace, duplicate, move, or redesign existing subjects. Keep the output "
        "photorealistic and preserve the source image geometry."
    )
    negative = (
        "identity drift, changed existing face, changed wardrobe, moved existing subject, "
        "duplicate person, extra person, extra object, removed subject, camera change, zoom, "
        "reframe, lighting change, environment change, scene cut, split screen, contact sheet, "
        "text overlay, redesign, teleportation, sudden full-body appearance"
    )
    return AutomatedIntroductionBoundaryRequest(
        shot_id=requirement.shot_id,
        requirement_id=requirement.requirement_id,
        boundary_id=requirement.boundary_id,
        source_span_id=requirement.source_span_id,
        target_span_id=requirement.target_span_id,
        source_global_frame_index=requirement.source_global_frame_index,
        target_global_frame_index=requirement.target_global_frame_index,
        source_boundary_image_path=str(source_boundary_image_path),
        source_boundary_image_sha256=source_boundary_image_sha256,
        introduced_asset_ids=requirement.introduced_asset_ids,
        introduced_asset_kinds=introduced_kinds,
        introduced_reference_ids=requirement.introduced_reference_ids,
        introduced_reference_paths=tuple(introduced_paths),
        introduced_reference_sha256=tuple(introduced_sha256),
        active_asset_ids=requirement.active_asset_ids,
        active_reference_ids=requirement.active_reference_ids,
        width=width,
        height=height,
        positive_prompt=positive,
        negative_prompt=negative,
        seed=seed,
        source_package_fingerprint=source_package_fingerprint,
    )


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
