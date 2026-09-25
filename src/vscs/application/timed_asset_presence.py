"""Provider-neutral timed asset presence authority for Phase 20.18.2.3.1."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class TimedAssetPresenceError(ValueError):
    """Raised when timed asset-presence authority is invalid or ambiguous."""


class TimedAssetKind(StrEnum):
    """Generic production asset categories that may be present within a shot."""

    CHARACTER = "character"
    SHIP = "ship"
    VEHICLE = "vehicle"
    LOCATION = "location"
    ENVIRONMENT = "environment"
    PLANET = "planet"
    PROP = "prop"
    EFFECT = "effect"
    TECHNOLOGY = "technology"
    OTHER = "other"


class AssetPresenceIntroduction(StrEnum):
    """How an asset becomes visible/active at its first governed frame."""

    PRESENT = "present"
    ENTER = "enter"
    REVEAL = "reveal"
    APPEAR = "appear"


class AssetPresenceRemoval(StrEnum):
    """How an asset stops being visible/active after its governed interval."""

    THROUGH_SHOT = "through_shot"
    EXIT = "exit"
    HIDE = "hide"
    DISAPPEAR = "disappear"


@dataclass(frozen=True, slots=True)
class TimedAssetPresence:
    """One exact governed frame interval for one canonical production asset."""

    asset_id: str
    asset_kind: TimedAssetKind
    from_frame: int
    through_frame: int
    introduction: AssetPresenceIntroduction = AssetPresenceIntroduction.PRESENT
    removal: AssetPresenceRemoval = AssetPresenceRemoval.THROUGH_SHOT
    canonical_reference_ids: tuple[str, ...] = ()
    required: bool = True
    notes: str = ""

    def __post_init__(self) -> None:
        asset_id = self.asset_id.strip()
        if not asset_id:
            raise TimedAssetPresenceError("Timed asset presence requires asset_id")
        object.__setattr__(self, "asset_id", asset_id)

        if self.from_frame < 0:
            raise TimedAssetPresenceError("from_frame cannot be negative")
        if self.through_frame < self.from_frame:
            raise TimedAssetPresenceError("through_frame cannot be before from_frame")
        if self.from_frame > 0 and self.introduction is AssetPresenceIntroduction.PRESENT:
            raise TimedAssetPresenceError(
                "An asset beginning after frame 0 requires ENTER, REVEAL, or APPEAR introduction"
            )

        references = tuple(value.strip() for value in self.canonical_reference_ids)
        if any(not value for value in references):
            raise TimedAssetPresenceError("canonical_reference_ids cannot contain blank values")
        if len(set(references)) != len(references):
            raise TimedAssetPresenceError("canonical_reference_ids cannot contain duplicates")
        object.__setattr__(self, "canonical_reference_ids", references)
        object.__setattr__(self, "notes", self.notes.strip())

    @property
    def presence_id(self) -> str:
        """Return deterministic identity for this exact interval authority."""
        payload = {
            "asset_id": self.asset_id,
            "asset_kind": self.asset_kind.value,
            "from_frame": self.from_frame,
            "through_frame": self.through_frame,
            "introduction": self.introduction.value,
            "removal": self.removal.value,
            "canonical_reference_ids": list(self.canonical_reference_ids),
            "required": self.required,
            "notes": self.notes,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:20].upper()
        return f"TAP-{digest}"

    def to_dict(self) -> dict[str, object]:
        return {
            "presence_id": self.presence_id,
            "asset_id": self.asset_id,
            "asset_kind": self.asset_kind.value,
            "from_frame": self.from_frame,
            "through_frame": self.through_frame,
            "introduction": self.introduction.value,
            "removal": self.removal.value,
            "canonical_reference_ids": list(self.canonical_reference_ids),
            "required": self.required,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> TimedAssetPresence:
        asset_id = str(raw.get("asset_id") or "").strip()
        kind_raw = str(raw.get("asset_kind") or "").strip().casefold()
        introduction_raw = str(raw.get("introduction") or "present").strip().casefold()
        removal_raw = str(raw.get("removal") or "through_shot").strip().casefold()
        references_raw = raw.get("canonical_reference_ids", [])
        if not isinstance(references_raw, list | tuple):
            raise TimedAssetPresenceError("canonical_reference_ids must be an array")
        required_raw = raw.get("required", True)
        if not isinstance(required_raw, bool):
            raise TimedAssetPresenceError("required must be a boolean")

        try:
            asset_kind = TimedAssetKind(kind_raw)
        except ValueError as exc:
            raise TimedAssetPresenceError(f"Unsupported timed asset kind: {kind_raw!r}") from exc
        try:
            introduction = AssetPresenceIntroduction(introduction_raw)
        except ValueError as exc:
            raise TimedAssetPresenceError(
                f"Unsupported asset introduction event: {introduction_raw!r}"
            ) from exc
        try:
            removal = AssetPresenceRemoval(removal_raw)
        except ValueError as exc:
            raise TimedAssetPresenceError(
                f"Unsupported asset removal event: {removal_raw!r}"
            ) from exc

        presence = cls(
            asset_id=asset_id,
            asset_kind=asset_kind,
            from_frame=_required_int(raw, "from_frame"),
            through_frame=_required_int(raw, "through_frame"),
            introduction=introduction,
            removal=removal,
            canonical_reference_ids=tuple(str(value) for value in references_raw),
            required=required_raw,
            notes=str(raw.get("notes") or ""),
        )
        supplied_id = str(raw.get("presence_id") or "").strip()
        if supplied_id and supplied_id != presence.presence_id:
            raise TimedAssetPresenceError(
                "Timed asset presence identity does not match its governed content"
            )
        return presence


@dataclass(frozen=True, slots=True)
class TimedAssetPresencePlan:
    """Frame-exact, provider-neutral asset presence authority for one editorial shot."""

    shot_id: str
    frames_per_second: int
    frame_count: int
    presences: tuple[TimedAssetPresence, ...] = ()
    schema_version: str = "1.0"
    provider_neutral: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip().upper()
        if not shot_id:
            raise TimedAssetPresenceError("Timed asset presence plan requires shot_id")
        object.__setattr__(self, "shot_id", shot_id)

        if self.schema_version != "1.0":
            raise TimedAssetPresenceError(
                f"Unsupported timed asset presence schema: {self.schema_version!r}"
            )
        if self.provider_neutral is not True:
            raise TimedAssetPresenceError("Timed asset presence authority must be provider-neutral")
        if self.frames_per_second <= 0:
            raise TimedAssetPresenceError("frames_per_second must be positive")
        if self.frame_count <= 0:
            raise TimedAssetPresenceError("frame_count must be positive")

        ordered = tuple(
            sorted(
                self.presences,
                key=lambda item: (
                    item.from_frame,
                    item.through_frame,
                    item.asset_id.casefold(),
                    item.presence_id,
                ),
            )
        )
        object.__setattr__(self, "presences", ordered)
        self._validate_intervals()

    @property
    def fingerprint(self) -> str:
        canonical = json.dumps(
            self._authority_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @property
    def plan_id(self) -> str:
        return f"TAPLAN-{self.shot_id}-{self.fingerprint[:12].upper()}"

    @property
    def change_frames(self) -> tuple[int, ...]:
        """Return exact frames where visible asset composition may change."""
        frames: set[int] = set()
        for presence in self.presences:
            if presence.from_frame > 0:
                frames.add(presence.from_frame)
            after = presence.through_frame + 1
            if after < self.frame_count:
                frames.add(after)
        return tuple(sorted(frames))

    def active_at(self, frame_index: int) -> tuple[TimedAssetPresence, ...]:
        if frame_index < 0 or frame_index >= self.frame_count:
            raise TimedAssetPresenceError(
                f"Frame {frame_index} is outside governed range 0..{self.frame_count - 1}"
            )
        return tuple(
            presence
            for presence in self.presences
            if presence.from_frame <= frame_index <= presence.through_frame
        )

    def require_governed_assets(self, asset_ids: set[str] | frozenset[str]) -> None:
        governed = {value.strip().upper() for value in asset_ids if value.strip()}
        missing = tuple(
            sorted(
                {
                    presence.asset_id
                    for presence in self.presences
                    if presence.asset_id.upper() not in governed
                },
                key=str.casefold,
            )
        )
        if missing:
            raise TimedAssetPresenceError(
                "Timed asset presence references assets absent from governed Asset authority: "
                + ", ".join(missing)
            )

    def require_execution_timing(
        self,
        *,
        shot_id: str,
        frames_per_second: int,
        frame_count: int,
    ) -> None:
        if self.shot_id != shot_id.strip().upper():
            raise TimedAssetPresenceError(
                "Timed asset presence Shot identity does not match executable ProductionTask"
            )
        if self.frames_per_second != frames_per_second:
            raise TimedAssetPresenceError(
                "Timed asset presence frame rate does not match executable render authority"
            )
        if self.frame_count != frame_count:
            raise TimedAssetPresenceError(
                "Timed asset presence frame count does not match executable render authority"
            )

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
            "presences": [presence.to_dict() for presence in self.presences],
            "change_frames": list(self.change_frames),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TimedAssetPresencePlan:
        schema_version = str(raw.get("schema_version") or "1.0")
        provider_neutral = raw.get("provider_neutral", True)
        if not isinstance(provider_neutral, bool):
            raise TimedAssetPresenceError("provider_neutral must be a boolean")

        timing = raw.get("timing_basis")
        if not isinstance(timing, dict):
            raise TimedAssetPresenceError("timing_basis must be an object")
        presences_raw = raw.get("presences", [])
        if not isinstance(presences_raw, list):
            raise TimedAssetPresenceError("presences must be an array")
        presences = tuple(
            TimedAssetPresence.from_dict(dict(item))
            for item in presences_raw
            if isinstance(item, dict)
        )
        if len(presences) != len(presences_raw):
            raise TimedAssetPresenceError("Every presences entry must be an object")

        plan = cls(
            shot_id=str(raw.get("shot_id") or ""),
            frames_per_second=_required_int(timing, "frames_per_second"),
            frame_count=_required_int(timing, "frame_count"),
            presences=presences,
            schema_version=schema_version,
            provider_neutral=provider_neutral,
        )
        supplied_id = str(raw.get("plan_id") or "").strip()
        if supplied_id and supplied_id != plan.plan_id:
            raise TimedAssetPresenceError(
                "Timed asset presence plan identity does not match governed content"
            )
        supplied_fingerprint = str(raw.get("fingerprint") or "").strip().lower()
        if supplied_fingerprint and supplied_fingerprint != plan.fingerprint:
            raise TimedAssetPresenceError(
                "Timed asset presence fingerprint does not match governed content"
            )
        supplied_change_frames = raw.get("change_frames")
        if supplied_change_frames is not None:
            if not isinstance(supplied_change_frames, list):
                raise TimedAssetPresenceError("change_frames must be an array")
            if tuple(
                _integer_value(value, "change_frames") for value in supplied_change_frames
            ) != (plan.change_frames):
                raise TimedAssetPresenceError(
                    "Timed asset presence change_frames do not match governed intervals"
                )
        return plan

    def _validate_intervals(self) -> None:
        final_frame = self.frame_count - 1
        by_asset: dict[str, list[TimedAssetPresence]] = {}
        for presence in self.presences:
            if presence.through_frame > final_frame:
                raise TimedAssetPresenceError(
                    f"{presence.asset_id} presence exceeds final governed frame {final_frame}"
                )
            if (
                presence.through_frame < final_frame
                and presence.removal is AssetPresenceRemoval.THROUGH_SHOT
            ):
                raise TimedAssetPresenceError(
                    f"{presence.asset_id} ending before frame {final_frame} requires EXIT, HIDE, "
                    "or DISAPPEAR removal authority"
                )
            by_asset.setdefault(presence.asset_id.upper(), []).append(presence)

        for asset_id, intervals in by_asset.items():
            ordered = sorted(intervals, key=lambda item: (item.from_frame, item.through_frame))
            previous: TimedAssetPresence | None = None
            for current in ordered:
                if previous is not None and current.from_frame <= previous.through_frame:
                    raise TimedAssetPresenceError(
                        f"Timed asset presence intervals overlap for {asset_id}"
                    )
                previous = current


def _required_int(raw: dict[str, object], key: str) -> int:
    if key not in raw:
        raise TimedAssetPresenceError(f"Missing required integer field {key!r}")
    return _integer_value(raw[key], key)


def _integer_value(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TimedAssetPresenceError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise TimedAssetPresenceError(f"{field_name} must be an integer") from exc
    raise TimedAssetPresenceError(f"{field_name} must be an integer")
