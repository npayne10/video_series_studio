from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from vscs.application.production_execution.package_compilation import (
    CompiledProductionPackage,
    ProductionPackageCompilationError,
    ProductionPackageCompilerService,
)
from vscs.application.production_package import ProductionPackageService
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    AssetPresenceRemoval,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)


def _ros_plan() -> TimedAssetPresencePlan:
    return TimedAssetPresencePlan(
        shot_id="EP-001-SCN-001-SHT-002",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-JAMES-PRIMARY",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-003",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-SANDRA-PRIMARY",),
            ),
            TimedAssetPresence(
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-IRON-HORIZON-BRIDGE",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-004",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=("REF-ROS-PRIMARY",),
                notes="Ros walks onto the bridge at 4.000 seconds.",
            ),
        ),
    )


def _asset_payload(asset_id: str, reference_id: str) -> dict[str, object]:
    return {
        "binding": {
            "binding_id": f"AB-{asset_id}",
            "role": "governed",
            "requirement": "Required by shot",
            "asset_id": asset_id,
        },
        "resolution": {
            "asset_id": asset_id,
            "canonical_reference": reference_id,
        },
        "production": {
            "asset_id": asset_id,
            "provider_neutral": True,
        },
    }


def test_ros_enters_at_exact_frame_96_without_leaking_into_opening_span() -> None:
    plan = _ros_plan()

    assert plan.change_frames == (96,)
    assert {item.asset_id for item in plan.active_at(95)} == {
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-LOC-021",
    }
    assert {item.asset_id for item in plan.active_at(96)} == {
        "CAP-CHR-001",
        "CAP-CHR-003",
        "CAP-LOC-021",
        "CAP-CHR-004",
    }
    ros = next(item for item in plan.presences if item.asset_id == "CAP-CHR-004")
    assert ros.introduction is AssetPresenceIntroduction.ENTER
    assert ros.canonical_reference_ids == ("REF-ROS-PRIMARY",)


def test_late_asset_presence_requires_explicit_introduction_event() -> None:
    with pytest.raises(TimedAssetPresenceError, match="requires ENTER, REVEAL, or APPEAR"):
        TimedAssetPresence(
            asset_id="CAP-CHR-004",
            asset_kind=TimedAssetKind.CHARACTER,
            from_frame=96,
            through_frame=143,
        )


def test_asset_ending_before_shot_requires_explicit_removal_event() -> None:
    with pytest.raises(TimedAssetPresenceError, match="requires EXIT, HIDE"):
        TimedAssetPresencePlan(
            shot_id="SHT-001",
            frames_per_second=24,
            frame_count=144,
            presences=(
                TimedAssetPresence(
                    asset_id="CAP-CHR-001",
                    asset_kind=TimedAssetKind.CHARACTER,
                    from_frame=0,
                    through_frame=95,
                ),
            ),
        )


def test_asset_may_exit_before_final_frame_with_explicit_removal_authority() -> None:
    plan = TimedAssetPresencePlan(
        shot_id="SHT-001",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=95,
                removal=AssetPresenceRemoval.EXIT,
            ),
        ),
    )

    assert plan.change_frames == (96,)
    assert plan.active_at(95)
    assert plan.active_at(96) == ()


def test_overlapping_presence_intervals_for_same_asset_fail_closed() -> None:
    with pytest.raises(TimedAssetPresenceError, match="overlap"):
        TimedAssetPresencePlan(
            shot_id="SHT-001",
            frames_per_second=24,
            frame_count=144,
            presences=(
                TimedAssetPresence(
                    asset_id="CAP-CHR-001",
                    asset_kind=TimedAssetKind.CHARACTER,
                    from_frame=0,
                    through_frame=100,
                    removal=AssetPresenceRemoval.EXIT,
                ),
                TimedAssetPresence(
                    asset_id="CAP-CHR-001",
                    asset_kind=TimedAssetKind.CHARACTER,
                    from_frame=96,
                    through_frame=143,
                    introduction=AssetPresenceIntroduction.ENTER,
                ),
            ),
        )


def test_presence_plan_fingerprint_and_identity_detect_tampering() -> None:
    payload = _ros_plan().to_dict()
    restored = TimedAssetPresencePlan.from_dict(payload)

    assert restored.plan_id == payload["plan_id"]
    assert restored.fingerprint == payload["fingerprint"]

    tampered = dict(payload)
    timing = dict(tampered["timing_basis"])  # type: ignore[arg-type]
    timing["frame_count"] = 145
    tampered["timing_basis"] = timing

    with pytest.raises(TimedAssetPresenceError):
        TimedAssetPresencePlan.from_dict(tampered)


def test_presence_plan_requires_assets_from_governed_asset_authority() -> None:
    with pytest.raises(TimedAssetPresenceError, match="CAP-CHR-004"):
        _ros_plan().require_governed_assets(
            {"CAP-CHR-001", "CAP-CHR-003", "CAP-LOC-021"}
        )


@dataclass(frozen=True)
class _Integrated:
    package_id: str = "PIP-SHT-002-AAAA"
    shot_id: str = "EP-001-SCN-001-SHT-002"
    review_id: str = "PRV-SHT-002"
    review_fingerprint: str = "review-fingerprint"
    package_fingerprint: str = "planning-fingerprint"

    def payload(self) -> dict[str, object]:
        return {
            "shot": {
                "shot_id": self.shot_id,
                "title": "Ros enters",
                "target_runtime_seconds": 6,
            },
            "assets": [
                _asset_payload("CAP-CHR-001", "REF-JAMES-PRIMARY"),
                _asset_payload("CAP-CHR-003", "REF-SANDRA-PRIMARY"),
                _asset_payload("CAP-LOC-021", "REF-IRON-HORIZON-BRIDGE"),
                _asset_payload("CAP-CHR-004", "REF-ROS-PRIMARY"),
            ],
            "camera": {"movement": "static"},
            "lighting": {"intent": "bridge practicals"},
            "environment": {"context": "interior"},
        }


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Planning:
    def __init__(self) -> None:
        self.value = _Integrated()

    def require_current_package(self, _shot_id: str) -> _Integrated:
        return self.value

    def current_package(self, _shot_id: str) -> _Integrated:
        return self.value


def test_production_package_persists_reviewed_timed_presence_authority(tmp_path: Path) -> None:
    service = ProductionPackageService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        _Planning(),  # type: ignore[arg-type]
    )
    service.materialize("EP-001-SCN-001-SHT-002")

    derived = service.derive_timed_asset_presence(
        "EP-001-SCN-001-SHT-002",
        _ros_plan(),
        production_notes="Ros enters at frame 96.",
    )
    repeated = service.derive_timed_asset_presence(
        "EP-001-SCN-001-SHT-002",
        _ros_plan(),
        production_notes="Ros enters at frame 96.",
    )

    assert derived.timed_asset_presence["plan_id"] == _ros_plan().plan_id
    assert derived.validation["timed_asset_presence_complete"] is True
    assert derived.validation["timed_asset_presence_review_notes"] == "Ros enters at frame 96."
    assert repeated == derived
    assert len(service.list_packages(shot_id="EP-001-SCN-001-SHT-002")) == 2


def test_upd_compilation_preserves_timed_presence_as_provider_neutral_authority() -> None:
    plan = _ros_plan().to_dict()
    compiled = UniversalProductionDescriptionCompilerService._compile_description(
        {
            "current_shot_id": "EP-001-SCN-001-SHT-002",
            "universal_text": "governed production description",
            "timed_asset_presence": plan,
            "provider_neutral": True,
        }
    )

    assert compiled["production"]["timed_asset_presence"] == plan


def test_execution_compiler_validates_timed_presence_against_render_timing_and_assets() -> None:
    compiler = ProductionPackageCompilerService()
    production = {
        "assets": [
            _asset_payload("CAP-CHR-001", "REF-JAMES-PRIMARY"),
            _asset_payload("CAP-CHR-003", "REF-SANDRA-PRIMARY"),
            _asset_payload("CAP-LOC-021", "REF-IRON-HORIZON-BRIDGE"),
            _asset_payload("CAP-CHR-004", "REF-ROS-PRIMARY"),
        ],
        "timed_asset_presence": _ros_plan().to_dict(),
    }

    compiled = compiler._timed_asset_presence(
        production,
        shot_id="EP-001-SCN-001-SHT-002",
        frames_per_second=24,
        frame_count=144,
    )

    assert compiled is not None
    assert compiled["change_frames"] == [96]

    with pytest.raises(ProductionPackageCompilationError, match="frame count"):
        compiler._timed_asset_presence(
            production,
            shot_id="EP-001-SCN-001-SHT-002",
            frames_per_second=24,
            frame_count=145,
        )


def _compiled_package(plan: dict[str, object] | None) -> CompiledProductionPackage:
    return CompiledProductionPackage(
        task_id="PT-VIDEO-SHT-002",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="EP-001-SCN-001-SHT-002",
        profile="production",
        authority_id="UPD-SHT-002",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="Neill Payne",
        source_package_id="PP-SHT-002",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="governed",
        positive_prompt="positive",
        negative_prompt="negative",
        previous_approved_final_frame=None,
        filename_prefix="XORIX/EP-001/PT-VIDEO-SHT-002",
        width=1280,
        height=720,
        frame_count=144,
        frames_per_second=24,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=42,
        composition_plan={},
        production_authority={},
        package_fingerprint="placeholder",
        timed_asset_presence=plan,
    )


def test_dynamic_timed_presence_fails_closed_until_internal_span_rendering_exists() -> None:
    with pytest.raises(LocalProductionPackageCompilationError, match="Internal governed render spans"):
        LocalProductionPackageCompilationService._comfyui_payload(
            _compiled_package(_ros_plan().to_dict())
        )


def test_static_timed_presence_can_be_carried_without_changing_provider_behavior() -> None:
    static = TimedAssetPresencePlan(
        shot_id="EP-001-SCN-001-SHT-002",
        frames_per_second=24,
        frame_count=144,
        presences=(
            TimedAssetPresence(
                asset_id="CAP-CHR-001",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
            ),
        ),
    ).to_dict()

    payload = LocalProductionPackageCompilationService._comfyui_payload(
        _compiled_package(static)
    )

    assert payload["timed_asset_presence"] == static
