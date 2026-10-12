"""Phase 20.18.2.3.6.6b.4 continuity asset-state carry-forward regressions."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.continuity_compiler import (
    ContinuityCompilationDraft,
    ContinuityCompilationStatus,
    ContinuityCompilerError,
    ContinuityCompilerService,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    AssetPresenceRemoval,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)

from .test_continuity_compiler import _service


def _presence_plan(
    shot_id: str,
    *,
    frame_count: int,
    include_ros: bool,
    ros_removal: AssetPresenceRemoval = AssetPresenceRemoval.THROUGH_SHOT,
) -> dict[str, object]:
    presences = [
        TimedAssetPresence(
            asset_id="CAP-CHR-001",
            asset_kind=TimedAssetKind.CHARACTER,
            from_frame=0,
            through_frame=frame_count - 1,
            introduction=AssetPresenceIntroduction.PRESENT,
            removal=AssetPresenceRemoval.THROUGH_SHOT,
        )
    ]
    if include_ros:
        presences.append(
            TimedAssetPresence(
                asset_id="CAP-CHR-005",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=frame_count - 1,
                introduction=AssetPresenceIntroduction.PRESENT,
                removal=ros_removal,
            )
        )
    return TimedAssetPresencePlan(
        shot_id=shot_id,
        frames_per_second=24,
        frame_count=frame_count,
        presences=tuple(presences),
    ).to_dict()


def _asset(asset_id: str) -> dict[str, object]:
    return {"resolution": {"asset_id": asset_id}}


def _continuous_packages(
    tmp_path: Path,
    *,
    previous_ros_removal: AssetPresenceRemoval = AssetPresenceRemoval.THROUGH_SHOT,
    current_has_ros: bool = False,
) -> tuple[ContinuityCompilerService, object]:
    service, packages = _service(tmp_path)
    previous = packages.values["SHT-001"]
    current = packages.values["SHT-002"]

    packages.values["SHT-001"] = replace(
        previous,
        assets=(
            _asset("CAP-CHR-001"),
            _asset("CAP-CHR-005"),
        ),
        timed_asset_presence=_presence_plan(
            "SHT-001",
            frame_count=144,
            include_ros=True,
            ros_removal=previous_ros_removal,
        ),
        action_performance={
            "opening_state": "Previous opens on bridge.",
            "closing_state": "Ros remains present on the bridge.",
        },
    )

    current_assets = [_asset("CAP-CHR-001")]
    if current_has_ros:
        current_assets.append(_asset("CAP-CHR-005"))
    packages.values["SHT-002"] = replace(
        current,
        assets=tuple(current_assets),
        timed_asset_presence=_presence_plan(
            "SHT-002",
            frame_count=240,
            include_ros=current_has_ros,
        ),
        action_performance={
            "opening_state": "Continue directly from SHT-001.",
            "closing_state": "James remains at the control station.",
        },
        shot={
            **current.shot,
            "continuity_in": "Continue directly from SHT-001.",
            "continuity_out": "James remains at the control station.",
        },
    )
    return service, packages


def test_continuous_boundary_blocks_dropped_final_active_asset_without_exit(
    tmp_path: Path,
) -> None:
    service, _packages = _continuous_packages(tmp_path)

    draft = service.create_from_current_package("SHT-002")
    continuity = draft.continuity_value()

    assert continuity["shot_boundary_mode"] == "continuous"
    assert continuity["previous_final_active_asset_ids"] == [
        "CAP-CHR-001",
        "CAP-CHR-005",
    ]
    assert continuity["previous_boundary_exit_asset_ids"] == []
    assert continuity["current_opening_active_asset_ids"] == ["CAP-CHR-001"]
    assert continuity["carry_forward_required_asset_ids"] == [
        "CAP-CHR-001",
        "CAP-CHR-005",
    ]
    assert continuity["missing_carried_asset_ids"] == ["CAP-CHR-005"]
    assert len(continuity["blocking_continuity_conflicts"]) == 1
    assert "CAP-CHR-005" in continuity["blocking_continuity_conflicts"][0]

    with pytest.raises(
        ContinuityCompilerError,
        match="unresolved blocking asset-state conflict",
    ):
        service.mark_ready("SHT-002")


def test_explicit_previous_boundary_exit_satisfies_carry_forward_governance(
    tmp_path: Path,
) -> None:
    service, packages = _continuous_packages(
        tmp_path,
        previous_ros_removal=AssetPresenceRemoval.EXIT,
    )

    draft = service.create_from_current_package("SHT-002")
    continuity = draft.continuity_value()

    assert continuity["previous_boundary_exit_asset_ids"] == ["CAP-CHR-005"]
    assert continuity["carry_forward_required_asset_ids"] == ["CAP-CHR-001"]
    assert continuity["missing_carried_asset_ids"] == []
    assert continuity["blocking_continuity_conflicts"] == []

    service.mark_ready("SHT-002")
    compiled = packages.values["SHT-002"].continuity["production"]
    assert compiled["previous_boundary_exit_asset_ids"] == ["CAP-CHR-005"]
    assert compiled["missing_carried_asset_ids"] == []
    assert compiled["blocking_conflicts"] == []


def test_carried_asset_present_at_current_frame_zero_resolves_boundary(
    tmp_path: Path,
) -> None:
    service, _packages = _continuous_packages(tmp_path, current_has_ros=True)

    continuity = service.create_from_current_package("SHT-002").continuity_value()

    assert continuity["current_opening_active_asset_ids"] == [
        "CAP-CHR-001",
        "CAP-CHR-005",
    ]
    assert continuity["missing_carried_asset_ids"] == []
    assert continuity["blocking_continuity_conflicts"] == []


def test_timed_presence_change_invalidates_new_asset_state_draft(tmp_path: Path) -> None:
    service, packages = _continuous_packages(tmp_path, current_has_ros=True)
    draft = service.create_from_current_package("SHT-002")
    assert service.is_current(draft)

    previous = packages.values["SHT-001"]
    packages.values["SHT-001"] = replace(
        previous,
        timed_asset_presence=_presence_plan(
            "SHT-001",
            frame_count=144,
            include_ros=True,
            ros_removal=AssetPresenceRemoval.EXIT,
        ),
    )

    assert not service.is_current(draft)


def test_legacy_ready_draft_remains_current_until_explicit_return_to_draft(
    tmp_path: Path,
) -> None:
    service, packages = _service(tmp_path)
    package: ProductionPackage = packages.values["SHT-002"]
    previous: ProductionPackage = packages.values["SHT-001"]
    legacy_fingerprint = service._legacy_dependency_fingerprint(
        package,
        previous,
        referenced_previous_shot_id="",
    )
    legacy = ContinuityCompilationDraft(
        shot_id="SHT-002",
        source_package_id=package.package_id,
        dependency_fingerprint=legacy_fingerprint,
        previous_shot_id="SHT-001",
        continuity={"current_shot_id": "SHT-002"},
        asset_state_governance_version="",
        status=ContinuityCompilationStatus.READY,
    )

    assert service.is_current(legacy)

    draft = replace(legacy, status=ContinuityCompilationStatus.DRAFT)
    assert not service.is_current(draft)
