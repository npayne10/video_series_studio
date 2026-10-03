from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from vscs.application.production_execution import (
    GovernedInternalRenderSpanCompiler,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirementPlan,
    TimedCanonicalReferenceActivationCompiler,
)
from vscs.application.production_execution.package_compilation import CompiledProductionPackage
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution import (
    MiniMaxH3FunctionalAcceptanceService,
    MiniMaxH3FunctionalAcceptanceState,
    MiniMaxH3MediaObservation,
    MiniMaxH3VisualObservation,
)
from vscs.infrastructure.production_execution.minimax_h3_span_adapter import (
    MiniMaxH3SpanAdapterCompiler,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reference(reference_id: str, asset_id: str, role: str, label: str) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "asset_id": asset_id,
        "role": role,
        "label": label,
        "reference_class": "provider_ready_derivative",
        "priority": "required",
        "subject_type": "character",
        "source_path": f"references/{reference_id}.png",
        "provider_ready": True,
        "file_checksum": f"sha-{reference_id}",
        "reference_fingerprint": f"fp-{reference_id}",
    }


def _reference_plan() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "status": "passed",
        "references": [
            _reference("REF-JAMES", "CAP-CHR-001", "primary_identity", "Commander James Spence"),
            _reference("REF-SANDRA", "CAP-CHR-003", "secondary_identity", "Sandra Crawford"),
            _reference("REF-BRIDGE", "CAP-LOC-021", "environment_reference", "Iron Horizon bridge"),
            _reference("REF-XORIX", "CAP-PLN-002", "environment_reference", "Xorix"),
            _reference("REF-ROS", "CAP-CHR-005", "secondary_identity", "Major Ros Rohsgard"),
        ],
        "diagnostics": [],
    }


def _compiled(project: Path) -> CompiledProductionPackage:
    timed = TimedAssetPresencePlan(
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
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-BRIDGE",),
            ),
            TimedAssetPresence(
                asset_id="CAP-PLN-002",
                asset_kind=TimedAssetKind.PLANET,
                from_frame=0,
                through_frame=143,
                canonical_reference_ids=("REF-XORIX",),
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
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        _reference_plan(),
    )
    requirements = GovernedIntroductionKeyframeRequirementCompiler().compile(
        spans,
        activation,
    )
    opening = project / "boundaries" / "shot-opening.png"
    opening.parent.mkdir(parents=True, exist_ok=True)
    opening.write_bytes(b"governed-opening")
    assets = [
        {"asset_id": "CAP-CHR-001", "name": "Commander James Spence", "category": "character"},
        {"asset_id": "CAP-CHR-003", "name": "Sandra Crawford", "category": "character"},
        {"asset_id": "CAP-CHR-005", "name": "Major Ros Rohsgard", "category": "character"},
        {"asset_id": "CAP-LOC-021", "name": "Iron Horizon bridge", "category": "location"},
        {"asset_id": "CAP-PLN-002", "name": "Xorix", "category": "planet"},
    ]
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
        positive_prompt=(
            "Create a photorealistic bridge shot. "
            "James remains left. Sandra remains right. "
            "Ros Rohsgard enters naturally from the far left edge. "
            "Xorix remains visible."
        ),
        negative_prompt="extra people; identity swap; do not duplicate Ros; warped faces",
        motion_prompt="James and Sandra remain stable. Ros enters naturally from the left edge.",
        previous_approved_final_frame=str(opening.relative_to(project)),
        filename_prefix="XORIX/EP-001/PT-VIDEO-SHT-002",
        width=1280,
        height=720,
        frame_count=144,
        frames_per_second=24,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=42,
        composition_plan={"assets": assets},
        production_authority={"assets": assets},
        package_fingerprint="package-fingerprint",
        timed_asset_presence=timed.to_dict(),
        internal_render_spans=spans.to_dict(),
        timed_reference_activation=activation.to_dict(),
        reference_plan=_reference_plan(),
        introduction_keyframe_requirements=requirements.to_dict(),
    )


def _approve_intro(project: Path, compiled: CompiledProductionPackage) -> None:
    raw = compiled.introduction_keyframe_requirements
    assert isinstance(raw, dict)
    requirement = IntroductionKeyframeRequirementPlan.from_dict(raw).requirements[0]
    source = project / "boundaries" / "frame-000095.png"
    intro = project / "keyframes" / "frame-000096.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    intro.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"frame-95")
    intro.write_bytes(b"frame-96-with-ros")
    store = GovernedIntroductionKeyframeStore(project)
    record = store.create_record(
        requirement,
        image_path=intro.relative_to(project).as_posix(),
        image_sha256=_sha(intro),
        source_boundary_image_path=source.relative_to(project).as_posix(),
        source_boundary_image_sha256=_sha(source),
        approved_by="Neill Payne",
        approved_at="2026-10-03T14:00:00+02:00",
    )
    store.save(record, requirement)


class _Probe:
    def __init__(self, facts: dict[str, MiniMaxH3MediaObservation]) -> None:
        self.facts = facts

    def observe(self, path: Path) -> MiniMaxH3MediaObservation:
        return self.facts[path.name]


def _prepare_evidence(project: Path, compiled: CompiledProductionPackage) -> _Probe:
    plan = MiniMaxH3SpanAdapterCompiler(project).compile(compiled)
    root = project / ".vscs" / "h3_span_orchestration" / compiled.task_id / plan.plan_id
    normalized = root / "normalized"
    normalized.mkdir(parents=True, exist_ok=True)
    span1 = normalized / "span-001.mp4"
    span2 = normalized / "span-002.mp4"
    final = root / f"{compiled.shot_id}-governed-h3-assembled.mp4"
    for path in (span1, span2, final):
        path.write_bytes(b"video")
    spans = []
    for execution, normalized_path in zip(plan.spans, (span1, span2), strict=True):
        raw = project / f"raw-{execution.sequence_number:03d}.mp4"
        raw.write_bytes(b"raw")
        spans.append(
            {
                **execution.to_dict(),
                "raw_output_path": str(raw),
                "normalized_output_path": str(normalized_path),
            }
        )
    manifest = {
        "schema_version": "1.0",
        "provider": plan.provider_id,
        "mode": plan.mode,
        "shot_id": compiled.shot_id,
        "task_id": compiled.task_id,
        "source_package_fingerprint": compiled.package_fingerprint,
        "plan_id": plan.plan_id,
        "plan_fingerprint": plan.fingerprint,
        "assembly_policy": "concatenate_normalized_span_outputs_in_sequence",
        "spans": spans,
        "final_path": str(final),
        "final_frame_count": compiled.frame_count,
        "frames_per_second": compiled.frames_per_second,
    }
    (root / "orchestration.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _Probe(
        {
            span1.name: MiniMaxH3MediaObservation(96, 24, 1280, 720),
            span2.name: MiniMaxH3MediaObservation(48, 24, 1280, 720),
            final.name: MiniMaxH3MediaObservation(144, 24, 1280, 720),
        }
    )


def _passing_visual() -> MiniMaxH3VisualObservation:
    return MiniMaxH3VisualObservation(
        james_sandra_present_frames_0_95=True,
        ros_absent_frames_0_95=True,
        ros_first_visible_frame_96=True,
        ros_continues_frames_96_143=True,
        no_extra_people=True,
        james_sandra_continuity_maintained=True,
        central_chair_continuity_maintained=True,
        bridge_xorix_coherent=True,
        no_provider_guide_cut=True,
        approved_by="Neill Payne",
    )


def test_h3_functional_acceptance_waits_for_visual_qc_after_technical_pass(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)

    report = MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled)

    assert report.state is MiniMaxH3FunctionalAcceptanceState.PENDING_VISUAL_QC
    assert report.technical_passed is True
    assert report.final_frame_count == 144
    assert report.frames_per_second == 24


def test_h3_functional_acceptance_passes_only_all_real_sht002_gates(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)

    report = MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled, visual_observation=_passing_visual())

    assert report.state is MiniMaxH3FunctionalAcceptanceState.PASSED
    assert report.passed is True
    assert report.visual_failures == ()


def test_h3_functional_acceptance_fails_if_ros_appears_before_frame_96(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)
    visual = _passing_visual()
    failing = replace(visual, ros_absent_frames_0_95=False)

    report = MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled, visual_observation=failing)

    assert report.state is MiniMaxH3FunctionalAcceptanceState.FAILED
    assert "Ros absent through frames 0-95" in report.visual_failures


def test_h3_functional_acceptance_detects_manifest_reference_or_prompt_tamper(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)
    plan = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)
    manifest_path = (
        tmp_path
        / ".vscs"
        / "h3_span_orchestration"
        / compiled.task_id
        / plan.plan_id
        / "orchestration.json"
    )
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["spans"][0]["positive_prompt"] += " Ros enters later."
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    report = MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled)

    assert report.state is MiniMaxH3FunctionalAcceptanceState.FAILED
    assert any("positive_prompt" in item for item in report.technical_failures)


def test_h3_functional_acceptance_detects_wrong_final_frame_count(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)
    probe.facts[f"{compiled.shot_id}-governed-h3-assembled.mp4"] = (
        MiniMaxH3MediaObservation(143, 24, 1280, 720)
    )

    report = MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled)

    assert report.state is MiniMaxH3FunctionalAcceptanceState.FAILED
    assert any("143 frames" in item for item in report.technical_failures)


def test_h3_functional_acceptance_detects_wrong_normalized_span_count(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)
    probe.facts["span-002.mp4"] = MiniMaxH3MediaObservation(47, 24, 1280, 720)

    report = MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled)

    assert report.state is MiniMaxH3FunctionalAcceptanceState.FAILED
    assert any("Normalized span 2 has 47 frames" in item for item in report.technical_failures)


def test_h3_functional_acceptance_persists_report_and_visual_evidence(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    probe = _prepare_evidence(tmp_path, compiled)
    plan = MiniMaxH3SpanAdapterCompiler(tmp_path).compile(compiled)

    MiniMaxH3FunctionalAcceptanceService(
        tmp_path,
        media_probe=probe,
    ).evaluate(compiled, visual_observation=_passing_visual())

    path = (
        tmp_path
        / ".vscs"
        / "h3_span_orchestration"
        / compiled.task_id
        / plan.plan_id
        / "functional_acceptance.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["report"]["state"] == "passed"
    assert payload["report"]["passed"] is True
    assert payload["visual_observation"]["ros_first_visible_frame_96"] is True


def test_h3_functional_acceptance_checks_all_nine_visual_criteria(tmp_path: Path) -> None:
    visual = _passing_visual()
    assert visual.passed is True
    assert visual.failed_criteria == ()
