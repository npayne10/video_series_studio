"""Authority resolution for Phase 20.18.2.3.6.2 identity-locked asset injection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)

from .introduction_asset_injection import (
    CanonicalInjectionAsset,
    InjectionRegionAuthority,
    IntroductionAssetInjectionError,
    IntroductionInjectionSide,
)
from .introduction_keyframes import IntroductionKeyframeRequirement


class CanonicalInjectionAssetResolutionError(IntroductionAssetInjectionError):
    """Raised when canonical injection identity cannot be resolved unambiguously."""


class IntroductionInjectionRegionError(IntroductionAssetInjectionError):
    """Raised when a safe deterministic injection region cannot be compiled."""


@dataclass(frozen=True, slots=True)
class CanonicalInjectionAssetResolver:
    """Resolve exact canonical reference evidence for one governed introduction."""

    def resolve(
        self,
        requirement: IntroductionKeyframeRequirement,
        timed_presence: TimedAssetPresencePlan,
        reference_plan: dict[str, Any],
    ) -> CanonicalInjectionAsset:
        if requirement.shot_id != timed_presence.shot_id:
            raise CanonicalInjectionAssetResolutionError(
                "Injection requirement and timed presence belong to different Shots"
            )
        if len(requirement.introduced_asset_ids) != 1:
            raise CanonicalInjectionAssetResolutionError(
                "Identity-locked injection currently requires exactly one introduced asset"
            )
        asset_id = requirement.introduced_asset_ids[0]
        presence = self._introduced_presence(
            asset_id,
            requirement.target_global_frame_index,
            timed_presence,
        )
        if presence.asset_kind is not TimedAssetKind.CHARACTER:
            raise CanonicalInjectionAssetResolutionError(
                "Identity-locked CHARACTER_ENTER injection requires a character asset"
            )
        if presence.introduction is not AssetPresenceIntroduction.ENTER:
            raise CanonicalInjectionAssetResolutionError(
                "Identity-locked CHARACTER_ENTER injection requires ENTER timed presence"
            )
        if not requirement.introduced_reference_ids:
            raise CanonicalInjectionAssetResolutionError(
                "Identity-locked injection requires introduced canonical references"
            )

        required_reference_ids = requirement.introduced_reference_ids
        presence_reference_ids = set(presence.canonical_reference_ids)
        if not set(required_reference_ids).issubset(presence_reference_ids):
            raise CanonicalInjectionAssetResolutionError(
                "Introduction requirement references are not authorized by timed presence"
            )

        references = self._reference_records(reference_plan)
        references_by_id: dict[str, dict[str, Any]] = {}
        for reference in references:
            reference_id = str(reference.get("reference_id") or "").strip()
            if not reference_id:
                raise CanonicalInjectionAssetResolutionError(
                    "Governed ReferencePlan contains a reference without reference_id"
                )
            if reference_id in references_by_id:
                raise CanonicalInjectionAssetResolutionError(
                    f"Governed ReferencePlan contains duplicate reference ID: {reference_id}"
                )
            references_by_id[reference_id] = reference

        paths: list[str] = []
        checksums: list[str] = []
        for reference_id in required_reference_ids:
            reference = references_by_id.get(reference_id)
            if reference is None:
                raise CanonicalInjectionAssetResolutionError(
                    f"Introduced canonical reference is missing from ReferencePlan: {reference_id}"
                )
            reference_asset_id = str(reference.get("asset_id") or "").strip()
            if reference_asset_id != asset_id:
                raise CanonicalInjectionAssetResolutionError(
                    f"Canonical reference {reference_id} is not bound to introduced asset {asset_id}"
                )
            source_path = str(reference.get("source_path") or "").strip()
            if not source_path:
                raise CanonicalInjectionAssetResolutionError(
                    f"Canonical reference {reference_id} has no source_path"
                )
            checksum = str(reference.get("file_checksum") or "").strip().lower()
            if not checksum:
                raise CanonicalInjectionAssetResolutionError(
                    f"Canonical reference {reference_id} has no file_checksum"
                )
            paths.append(source_path)
            checksums.append(checksum)

        return CanonicalInjectionAsset(
            asset_id=asset_id,
            asset_kind=presence.asset_kind.value,
            reference_ids=required_reference_ids,
            reference_paths=tuple(paths),
            reference_sha256=tuple(checksums),
        )

    @staticmethod
    def _introduced_presence(
        asset_id: str,
        target_global_frame_index: int,
        timed_presence: TimedAssetPresencePlan,
    ) -> TimedAssetPresence:
        matches = tuple(
            presence
            for presence in timed_presence.presences
            if presence.asset_id == asset_id
            and presence.from_frame == target_global_frame_index
        )
        if len(matches) != 1:
            raise CanonicalInjectionAssetResolutionError(
                "Introduced asset must resolve to exactly one timed presence beginning "
                "at the target frame"
            )
        return matches[0]

    @staticmethod
    def _reference_records(reference_plan: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        status = str(reference_plan.get("status") or "").strip().casefold()
        if status and status != "passed":
            raise CanonicalInjectionAssetResolutionError(
                "Canonical injection requires a passed governed ReferencePlan"
            )
        raw = reference_plan.get("references")
        if not isinstance(raw, list):
            raise CanonicalInjectionAssetResolutionError(
                "Governed ReferencePlan references must be an array"
            )
        records = tuple(dict(item) for item in raw if isinstance(item, dict))
        if len(records) != len(raw):
            raise CanonicalInjectionAssetResolutionError(
                "Every governed ReferencePlan reference must be an object"
            )
        return records


@dataclass(frozen=True, slots=True)
class IntroductionInjectionRegionCompiler:
    """Compile a deterministic edge-constrained region for first-frame entrance injection."""

    edge_width_ratio: float = 0.18
    top_ratio: float = 0.08
    bottom_ratio: float = 0.96
    max_subject_scale_ratio: float = 0.55

    def __post_init__(self) -> None:
        if not 0.05 <= self.edge_width_ratio <= 0.25:
            raise IntroductionInjectionRegionError(
                "Injection edge_width_ratio must be between 0.05 and 0.25"
            )
        if not 0.0 <= self.top_ratio < self.bottom_ratio <= 1.0:
            raise IntroductionInjectionRegionError(
                "Injection vertical ratios must form a normalized positive interval"
            )
        if not 0.0 < self.max_subject_scale_ratio <= 0.60:
            raise IntroductionInjectionRegionError(
                "Injection max_subject_scale_ratio must be greater than 0 and at most 0.60"
            )

    def compile(
        self,
        *,
        width: int,
        height: int,
        side: IntroductionInjectionSide,
    ) -> InjectionRegionAuthority:
        if width <= 0 or height <= 0:
            raise IntroductionInjectionRegionError(
                "Injection region compilation requires positive frame dimensions"
            )
        if side is IntroductionInjectionSide.AUTO:
            raise IntroductionInjectionRegionError(
                "AUTO injection side cannot be delegated to a generative provider; "
                "resolve LEFT or RIGHT from governed scene authority first"
            )

        if side is IntroductionInjectionSide.LEFT:
            left = 0.0
            right = self.edge_width_ratio
        elif side is IntroductionInjectionSide.RIGHT:
            left = 1.0 - self.edge_width_ratio
            right = 1.0
        else:
            raise IntroductionInjectionRegionError(
                f"Unsupported injection side: {side!s}"
            )

        region = InjectionRegionAuthority(
            side=side,
            left=left,
            top=self.top_ratio,
            right=right,
            bottom=self.bottom_ratio,
            partial_visibility_required=True,
            max_subject_scale_ratio=self.max_subject_scale_ratio,
        )
        self._validate_pixel_region(region, width=width, height=height)
        return region

    @staticmethod
    def pixel_box(
        region: InjectionRegionAuthority,
        *,
        width: int,
        height: int,
    ) -> tuple[int, int, int, int]:
        if width <= 0 or height <= 0:
            raise IntroductionInjectionRegionError(
                "Injection pixel region requires positive frame dimensions"
            )
        left = round(region.left * width)
        top = round(region.top * height)
        right = round(region.right * width)
        bottom = round(region.bottom * height)
        if left >= right or top >= bottom:
            raise IntroductionInjectionRegionError(
                "Injection normalized region collapses at target frame dimensions"
            )
        return (left, top, right, bottom)

    def _validate_pixel_region(
        self,
        region: InjectionRegionAuthority,
        *,
        width: int,
        height: int,
    ) -> None:
        left, _top, right, _bottom = self.pixel_box(
            region,
            width=width,
            height=height,
        )
        if region.side is IntroductionInjectionSide.LEFT and left != 0:
            raise IntroductionInjectionRegionError(
                "Compiled LEFT injection region lost its frame-edge anchor"
            )
        if region.side is IntroductionInjectionSide.RIGHT and right != width:
            raise IntroductionInjectionRegionError(
                "Compiled RIGHT injection region lost its frame-edge anchor"
            )
        if region.side is IntroductionInjectionSide.LEFT and right > width // 4:
            raise IntroductionInjectionRegionError(
                "Compiled LEFT injection region intrudes into the central frame"
            )
        if region.side is IntroductionInjectionSide.RIGHT and left < (width * 3) // 4:
            raise IntroductionInjectionRegionError(
                "Compiled RIGHT injection region intrudes into the central frame"
            )
