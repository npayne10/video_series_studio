"""Provider-neutral authority contracts for Phase 20.18.2.3.6.2 asset injection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class IntroductionAssetInjectionError(RuntimeError):
    """Raised when identity-locked asset-injection authority is invalid."""


class IntroductionInjectionMode(StrEnum):
    """Governed injection behavior for an introduced asset."""

    CHARACTER_ENTER = "character_enter"


class IntroductionInjectionSide(StrEnum):
    """Governed side from which an injected asset may enter the scene."""

    LEFT = "left"
    RIGHT = "right"
    AUTO = "auto"


class IntroductionInjectionDecision(StrEnum):
    """Human decision for one exact injected-boundary candidate."""

    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class InjectionRegionAuthority:
    """Normalized scene region in which an injected asset is permitted to appear."""

    side: IntroductionInjectionSide
    left: float
    top: float
    right: float
    bottom: float
    partial_visibility_required: bool = True
    max_subject_scale_ratio: float = 0.60
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in ("left", "top", "right", "bottom"):
            value = float(getattr(self, field_name))
            if not 0.0 <= value <= 1.0:
                raise IntroductionAssetInjectionError(
                    f"Injection region {field_name} must be normalized between 0 and 1"
                )
            object.__setattr__(self, field_name, value)
        if self.left >= self.right or self.top >= self.bottom:
            raise IntroductionAssetInjectionError(
                "Injection region must have positive normalized width and height"
            )
        ratio = float(self.max_subject_scale_ratio)
        if not 0.0 < ratio <= 1.0:
            raise IntroductionAssetInjectionError(
                "Injection region max_subject_scale_ratio must be greater than 0 and at most 1"
            )
        object.__setattr__(self, "max_subject_scale_ratio", ratio)

        if self.side is IntroductionInjectionSide.LEFT and self.left != 0.0:
            raise IntroductionAssetInjectionError(
                "LEFT injection region must be anchored to the left frame edge"
            )
        if self.side is IntroductionInjectionSide.RIGHT and self.right != 1.0:
            raise IntroductionAssetInjectionError(
                "RIGHT injection region must be anchored to the right frame edge"
            )

    @property
    def region_id(self) -> str:
        return f"IIRG-{_fingerprint(self._authority_payload())[:16].upper()}"

    @property
    def normalized_box(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "side": self.side.value,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "partial_visibility_required": self.partial_visibility_required,
            "max_subject_scale_ratio": self.max_subject_scale_ratio,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["region_id"] = self.region_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> InjectionRegionAuthority:
        region = cls(
            side=IntroductionInjectionSide(str(raw.get("side") or "")),
            left=float(raw.get("left") or 0.0),
            top=float(raw.get("top") or 0.0),
            right=float(raw.get("right") or 0.0),
            bottom=float(raw.get("bottom") or 0.0),
            partial_visibility_required=bool(raw.get("partial_visibility_required", True)),
            max_subject_scale_ratio=float(raw.get("max_subject_scale_ratio") or 0.60),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied = str(raw.get("region_id") or "").strip()
        if supplied and supplied != region.region_id:
            raise IntroductionAssetInjectionError(
                "Injection region identity does not match governed content"
            )
        return region


@dataclass(frozen=True, slots=True)
class CanonicalInjectionAsset:
    """Canonical asset evidence used as immutable injection identity authority."""

    asset_id: str
    asset_kind: str
    reference_ids: tuple[str, ...]
    reference_paths: tuple[str, ...]
    reference_sha256: tuple[str, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        asset_id = self.asset_id.strip().upper()
        asset_kind = self.asset_kind.strip().casefold()
        if not asset_id:
            raise IntroductionAssetInjectionError("Canonical injection asset requires asset_id")
        if not asset_kind:
            raise IntroductionAssetInjectionError("Canonical injection asset requires asset_kind")
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "asset_kind", asset_kind)

        lengths = {
            len(self.reference_ids),
            len(self.reference_paths),
            len(self.reference_sha256),
        }
        if lengths != {len(self.reference_ids)} or not self.reference_ids:
            raise IntroductionAssetInjectionError(
                "Canonical injection reference ids, paths, and checksums must be non-empty and aligned"
            )
        if any(not value.strip() for value in self.reference_ids):
            raise IntroductionAssetInjectionError(
                "Canonical injection reference ids cannot be blank"
            )
        if any(not value.strip() for value in self.reference_paths):
            raise IntroductionAssetInjectionError(
                "Canonical injection reference paths cannot be blank"
            )
        checksums = tuple(value.strip().lower() for value in self.reference_sha256)
        if any(not value for value in checksums):
            raise IntroductionAssetInjectionError(
                "Canonical injection reference checksums cannot be blank"
            )
        object.__setattr__(
            self, "reference_ids", tuple(value.strip() for value in self.reference_ids)
        )
        object.__setattr__(
            self,
            "reference_paths",
            tuple(value.strip() for value in self.reference_paths),
        )
        object.__setattr__(self, "reference_sha256", checksums)

    @property
    def authority_id(self) -> str:
        return f"CIA-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "asset_id": self.asset_id,
            "asset_kind": self.asset_kind,
            "reference_ids": list(self.reference_ids),
            "reference_paths": list(self.reference_paths),
            "reference_sha256": list(self.reference_sha256),
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["authority_id"] = self.authority_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CanonicalInjectionAsset:
        asset = cls(
            asset_id=str(raw.get("asset_id") or ""),
            asset_kind=str(raw.get("asset_kind") or ""),
            reference_ids=tuple(str(value) for value in raw.get("reference_ids") or ()),
            reference_paths=tuple(str(value) for value in raw.get("reference_paths") or ()),
            reference_sha256=tuple(str(value) for value in raw.get("reference_sha256") or ()),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied = str(raw.get("authority_id") or "").strip()
        if supplied and supplied != asset.authority_id:
            raise IntroductionAssetInjectionError(
                "Canonical injection asset identity does not match governed content"
            )
        return asset


@dataclass(frozen=True, slots=True)
class IntroductionInjectionRequest:
    """Immutable authority for injecting one canonical asset into one exact boundary frame."""

    shot_id: str
    requirement_id: str
    boundary_id: str
    source_span_id: str
    target_span_id: str
    source_global_frame_index: int
    target_global_frame_index: int
    source_boundary_image_path: str
    source_boundary_image_sha256: str
    canonical_asset: CanonicalInjectionAsset
    injection_region: InjectionRegionAuthority
    width: int
    height: int
    seed: int
    timed_asset_presence_fingerprint: str
    source_package_fingerprint: str
    mode: IntroductionInjectionMode = IntroductionInjectionMode.CHARACTER_ENTER
    injection_version: str = "3.6.2"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise IntroductionAssetInjectionError("Injection request requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)
        for field_name in (
            "requirement_id",
            "boundary_id",
            "source_span_id",
            "target_span_id",
            "source_boundary_image_path",
            "source_boundary_image_sha256",
            "timed_asset_presence_fingerprint",
            "source_package_fingerprint",
            "injection_version",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise IntroductionAssetInjectionError(f"Injection request requires {field_name}")
            if field_name.endswith("sha256") or field_name.endswith("fingerprint"):
                value = value.lower()
            object.__setattr__(self, field_name, value)
        if self.source_global_frame_index < 0:
            raise IntroductionAssetInjectionError("Injection source frame index cannot be negative")
        if self.target_global_frame_index != self.source_global_frame_index + 1:
            raise IntroductionAssetInjectionError(
                "Injection target frame must immediately follow the source boundary"
            )
        if self.width <= 0 or self.height <= 0:
            raise IntroductionAssetInjectionError(
                "Injection request target dimensions must be positive"
            )
        if self.mode is IntroductionInjectionMode.CHARACTER_ENTER:
            if self.canonical_asset.asset_kind != "character":
                raise IntroductionAssetInjectionError(
                    "CHARACTER_ENTER injection requires a character canonical asset"
                )
            if not self.injection_region.partial_visibility_required:
                raise IntroductionAssetInjectionError(
                    "CHARACTER_ENTER injection requires partial first-frame visibility"
                )

    @property
    def request_id(self) -> str:
        return f"IIAR-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "injection_version": self.injection_version,
            "mode": self.mode.value,
            "shot_id": self.shot_id,
            "requirement_id": self.requirement_id,
            "boundary_id": self.boundary_id,
            "source_span_id": self.source_span_id,
            "target_span_id": self.target_span_id,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "source_boundary_image_path": self.source_boundary_image_path,
            "source_boundary_image_sha256": self.source_boundary_image_sha256,
            "canonical_asset": self.canonical_asset.to_dict(),
            "injection_region": self.injection_region.to_dict(),
            "width": self.width,
            "height": self.height,
            "seed": self.seed,
            "timed_asset_presence_fingerprint": self.timed_asset_presence_fingerprint,
            "source_package_fingerprint": self.source_package_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["request_id"] = self.request_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IntroductionInjectionRequest:
        asset_raw = raw.get("canonical_asset")
        region_raw = raw.get("injection_region")
        if not isinstance(asset_raw, dict) or not isinstance(region_raw, dict):
            raise IntroductionAssetInjectionError(
                "Injection request requires canonical_asset and injection_region objects"
            )
        request = cls(
            shot_id=str(raw.get("shot_id") or ""),
            requirement_id=str(raw.get("requirement_id") or ""),
            boundary_id=str(raw.get("boundary_id") or ""),
            source_span_id=str(raw.get("source_span_id") or ""),
            target_span_id=str(raw.get("target_span_id") or ""),
            source_global_frame_index=int(raw.get("source_global_frame_index") or 0),
            target_global_frame_index=int(raw.get("target_global_frame_index") or 0),
            source_boundary_image_path=str(raw.get("source_boundary_image_path") or ""),
            source_boundary_image_sha256=str(raw.get("source_boundary_image_sha256") or ""),
            canonical_asset=CanonicalInjectionAsset.from_dict(asset_raw),
            injection_region=InjectionRegionAuthority.from_dict(region_raw),
            width=int(raw.get("width") or 0),
            height=int(raw.get("height") or 0),
            seed=int(raw.get("seed") or 0),
            timed_asset_presence_fingerprint=str(raw.get("timed_asset_presence_fingerprint") or ""),
            source_package_fingerprint=str(raw.get("source_package_fingerprint") or ""),
            mode=IntroductionInjectionMode(
                str(raw.get("mode") or IntroductionInjectionMode.CHARACTER_ENTER.value)
            ),
            injection_version=str(raw.get("injection_version") or "3.6.2"),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied = str(raw.get("request_id") or "").strip()
        if supplied and supplied != request.request_id:
            raise IntroductionAssetInjectionError(
                "Injection request identity does not match governed content"
            )
        return request


@dataclass(frozen=True, slots=True)
class IntroductionInjectionResult:
    """Exact immutable image result produced for one governed injection request."""

    request_id: str
    requirement_id: str
    image_path: str
    image_sha256: str
    canonical_asset_id: str
    injection_region_id: str
    provider_name: str
    model: str
    generated_at: str
    attempt_number: int
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "requirement_id",
            "image_path",
            "image_sha256",
            "canonical_asset_id",
            "injection_region_id",
            "provider_name",
            "model",
            "generated_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise IntroductionAssetInjectionError(f"Injection result requires {field_name}")
            if field_name == "image_sha256":
                value = value.lower()
            object.__setattr__(self, field_name, value)
        if self.attempt_number <= 0:
            raise IntroductionAssetInjectionError(
                "Injection result attempt_number must be positive"
            )

    @property
    def result_id(self) -> str:
        return f"IIAS-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "requirement_id": self.requirement_id,
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "canonical_asset_id": self.canonical_asset_id,
            "injection_region_id": self.injection_region_id,
            "provider_name": self.provider_name,
            "model": self.model,
            "generated_at": self.generated_at,
            "attempt_number": self.attempt_number,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["result_id"] = self.result_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IntroductionInjectionResult:
        result = cls(
            request_id=str(raw.get("request_id") or ""),
            requirement_id=str(raw.get("requirement_id") or ""),
            image_path=str(raw.get("image_path") or ""),
            image_sha256=str(raw.get("image_sha256") or ""),
            canonical_asset_id=str(raw.get("canonical_asset_id") or ""),
            injection_region_id=str(raw.get("injection_region_id") or ""),
            provider_name=str(raw.get("provider_name") or ""),
            model=str(raw.get("model") or ""),
            generated_at=str(raw.get("generated_at") or ""),
            attempt_number=int(raw.get("attempt_number") or 0),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied = str(raw.get("result_id") or "").strip()
        if supplied and supplied != result.result_id:
            raise IntroductionAssetInjectionError(
                "Injection result identity does not match governed content"
            )
        return result


@dataclass(frozen=True, slots=True)
class IntroductionInjectionReview:
    """Append-only human decision bound to one exact injection candidate."""

    requirement_id: str
    result_id: str
    image_sha256: str
    decision: IntroductionInjectionDecision
    reviewed_by: str
    reviewed_at: str
    notes: str = ""
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "requirement_id",
            "result_id",
            "image_sha256",
            "reviewed_by",
            "reviewed_at",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise IntroductionAssetInjectionError(f"Injection review requires {field_name}")
            if field_name == "image_sha256":
                value = value.lower()
            object.__setattr__(self, field_name, value)
        object.__setattr__(self, "notes", self.notes.strip())

    @property
    def review_id(self) -> str:
        return f"IIREV-{_fingerprint(self._authority_payload())[:16].upper()}"

    def _authority_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "requirement_id": self.requirement_id,
            "result_id": self.result_id,
            "image_sha256": self.image_sha256,
            "decision": self.decision.value,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "notes": self.notes,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self._authority_payload()
        payload["review_id"] = self.review_id
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> IntroductionInjectionReview:
        review = cls(
            requirement_id=str(raw.get("requirement_id") or ""),
            result_id=str(raw.get("result_id") or ""),
            image_sha256=str(raw.get("image_sha256") or ""),
            decision=IntroductionInjectionDecision(str(raw.get("decision") or "")),
            reviewed_by=str(raw.get("reviewed_by") or ""),
            reviewed_at=str(raw.get("reviewed_at") or ""),
            notes=str(raw.get("notes") or ""),
            schema_version=str(raw.get("schema_version") or "1.0"),
        )
        supplied = str(raw.get("review_id") or "").strip()
        if supplied and supplied != review.review_id:
            raise IntroductionAssetInjectionError(
                "Injection review identity does not match governed content"
            )
        return review


@dataclass(frozen=True, slots=True)
class IntroductionInjectionCandidateStatus:
    """Operator-facing injected-boundary candidate with exact authority evidence."""

    requirement_id: str
    request_id: str
    result_id: str
    source_boundary_image_path: str
    source_boundary_image_sha256: str
    image_path: str
    image_sha256: str
    canonical_asset: CanonicalInjectionAsset
    injection_region: InjectionRegionAuthority
    target_global_frame_index: int
    attempt_number: int
    decision: IntroductionInjectionDecision | None = None

    @property
    def pending(self) -> bool:
        return self.decision is None


class IntroductionInjectionBoundaryStore:
    """Persist immutable injection requests/results for orchestration and human review."""

    RELATIVE_PATH = Path(".vscs") / "introduction_injection_boundaries.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def save_request(self, request: IntroductionInjectionRequest) -> IntroductionInjectionRequest:
        root = self._root()
        rows = [dict(item) for item in root.get("requests", []) if isinstance(item, dict)]
        if not any(str(item.get("request_id") or "") == request.request_id for item in rows):
            rows.append(request.to_dict())
        root["requests"] = rows
        self._write(root)
        stored = self.request_for_id(request.request_id)
        assert stored is not None
        return stored

    def save_result(self, result: IntroductionInjectionResult) -> IntroductionInjectionResult:
        request = self.request_for_id(result.request_id)
        if request is None:
            raise IntroductionAssetInjectionError(
                "Injection result cannot be stored without its immutable request"
            )
        if result.requirement_id != request.requirement_id:
            raise IntroductionAssetInjectionError(
                "Injection result requirement does not match its immutable request"
            )
        if result.canonical_asset_id != request.canonical_asset.authority_id:
            raise IntroductionAssetInjectionError(
                "Injection result canonical asset authority does not match its immutable request"
            )
        if result.injection_region_id != request.injection_region.region_id:
            raise IntroductionAssetInjectionError(
                "Injection result region authority does not match its immutable request"
            )
        root = self._root()
        rows = [dict(item) for item in root.get("results", []) if isinstance(item, dict)]
        if not any(str(item.get("result_id") or "") == result.result_id for item in rows):
            rows.append(result.to_dict())
        root["results"] = rows
        self._write(root)
        stored = self.result_for_id(result.result_id)
        assert stored is not None
        return stored

    def request_for_id(self, request_id: str) -> IntroductionInjectionRequest | None:
        normalized = request_id.strip()
        for raw in reversed(self._root().get("requests", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("request_id") or "").strip() == normalized:
                return IntroductionInjectionRequest.from_dict(raw)
        return None

    def result_for_id(self, result_id: str) -> IntroductionInjectionResult | None:
        normalized = result_id.strip()
        for raw in reversed(self._root().get("results", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("result_id") or "").strip() == normalized:
                return IntroductionInjectionResult.from_dict(raw)
        return None

    def latest_result_for_requirement(
        self,
        requirement_id: str,
    ) -> IntroductionInjectionResult | None:
        normalized = requirement_id.strip()
        for raw in reversed(self._root().get("results", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("requirement_id") or "").strip() == normalized:
                return IntroductionInjectionResult.from_dict(raw)
        return None

    def latest_result_for_request(
        self,
        request_id: str,
    ) -> IntroductionInjectionResult | None:
        normalized = request_id.strip()
        for raw in reversed(self._root().get("results", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("request_id") or "").strip() == normalized:
                return IntroductionInjectionResult.from_dict(raw)
        return None

    def _root(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema_version": "1.0", "requests": [], "results": []}
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IntroductionAssetInjectionError(
                f"Cannot read introduction injection-boundary store: {exc}"
            ) from exc
        if not isinstance(root, dict):
            raise IntroductionAssetInjectionError(
                "Introduction injection-boundary store root must be an object"
            )
        for field_name in ("requests", "results"):
            if not isinstance(root.get(field_name, []), list):
                raise IntroductionAssetInjectionError(
                    f"Introduction injection-boundary store {field_name} must be an array"
                )
        return dict(root)

    def _write(self, root: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "schema_version": "1.0",
            "requests": list(root.get("requests", [])),
            "results": list(root.get("results", [])),
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


class IntroductionInjectionReviewStore:
    """Append-only human review authority for injection candidates."""

    RELATIVE_PATH = Path(".vscs") / "introduction_injection_reviews.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.RELATIVE_PATH

    def save(self, review: IntroductionInjectionReview) -> IntroductionInjectionReview:
        root = self._root()
        rows = [dict(item) for item in root.get("reviews", []) if isinstance(item, dict)]
        if not any(str(item.get("review_id") or "") == review.review_id for item in rows):
            rows.append(review.to_dict())
        root["reviews"] = rows
        self._write(root)
        stored = self.review_for_result(review.result_id)
        assert stored is not None
        return stored

    def record(
        self,
        *,
        requirement_id: str,
        result_id: str,
        image_sha256: str,
        decision: IntroductionInjectionDecision,
        reviewed_by: str,
        notes: str = "",
        reviewed_at: str | None = None,
    ) -> IntroductionInjectionReview:
        return self.save(
            IntroductionInjectionReview(
                requirement_id=requirement_id,
                result_id=result_id,
                image_sha256=image_sha256,
                decision=decision,
                reviewed_by=reviewed_by,
                reviewed_at=reviewed_at or datetime.now(UTC).isoformat(),
                notes=notes,
            )
        )

    def review_for_result(self, result_id: str) -> IntroductionInjectionReview | None:
        normalized = result_id.strip()
        for raw in reversed(self._root().get("reviews", [])):
            if not isinstance(raw, dict):
                continue
            if str(raw.get("result_id") or "").strip() != normalized:
                continue
            return IntroductionInjectionReview.from_dict(raw)
        return None

    def approved(self, result_id: str, image_sha256: str) -> bool:
        review = self.review_for_result(result_id)
        return (
            review is not None
            and review.decision is IntroductionInjectionDecision.APPROVED
            and review.image_sha256 == image_sha256.strip().lower()
        )

    def rejected_count(self, requirement_id: str) -> int:
        normalized = requirement_id.strip()
        return sum(
            1
            for raw in self._root().get("reviews", [])
            if isinstance(raw, dict)
            and str(raw.get("requirement_id") or "").strip() == normalized
            and str(raw.get("decision") or "").strip()
            == IntroductionInjectionDecision.REJECTED.value
        )

    def _root(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"schema_version": "1.0", "reviews": []}
        try:
            root = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IntroductionAssetInjectionError(
                f"Cannot read introduction injection-review store: {exc}"
            ) from exc
        if not isinstance(root, dict):
            raise IntroductionAssetInjectionError(
                "Introduction injection-review store root must be an object"
            )
        reviews = root.get("reviews", [])
        if not isinstance(reviews, list):
            raise IntroductionAssetInjectionError(
                "Introduction injection-review store reviews must be an array"
            )
        return dict(root)

    def _write(self, root: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(root, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
