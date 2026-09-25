"""Human-governed authoring bridge for frame-exact Timed Asset Presence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vscs.application.governed_reference_plan_source import GovernedReferencePlanSource
from vscs.application.production_package import ProductionPackageService
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    AssetPresenceRemoval,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)


class TimedAssetPresenceAuthoringError(RuntimeError):
    """Raised when explicit timed-presence authority cannot be authored safely."""


_FRAME_STATE_ROLES = {
    "scene_composition_anchor",
    "continuity_anchor",
    "start_frame_reference",
    "end_frame_reference",
}


@dataclass(frozen=True, slots=True)
class TimedAssetPresenceAuthoringContext:
    """Current governed inputs exposed to the operator before persistence."""

    shot_id: str
    frames_per_second: int
    frame_count: int
    governed_asset_ids: tuple[str, ...]
    reference_ids_by_asset: dict[str, tuple[str, ...]]
    plan: TimedAssetPresencePlan
    persisted: bool


class TimedAssetPresenceAuthoringService:
    """Build and persist explicit timed-presence authority without prose inference."""

    def __init__(
        self,
        packages: ProductionPackageService,
        reference_source: GovernedReferencePlanSource,
    ) -> None:
        self.packages = packages
        self.reference_source = reference_source

    def context(
        self,
        shot_id: str,
        *,
        frames_per_second: int = 24,
    ) -> TimedAssetPresenceAuthoringContext:
        package = self.packages.current_package(shot_id)
        if package is None:
            raise TimedAssetPresenceAuthoringError(
                f"No current Production Package exists for {shot_id}"
            )
        normalized = package.shot_id.strip().upper()
        fps = int(frames_per_second)
        if fps <= 0:
            raise TimedAssetPresenceAuthoringError("Frames per second must be positive")

        if package.timed_asset_presence:
            try:
                plan = TimedAssetPresencePlan.from_dict(package.timed_asset_presence)
            except TimedAssetPresenceError as exc:
                raise TimedAssetPresenceAuthoringError(
                    f"Persisted Timed Asset Presence authority is invalid: {exc}"
                ) from exc
            return TimedAssetPresenceAuthoringContext(
                shot_id=normalized,
                frames_per_second=plan.frames_per_second,
                frame_count=plan.frame_count,
                governed_asset_ids=tuple(self._governed_assets(package.assets)),
                reference_ids_by_asset=self._reference_ids_by_asset(normalized),
                plan=plan,
                persisted=True,
            )

        frame_count = self._default_frame_count(package.shot, fps)
        references = self._reference_ids_by_asset(normalized)
        presences: list[TimedAssetPresence] = []
        for asset in package.assets:
            production = self._production_record(asset)
            asset_id = str(production.get("asset_id") or "").strip()
            if not asset_id:
                continue
            kind = self._asset_kind(str(production.get("category") or ""))
            presences.append(
                TimedAssetPresence(
                    asset_id=asset_id,
                    asset_kind=kind,
                    from_frame=0,
                    through_frame=frame_count - 1,
                    introduction=AssetPresenceIntroduction.PRESENT,
                    removal=AssetPresenceRemoval.THROUGH_SHOT,
                    canonical_reference_ids=references.get(asset_id.upper(), ()),
                    required=True,
                )
            )
        if not presences:
            raise TimedAssetPresenceAuthoringError(
                "Current Production Package has no governed Asset authority"
            )
        plan = TimedAssetPresencePlan(
            shot_id=normalized,
            frames_per_second=fps,
            frame_count=frame_count,
            presences=tuple(presences),
        )
        return TimedAssetPresenceAuthoringContext(
            shot_id=normalized,
            frames_per_second=fps,
            frame_count=frame_count,
            governed_asset_ids=tuple(self._governed_assets(package.assets)),
            reference_ids_by_asset=references,
            plan=plan,
            persisted=False,
        )

    def persist(
        self,
        shot_id: str,
        plan: TimedAssetPresencePlan,
        *,
        production_notes: str = "",
    ) -> TimedAssetPresencePlan:
        package = self.packages.current_package(shot_id)
        if package is None:
            raise TimedAssetPresenceAuthoringError(
                f"No current Production Package exists for {shot_id}"
            )
        governed_assets = set(self._governed_assets(package.assets))
        reference_plan = self.reference_source.reference_plan_for_shot(shot_id)
        if not isinstance(reference_plan, dict):
            raise TimedAssetPresenceAuthoringError(
                "Timed Asset Presence authoring requires a persisted governed ReferencePlan"
            )
        if str(reference_plan.get("status") or "").strip().lower() != "passed":
            raise TimedAssetPresenceAuthoringError(
                "Timed Asset Presence authoring requires a passing governed ReferencePlan"
            )
        try:
            plan.require_governed_assets(governed_assets)
        except TimedAssetPresenceError as exc:
            raise TimedAssetPresenceAuthoringError(str(exc)) from exc
        self._validate_reference_scope(plan, reference_plan)
        self.packages.derive_timed_asset_presence(
            shot_id,
            plan,
            production_notes=production_notes,
        )
        return plan

    @classmethod
    def _validate_reference_scope(
        cls,
        plan: TimedAssetPresencePlan,
        reference_plan: dict[str, Any],
    ) -> None:
        raw = reference_plan.get("references")
        if not isinstance(raw, list):
            raise TimedAssetPresenceAuthoringError(
                "Governed ReferencePlan references must be an array"
            )
        references = tuple(dict(item) for item in raw if isinstance(item, dict))
        if len(references) != len(raw):
            raise TimedAssetPresenceAuthoringError(
                "Every governed ReferencePlan reference must be an object"
            )
        by_id = {
            str(item.get("reference_id") or "").strip(): item
            for item in references
            if str(item.get("reference_id") or "").strip()
        }
        declared: set[str] = set()
        for presence in plan.presences:
            for reference_id in presence.canonical_reference_ids:
                reference = by_id.get(reference_id)
                if reference is None:
                    raise TimedAssetPresenceAuthoringError(
                        f"Timed presence for {presence.asset_id} references unknown governed "
                        f"reference {reference_id}"
                    )
                role = str(reference.get("role") or "").strip()
                if role in _FRAME_STATE_ROLES:
                    raise TimedAssetPresenceAuthoringError(
                        f"Frame-state reference {reference_id} cannot be assigned as a timed "
                        "canonical asset reference"
                    )
                asset_id = str(reference.get("asset_id") or "").strip()
                if asset_id.upper() != presence.asset_id.upper():
                    raise TimedAssetPresenceAuthoringError(
                        f"Timed canonical reference {reference_id} belongs to "
                        f"{asset_id or 'no asset'}, not {presence.asset_id}"
                    )
                declared.add(reference_id)

        if plan.change_frames:
            unscoped = tuple(
                str(item.get("reference_id") or "").strip()
                for item in references
                if str(item.get("reference_id") or "").strip()
                and str(item.get("role") or "").strip() not in _FRAME_STATE_ROLES
                and str(item.get("reference_id") or "").strip() not in declared
            )
            if unscoped:
                raise TimedAssetPresenceAuthoringError(
                    "Dynamic timed presence leaves governed supporting references without "
                    "temporal scope: " + ", ".join(unscoped)
                )

    def _reference_ids_by_asset(self, shot_id: str) -> dict[str, tuple[str, ...]]:
        plan = self.reference_source.reference_plan_for_shot(shot_id)
        if not isinstance(plan, dict):
            return {}
        raw = plan.get("references")
        if not isinstance(raw, list):
            return {}
        result: dict[str, list[str]] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            reference_id = str(item.get("reference_id") or "").strip()
            asset_id = str(item.get("asset_id") or "").strip().upper()
            role = str(item.get("role") or "").strip()
            if not reference_id or not asset_id or role in _FRAME_STATE_ROLES:
                continue
            result.setdefault(asset_id, []).append(reference_id)
        return {key: tuple(dict.fromkeys(values)) for key, values in result.items()}

    @classmethod
    def _governed_assets(cls, assets: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
        result: list[str] = []
        for asset in assets:
            production = cls._production_record(asset)
            asset_id = str(production.get("asset_id") or "").strip().upper()
            if asset_id and asset_id not in result:
                result.append(asset_id)
        return tuple(result)

    @staticmethod
    def _production_record(asset: dict[str, Any]) -> dict[str, Any]:
        production = asset.get("production")
        if isinstance(production, dict):
            return production
        return asset

    @staticmethod
    def _asset_kind(category: str) -> TimedAssetKind:
        normalized = category.strip().casefold().replace(" ", "_")
        aliases = {
            "set": TimedAssetKind.LOCATION,
            "vehicle/ship": TimedAssetKind.SHIP,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return TimedAssetKind(normalized)
        except ValueError:
            return TimedAssetKind.OTHER

    @staticmethod
    def _default_frame_count(shot: dict[str, Any], frames_per_second: int) -> int:
        runtime = shot.get("target_runtime_seconds")
        if not isinstance(runtime, int | float) or isinstance(runtime, bool) or runtime <= 0:
            raise TimedAssetPresenceAuthoringError(
                "Current Shot has no positive target runtime for Timed Asset Presence authoring"
            )
        frame_count = round(float(runtime) * frames_per_second)
        if frame_count <= 0:
            raise TimedAssetPresenceAuthoringError(
                "Timed Asset Presence frame count must be positive"
            )
        return frame_count
