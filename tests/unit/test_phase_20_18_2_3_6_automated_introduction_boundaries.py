from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
    KEYFRAME_ACCEPTANCE_CRITERIA,
    AutomatedIntroductionBoundaryError,
    AutomatedTimedSpanOrchestrationResult,
    ProductionExecutionUiService,
    GovernedInternalRenderSpanCompiler,
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedIntroductionKeyframeStore,
    IntroductionBoundaryAutomationPlanner,
    IntroductionBoundaryProviderCapabilities,
    IntroductionBoundaryStrategy,
    TimedCanonicalReferenceActivationCompiler,
)
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
    TimedSpanAcceptancePackageError,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timed() -> TimedAssetPresencePlan:
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
                canonical_reference_ids=("REF-JAMES",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-003",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-SANDRA",),
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-005",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=AssetPresenceIntroduction.ENTER,
                canonical_reference_ids=("REF-ROS",),
            ),
        ),
    )


def _reference_plan(project: Path) -> dict[str, object]:
    references = []
    for reference_id, asset_id, role in (
        ("REF-JAMES", "CAP-CHR-001", "secondary_identity"),
        ("REF-SANDRA", "CAP-CHR-003", "primary_identity"),
        ("REF-ROS", "CAP-CHR-005", "secondary_identity"),
    ):
        image = project / "references" / f"{reference_id}.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(reference_id.encode())
        references.append(
            {
                "reference_id": reference_id,
                "role": role,
                "asset_id": asset_id,
                "reference_class": "canonical_master",
                "priority": "required",
                "subject_type": "character",
                "source_path": str(image),
                "provider_ready": True,
                "file_checksum": _sha(image),
                "reference_fingerprint": f"fp-{reference_id}",
            }
        )
    anchor = project / "references" / "composition.png"
    anchor.write_bytes(b"composition")
    references.append(
        {
            "reference_id": "REF-COMPOSITION",
            "role": "scene_composition_anchor",
            "asset_id": None,
            "reference_class": "shot_composite",
            "priority": "required",
            "subject_type": "multi_subject_scene",
            "source_path": str(anchor),
            "provider_ready": True,
            "file_checksum": _sha(anchor),
            "reference_fingerprint": "fp-composition",
        }
    )
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx-2.5",
        },
        "references": references,
        "diagnostics": [],
    }


def _authority(project: Path):
    timed = _timed()
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        _reference_plan(project),
    )
    requirements = GovernedIntroductionKeyframeRequirementCompiler().compile(
        spans,
        activation,
    )
    return timed, spans, activation, requirements


def _candidate_package(project: Path) -> tuple[Path, object]:
    timed, spans, activation, requirements = _authority(project)
    opening = project / "keyframes" / "opening.png"
    opening.parent.mkdir(parents=True, exist_ok=True)
    opening.write_bytes(b"opening")
    raw: dict[str, object] = {
        "schema_version": "7.2.2-vscs-1",
        "status": "TIMED_SPAN_ACCEPTANCE_REQUIRED",
        "profile": "production",
        "positive_prompt": "continue",
        "negative_prompt": "no drift",
        "motion_prompt": "continue",
        "shot_prompt": "continue",
        "filename_prefix": "XORIX/EP-001/PT-SHT-002",
        "width": 1280,
        "height": 720,
        "frame_count": 144,
        "fps": 24,
        "cfg": 1.0,
        "ic_lora_strength": 1.0,
        "seed": 42,
        "timed_asset_presence": timed.to_dict(),
        "internal_render_spans": spans.to_dict(),
        "timed_reference_activation": activation.to_dict(),
        "introduction_keyframe_requirements": requirements.to_dict(),
        "reference_plan": _reference_plan(project),
        "governed_keyframe": {
            "schema_version": "1.0",
            "shot_id": timed.shot_id,
            "image_path": str(opening),
            "image_sha256": _sha(opening),
            "approved_by": "Neill Payne",
            "approved_at": "2026-09-26T10:00:00+02:00",
            "acceptance_criteria": list(KEYFRAME_ACCEPTANCE_CRITERIA),
            "status": "approved",
            "source_kind": "human_approved_shot_composition",
        },
        "_vscs_manifest": {
            "task_id": "PT-VIDEO-SHT-002",
            "production_id": "XORIX",
            "episode_id": "EP-001",
            "scene_id": "SCN-001",
            "shot_id": timed.shot_id,
            "package_fingerprint": "parent-package-fingerprint",
        },
    }
    path = project / "production" / "compiled" / "production_package.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return path, requirements


def test_strategy_prefers_native_then_synthesis_then_manual() -> None:
    native = IntroductionBoundaryProviderCapabilities(
        provider_id="future",
        timed_reference_injection=True,
        introduction_frame_synthesis=True,
    )
    synthesis = IntroductionBoundaryProviderCapabilities(
        provider_id="ltx-2.5",
        introduction_frame_synthesis=True,
        first_frame_i2v=True,
    )
    manual = IntroductionBoundaryProviderCapabilities(provider_id="legacy")

    assert IntroductionBoundaryAutomationPlanner.choose(native) is IntroductionBoundaryStrategy.PROVIDER_NATIVE
    assert (
        IntroductionBoundaryAutomationPlanner.choose(synthesis)
        is IntroductionBoundaryStrategy.SYNTHESIZED_KEYFRAME
    )
    assert IntroductionBoundaryAutomationPlanner.choose(manual) is IntroductionBoundaryStrategy.MANUAL_FALLBACK


def test_first_span_can_be_materialized_before_introduction_keyframe_exists(
    tmp_path: Path,
) -> None:
    package_path, _ = _candidate_package(tmp_path)
    builder = LTX25TimedSpanAcceptancePackageBuilder(tmp_path)

    first_path = builder.build_span(package_path, 1)
    first = json.loads(first_path.read_text(encoding="utf-8"))

    assert first["frame_count"] == 96
    assert first["provider_execution_plan"]["provider_frame_count"] == 97
    assert first["timed_span_execution"]["global_through_frame"] == 95

    with pytest.raises(TimedSpanAcceptancePackageError, match="blocked until"):
        builder.build_span(package_path, 2)


def test_automated_validated_keyframe_requires_provenance_record(tmp_path: Path) -> None:
    _, requirements = _candidate_package(tmp_path)
    requirement = requirements.requirements[0]
    source = tmp_path / "automation" / "source.png"
    target = tmp_path / "automation" / "target.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source")
    target.write_bytes(b"target")

    with pytest.raises(GovernedIntroductionKeyframeError, match="automation_record_path"):
        GovernedIntroductionKeyframeStore.create_record(
            requirement,
            image_path=target.relative_to(tmp_path).as_posix(),
            image_sha256=_sha(target),
            source_boundary_image_path=source.relative_to(tmp_path).as_posix(),
            source_boundary_image_sha256=_sha(source),
            approved_by="VSCS Automated Boundary Synthesis",
            approved_at="2026-09-26T10:05:00+02:00",
            approval_mode="automated_validated",
        )


def test_automated_validated_keyframe_round_trips_and_unblocks_second_span(
    tmp_path: Path,
) -> None:
    package_path, requirements = _candidate_package(tmp_path)
    requirement = requirements.requirements[0]
    directory = tmp_path / ".vscs" / "automated_introduction_boundaries" / requirement.shot_id
    directory.mkdir(parents=True, exist_ok=True)
    source = directory / "frame-95.png"
    target = directory / "frame-96.png"
    automation = directory / "automation.json"
    source.write_bytes(b"source-95")
    target.write_bytes(b"target-96")
    automation.write_text('{"state":"validated"}', encoding="utf-8")

    store = GovernedIntroductionKeyframeStore(tmp_path)
    record = store.create_record(
        requirement,
        image_path=target.relative_to(tmp_path).as_posix(),
        image_sha256=_sha(target),
        source_boundary_image_path=source.relative_to(tmp_path).as_posix(),
        source_boundary_image_sha256=_sha(source),
        approved_by="VSCS Automated Boundary Synthesis",
        approved_at="2026-09-26T10:05:00+02:00",
        acceptance_criteria=INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
        approval_mode="automated_validated",
        automation_record_path=automation.relative_to(tmp_path).as_posix(),
    )
    store.save(record, requirement)

    restored = store.require_approved(requirement)
    assert restored.approval_mode == "automated_validated"
    assert restored.automation_record_path == automation.relative_to(tmp_path).as_posix()

    second_path = LTX25TimedSpanAcceptancePackageBuilder(tmp_path).build_span(package_path, 2)
    second = json.loads(second_path.read_text(encoding="utf-8"))
    assert second["frame_count"] == 48
    assert second["provider_execution_plan"]["provider_frame_count"] == 49
    assert second["governed_keyframe"]["approval_mode"] == "automated_validated"
    assert second["timed_span_execution"]["global_start_frame"] == 96


def test_human_keyframe_records_remain_backward_compatible(tmp_path: Path) -> None:
    _, requirements = _candidate_package(tmp_path)
    requirement = requirements.requirements[0]
    source = tmp_path / "source.png"
    target = tmp_path / "target.png"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    store = GovernedIntroductionKeyframeStore(tmp_path)
    record = store.create_record(
        requirement,
        image_path="target.png",
        image_sha256=_sha(target),
        source_boundary_image_path="source.png",
        source_boundary_image_sha256=_sha(source),
        approved_by="Neill Payne",
        approved_at="2026-09-26T10:10:00+02:00",
    )
    store.save(record, requirement)

    restored = store.require_approved(requirement)
    assert restored.approval_mode == "human"
    assert restored.automation_record_path is None


class _AutomationFacadeBackend:
    def __init__(self) -> None:
        self.profile: str | None = None

    def run_automated_timed_span_orchestration_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> AutomatedTimedSpanOrchestrationResult:
        assert task_id == "PT-TIMED"
        self.profile = profile
        return AutomatedTimedSpanOrchestrationResult(
            shot_id="EP-001-SCN-001-SHT-002",
            state="accepted",
            span_outputs=(Path("span-001.mp4"), Path("span-002.mp4")),
            assembled_output=Path("assembled.mp4"),
            message="Automated.",
        )


def test_ui_facade_delegates_automated_orchestration_with_normalized_profile() -> None:
    backend = _AutomationFacadeBackend()
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    result = service.run_automated_timed_span_orchestration(
        "PT-TIMED",
        profile="Production",
    )

    assert result.state == "accepted"
    assert backend.profile == "production"
