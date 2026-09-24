from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vscs.application.production_execution import (
    INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA,
    KEYFRAME_ACCEPTANCE_CRITERIA,
    CompiledProductionPackage,
    GovernedInternalRenderSpanCompiler,
    GovernedInternalRenderSpanPlan,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedShotKeyframe,
    GovernedShotKeyframeStore,
    IntroductionKeyframeRequirementPlan,
    ProductionExecutionCandidate,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
    TimedCanonicalReferenceActivationCompiler,
    TimedCanonicalReferenceActivationPlan,
    TimedSpanAcceptanceEvaluator,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    TimedSpanAcceptanceStore,
    TimedSpanAssemblyEvidence,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    CurrentAuthorityLTX25GovernedKeyframeCompilationService,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
    TimedSpanAcceptancePackageError,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    GovernedSpanAssemblyRuntimeError,
    SpanMediaObservation,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_service import (
    TimedSpanFunctionalAcceptanceService,
)
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


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
            ),
        ),
    )


def _reference(
    reference_id: str,
    role: str,
    asset_id: str | None,
) -> dict[str, object]:
    return {
        "reference_id": reference_id,
        "role": role,
        "asset_id": asset_id,
        "reference_class": (
            "shot_composite" if role == "scene_composition_anchor" else "provider_ready_derivative"
        ),
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
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx-2.5",
        },
        "references": [
            _reference("REF-COMPOSITION", "scene_composition_anchor", None),
            _reference("REF-JAMES-PRIMARY", "primary_identity", "CAP-CHR-001"),
            _reference("REF-SANDRA-PRIMARY", "secondary_identity", "CAP-CHR-003"),
            _reference(
                "REF-IRON-HORIZON-BRIDGE",
                "environment_reference",
                "CAP-LOC-021",
            ),
            _reference("REF-ROS-PRIMARY", "secondary_identity", "CAP-CHR-004"),
        ],
        "diagnostics": [],
    }


def _authority() -> tuple[
    TimedAssetPresencePlan,
    GovernedInternalRenderSpanPlan,
    TimedCanonicalReferenceActivationPlan,
    IntroductionKeyframeRequirementPlan,
]:
    timed = _timed()
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
    return timed, spans, activation, requirements


def _candidate_package(project: Path) -> tuple[Path, dict[str, object]]:
    timed, spans, activation, requirements = _authority()
    opening = project / "keyframes" / "opening.png"
    opening.parent.mkdir(parents=True, exist_ok=True)
    opening.write_bytes(b"approved-opening-frame")
    raw: dict[str, object] = {
        "schema_version": "7.2.2-vscs-1",
        "status": "TIMED_SPAN_ACCEPTANCE_REQUIRED",
        "profile": "production",
        "target_description": "Governed dynamic shot.",
        "shot_prompt": "continue",
        "positive_prompt": "continue",
        "motion_prompt": "continue",
        "negative_prompt": "no identity drift",
        "filename_prefix": "XORIX/EP-001/PT-VIDEO-SHT-002",
        "width": 1280,
        "height": 720,
        "frame_count": 144,
        "fps": 24,
        "cfg": 1.0,
        "ic_lora_strength": 1.0,
        "seed": 42,
        "composition_plan": {},
        "production_authority": {},
        "timed_asset_presence": timed.to_dict(),
        "internal_render_spans": spans.to_dict(),
        "timed_reference_activation": activation.to_dict(),
        "introduction_keyframe_requirements": requirements.to_dict(),
        "governed_keyframe": {
            "schema_version": "1.0",
            "shot_id": timed.shot_id,
            "image_path": str(opening),
            "image_sha256": _sha(opening),
            "approved_by": "Neill Payne",
            "approved_at": "2026-09-24T11:00:00+02:00",
            "acceptance_criteria": list(KEYFRAME_ACCEPTANCE_CRITERIA),
            "status": "approved",
            "source_kind": "human_approved_shot_composition",
        },
        "provider_video_rebaseline": {"active_candidate": "C"},
        "provider_execution_plan": {
            "provider": "ltx-2.5",
            "mode": "governed_multi_span_functional_acceptance",
            "governed_frame_count": 144,
            "provider_frame_count": 145,
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
    return path, raw


def _approve_intro(project: Path, package_path: Path) -> str:
    service = TimedSpanFunctionalAcceptanceService(project)
    requirement = service.requirements(package_path)[0]
    source = project / "boundaries" / "span-001-frame-95.png"
    intro = project / "keyframes" / "span-002-frame-96.png"
    source.parent.mkdir(parents=True, exist_ok=True)
    intro.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"frame-95")
    intro.write_bytes(b"frame-96-with-ros")
    status = service.approve_introduction_keyframe(
        package_path,
        requirement_id=requirement.requirement_id,
        image_path=intro,
        source_boundary_image_path=source,
        approved_by="Neill Payne",
        approved_at="2026-09-24T11:05:00+02:00",
    )
    assert status.approved_keyframe_count == 1
    return requirement.requirement_id


def _record_assembly(project: Path, raw: dict[str, object]) -> None:
    spans_raw = raw["internal_render_spans"]
    assert isinstance(spans_raw, dict)
    spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
    span1 = project / "acceptance" / "span-001.mp4"
    span2 = project / "acceptance" / "span-002.mp4"
    final = project / "acceptance" / "assembled.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    span1.write_bytes(b"normalized-span-1")
    span2.write_bytes(b"normalized-span-2")
    final.write_bytes(b"assembled-144")
    evidence = TimedSpanAssemblyEvidence(
        shot_id=spans.shot_id,
        source_span_plan_id=spans.plan_id,
        source_span_plan_fingerprint=spans.fingerprint,
        span_ids=tuple(span.span_id for span in spans.spans),
        span_paths=(str(span1), str(span2)),
        span_sha256=(_sha(span1), _sha(span2)),
        span_frame_counts=(96, 48),
        final_path=str(final),
        final_frame_count=144,
        width=1280,
        height=720,
        frames_per_second=24,
        final_sha256=_sha(final),
        recorded_at="2026-09-24T11:10:00+02:00",
    )
    TimedSpanAcceptanceStore(project).save_assembly(evidence)


def test_timed_span_acceptance_progresses_keyframe_assembly_qc(tmp_path: Path) -> None:
    package_path, raw = _candidate_package(tmp_path)
    evaluator = TimedSpanAcceptanceEvaluator(tmp_path)

    first = evaluator.evaluate(raw)
    assert first.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert len(first.pending_keyframe_requirement_ids) == 1

    requirement_id = _approve_intro(tmp_path, package_path)
    after_keyframe = TimedSpanFunctionalAcceptanceService(tmp_path).status(package_path)
    assert after_keyframe.state is TimedSpanAcceptanceState.OUTPUTS_REQUIRED
    assert after_keyframe.pending_keyframe_requirement_ids == ()

    _record_assembly(tmp_path, raw)
    after_assembly = TimedSpanFunctionalAcceptanceService(tmp_path).status(package_path)
    assert after_assembly.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert after_assembly.final_frame_count == 144
    assert after_assembly.pending_qc_requirement_ids == (requirement_id,)

    accepted = TimedSpanFunctionalAcceptanceService(tmp_path).record_visual_qc(
        package_path,
        requirement_id=requirement_id,
        absent_before_boundary=True,
        present_from_target_frame=True,
        source_continuity_preserved=True,
        no_unapproved_assets=True,
        approved_by="Neill Payne",
        notes="Ros absent through frame 95 and present from frame 96.",
    )
    assert accepted.state is TimedSpanAcceptanceState.ACCEPTED
    assert accepted.accepted
    assert accepted.final_frame_count == 144
    assert accepted.pending_qc_requirement_ids == ()


def test_failed_visual_qc_does_not_accept_timed_span_shot(tmp_path: Path) -> None:
    package_path, raw = _candidate_package(tmp_path)
    requirement_id = _approve_intro(tmp_path, package_path)
    _record_assembly(tmp_path, raw)

    status = TimedSpanFunctionalAcceptanceService(tmp_path).record_visual_qc(
        package_path,
        requirement_id=requirement_id,
        absent_before_boundary=False,
        present_from_target_frame=True,
        source_continuity_preserved=True,
        no_unapproved_assets=True,
        approved_by="Reviewer",
        notes="Ros was visible too early.",
    )

    assert status.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert status.qc_passed_count == 0


def test_visual_qc_history_is_append_only_and_latest_record_controls_state(
    tmp_path: Path,
) -> None:
    package_path, raw = _candidate_package(tmp_path)
    requirement_id = _approve_intro(tmp_path, package_path)
    _record_assembly(tmp_path, raw)
    service = TimedSpanFunctionalAcceptanceService(tmp_path)

    failed = service.record_visual_qc(
        package_path,
        requirement_id=requirement_id,
        absent_before_boundary=False,
        present_from_target_frame=True,
        source_continuity_preserved=True,
        no_unapproved_assets=True,
        approved_by="Reviewer",
        notes="Ros appeared before frame 96.",
    )
    assert failed.state is TimedSpanAcceptanceState.QC_REQUIRED

    passed = service.record_visual_qc(
        package_path,
        requirement_id=requirement_id,
        absent_before_boundary=True,
        present_from_target_frame=True,
        source_continuity_preserved=True,
        no_unapproved_assets=True,
        approved_by="Reviewer",
        notes="Corrected acceptance render.",
    )
    assert passed.state is TimedSpanAcceptanceState.ACCEPTED

    store_path = tmp_path / ".vscs" / "timed_span_acceptance.json"
    raw_store = json.loads(store_path.read_text(encoding="utf-8"))
    records = raw_store["qc_records"]
    assert len(records) == 2
    assert records[0]["passed"] is False
    assert records[1]["passed"] is True


def test_assembly_evidence_becomes_invalid_when_final_media_changes(tmp_path: Path) -> None:
    package_path, raw = _candidate_package(tmp_path)
    _approve_intro(tmp_path, package_path)
    _record_assembly(tmp_path, raw)

    accepted_store = TimedSpanAcceptanceStore(tmp_path)
    evidence = accepted_store.require_current_assembly("EP-001-SCN-001-SHT-002")
    assert evidence is not None
    Path(evidence.final_path).write_bytes(b"changed-after-assembly")

    status = TimedSpanFunctionalAcceptanceService(tmp_path).status(package_path)

    assert status.state is TimedSpanAcceptanceState.OUTPUTS_REQUIRED
    assert not status.assembly_present


def test_timed_span_package_builder_emits_97_and_49_frame_candidate_c_packages(
    tmp_path: Path,
) -> None:
    package_path, _ = _candidate_package(tmp_path)
    _approve_intro(tmp_path, package_path)

    package_set = LTX25TimedSpanAcceptancePackageBuilder(tmp_path).build(package_path)

    assert len(package_set.package_paths) == 2
    first = json.loads(package_set.package_paths[0].read_text(encoding="utf-8"))
    second = json.loads(package_set.package_paths[1].read_text(encoding="utf-8"))

    assert first["frame_count"] == 96
    assert first["provider_execution_plan"]["provider_frame_count"] == 97
    assert first["provider_execution_plan"]["provider_trim_frames"] == 1
    assert first["timed_span_execution"]["global_start_frame"] == 0
    assert first["timed_span_execution"]["global_through_frame"] == 95
    assert first["timed_span_execution"]["direct_provider_reference_ids"] == []
    assert "Do not introduce any new subject" in first["motion_prompt"]

    assert second["frame_count"] == 48
    assert second["provider_execution_plan"]["provider_frame_count"] == 49
    assert second["provider_execution_plan"]["provider_trim_frames"] == 1
    assert second["timed_span_execution"]["global_start_frame"] == 96
    assert second["timed_span_execution"]["global_through_frame"] == 143
    assert second["timed_span_execution"]["conditioning_frame_global_index"] == 96
    assert second["timed_span_execution"]["preceding_boundary_global_frame_index"] == 95
    assert second["timed_span_execution"]["preceding_boundary_frame_reemitted"] is False
    assert second["governed_keyframe"]["source_kind"] == "governed_introduction_keyframe"
    assert second["governed_keyframe"]["acceptance_criteria"] == list(
        INTRODUCTION_KEYFRAME_ACCEPTANCE_CRITERIA
    )
    assert (
        first["_vscs_manifest"]["package_fingerprint"]
        != second["_vscs_manifest"]["package_fingerprint"]
    )
    assert not (tmp_path / ".vscs" / "provider_executions").exists()


def test_timed_span_package_builder_fails_closed_without_introduction_keyframe(
    tmp_path: Path,
) -> None:
    package_path, _ = _candidate_package(tmp_path)

    with pytest.raises(TimedSpanAcceptancePackageError, match="blocked until"):
        LTX25TimedSpanAcceptancePackageBuilder(tmp_path).build(package_path)


class _FakeAssemblyRuntime(GovernedSpanAssemblyRuntime):
    def __init__(
        self,
        project_directory: Path,
        observations: dict[str, SpanMediaObservation],
    ) -> None:
        super().__init__(project_directory)
        self.observations = observations

    def _verify_boundary_evidence(
        self,
        compiled_package: dict[str, object],
        spans: object,
        observations: tuple[SpanMediaObservation, ...],
    ) -> None:
        del compiled_package, spans, observations

    def _observe(self, path: Path) -> SpanMediaObservation:
        key = str(Path(path).resolve(strict=False))
        observation = self.observations.get(key)
        if observation is None:
            raise GovernedSpanAssemblyRuntimeError(f"No fake observation for {key}")
        return observation

    def _assemble(self, paths: tuple[Path, ...], destination: Path) -> None:
        assert len(paths) == 2
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"assembled")
        self.observations[str(destination.resolve(strict=False))] = SpanMediaObservation(
            path=destination.resolve(strict=False),
            frame_count=144,
            width=1280,
            height=720,
            frames_per_second=24,
        )


class _BoundaryEvidenceRuntime(_FakeAssemblyRuntime):
    def __init__(
        self,
        project_directory: Path,
        observations: dict[str, SpanMediaObservation],
        *,
        boundary_matches: bool,
    ) -> None:
        super().__init__(project_directory, observations)
        self.boundary_matches = boundary_matches

    def _verify_boundary_evidence(
        self,
        compiled_package: dict[str, object],
        spans: object,
        observations: tuple[SpanMediaObservation, ...],
    ) -> None:
        from vscs.application.production_execution import GovernedInternalRenderSpanPlan

        assert isinstance(spans, GovernedInternalRenderSpanPlan)
        GovernedSpanAssemblyRuntime._verify_boundary_evidence(
            self,
            compiled_package,  # type: ignore[arg-type]
            spans,
            observations,
        )

    def _decoded_rgb_sha256(
        self,
        path: Path,
        *,
        frame_index: int | None,
    ) -> str:
        name = Path(path).name
        if name == "span1.mp4" and frame_index == 95:
            return "same-boundary-pixels"
        if name == "span-001-frame-95.png" and frame_index is None:
            return "same-boundary-pixels" if self.boundary_matches else "wrong-boundary-pixels"
        return f"pixels-{name}-{frame_index}"


def test_assembly_requires_source_boundary_pixels_to_match_actual_frame_95(
    tmp_path: Path,
) -> None:
    package_path, raw = _candidate_package(tmp_path)
    _approve_intro(tmp_path, package_path)
    span1 = tmp_path / "span1.mp4"
    span2 = tmp_path / "span2.mp4"
    span1.write_bytes(b"span1")
    span2.write_bytes(b"span2")
    observations = {
        str(span1.resolve()): SpanMediaObservation(span1.resolve(), 96, 1280, 720, 24),
        str(span2.resolve()): SpanMediaObservation(span2.resolve(), 48, 1280, 720, 24),
    }

    runtime = _BoundaryEvidenceRuntime(
        tmp_path,
        observations,
        boundary_matches=True,
    )
    evidence = runtime.assemble(
        raw,
        (span1, span2),
        tmp_path / "Media Output" / "boundary-verified.mp4",
    )
    assert evidence.final_frame_count == 144

    with pytest.raises(GovernedSpanAssemblyRuntimeError, match="exact final frame"):
        _BoundaryEvidenceRuntime(
            tmp_path,
            observations,
            boundary_matches=False,
        ).assemble(
            raw,
            (span1, span2),
            tmp_path / "Media Output" / "boundary-rejected.mp4",
        )


def test_assembly_runtime_proves_exact_144_frame_output(tmp_path: Path) -> None:
    _, raw = _candidate_package(tmp_path)
    span1 = tmp_path / "span1.mp4"
    span2 = tmp_path / "span2.mp4"
    span1.write_bytes(b"span1")
    span2.write_bytes(b"span2")
    observations = {
        str(span1.resolve()): SpanMediaObservation(span1.resolve(), 96, 1280, 720, 24),
        str(span2.resolve()): SpanMediaObservation(span2.resolve(), 48, 1280, 720, 24),
    }
    runtime = _FakeAssemblyRuntime(tmp_path, observations)

    evidence = runtime.assemble(
        raw,
        (span1, span2),
        tmp_path / "Media Output" / "SHT-002-assembled.mp4",
    )

    assert evidence.span_frame_counts == (96, 48)
    assert evidence.final_frame_count == 144
    assert evidence.span_sha256 == (_sha(span1), _sha(span2))
    assert (
        TimedSpanAcceptanceStore(tmp_path).require_current_assembly("EP-001-SCN-001-SHT-002")
        == evidence
    )


def test_assembly_runtime_rejects_untrimmed_provider_span(tmp_path: Path) -> None:
    _, raw = _candidate_package(tmp_path)
    span1 = tmp_path / "span1.mp4"
    span2 = tmp_path / "span2.mp4"
    span1.write_bytes(b"span1")
    span2.write_bytes(b"span2")
    observations = {
        str(span1.resolve()): SpanMediaObservation(span1.resolve(), 97, 1280, 720, 24),
        str(span2.resolve()): SpanMediaObservation(span2.resolve(), 48, 1280, 720, 24),
    }

    with pytest.raises(GovernedSpanAssemblyRuntimeError, match="requires 96"):
        _FakeAssemblyRuntime(tmp_path, observations).assemble(
            raw,
            (span1, span2),
            tmp_path / "Media Output" / "bad.mp4",
        )


def test_candidate_c_dynamic_payload_compiles_for_acceptance_but_not_monolithic_execution(
    tmp_path: Path,
) -> None:
    timed, spans, activation, requirements = _authority()
    opening = tmp_path / "opening.png"
    opening.write_bytes(b"opening")
    GovernedShotKeyframeStore(tmp_path).save(
        GovernedShotKeyframe(
            shot_id=timed.shot_id,
            image_path=opening.relative_to(tmp_path).as_posix(),
            image_sha256=_sha(opening),
            approved_by="Neill Payne",
            approved_at="2026-09-24T11:00:00+02:00",
            acceptance_criteria=KEYFRAME_ACCEPTANCE_CRITERIA,
        )
    )
    compiled = CompiledProductionPackage(
        task_id="PT-VIDEO-SHT-002",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=timed.shot_id,
        profile="production",
        authority_id="UPD-SHT-002",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="Neill Payne",
        source_package_id="PP-SHT-002",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="dynamic acceptance",
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
        production_authority={
            "continuity": {"shot_boundary_mode": "new_composition"},
            "dialogue": [],
            "action_performance": {"spoken_content": ""},
        },
        package_fingerprint="placeholder",
        timed_asset_presence=timed.to_dict(),
        internal_render_spans=spans.to_dict(),
        timed_reference_activation=activation.to_dict(),
        introduction_keyframe_requirements=requirements.to_dict(),
        reference_plan=_reference_plan(),
        motion_prompt="continue",
    )

    payload = CurrentAuthorityLTX25GovernedKeyframeCompilationService(tmp_path)._comfyui_payload(
        compiled
    )

    assert payload["status"] == "TIMED_SPAN_ACCEPTANCE_REQUIRED"
    assert payload["provider_execution_plan"]["mode"] == (
        "governed_multi_span_functional_acceptance"
    )
    assert payload["provider_execution_plan"]["automatic_provider_submission"] is False
    assert payload["provider_execution_plan"]["monolithic_submission_permitted"] is False
    assert "reference_plan" not in payload


class _TimedSpanFacadeBackend:
    def __init__(self) -> None:
        self.profile: str | None = None

    def timed_span_acceptance_status_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> TimedSpanAcceptanceStatus:
        assert task_id == "PT-TIMED"
        self.profile = profile
        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-001-SHT-002",
            state=TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=0,
            qc_passed_count=0,
            assembly_present=False,
            message="Introduction Keyframe required.",
            requirement_ids=("GIKR-001",),
            pending_keyframe_requirement_ids=("GIKR-001",),
            pending_qc_requirement_ids=("GIKR-001",),
        )


def test_ui_service_delegates_timed_span_status_with_normalized_profile() -> None:
    backend = _TimedSpanFacadeBackend()
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    status = service.timed_span_acceptance_status("PT-TIMED", profile="Production")

    assert status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert backend.profile == "production"


class _TimedSpanWorkspaceService:
    def __init__(self, package_path: Path, status_state: TimedSpanAcceptanceState) -> None:
        self.package_path = package_path
        self.status_state = status_state
        self.candidate = ProductionExecutionCandidate(
            production_id="XORIX",
            task_id="PT-UI-TIMED-SPAN",
            task_type=ProductionTaskType.VIDEO_GENERATION,
            task_state=ProductionTaskState.READY,
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="EP-001-SCN-001-SHT-002",
            resource_id="GPU-01",
            queue_entry_id="PQE-UI-TIMED-SPAN",
            label="Video Generation — SHT-002",
        )

    def candidates(self) -> tuple[ProductionExecutionCandidate, ...]:
        return (self.candidate,)

    def package_status(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        assert task_id == self.candidate.task_id
        return ProductionPackageStatus(
            task_id=task_id,
            state=ProductionPackageCompilationState.COMPILED,
            profile=profile,
            path=self.package_path,
            authority_fingerprint="authority",
            package_fingerprint="package",
            source_package_id="PP-SHT-002",
            message="Compiled",
        )

    def has_execution(self, task_id: str, *, profile: str | None = None) -> bool:
        assert task_id == self.candidate.task_id
        return False

    def retry_override_status(self, task_id: str, *, profile: str | None = None) -> object:
        raise RuntimeError("not needed for this UI test")

    def shot_boundary_status(self, task_id: str, *, profile: str | None = None) -> object:
        raise RuntimeError("not needed for this UI test")

    def timed_span_acceptance_status(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> object:
        assert task_id == self.candidate.task_id
        if self.status_state is TimedSpanAcceptanceState.NOT_APPLICABLE:
            from vscs.application.production_execution import TimedSpanAcceptanceStatus

            return TimedSpanAcceptanceStatus(
                shot_id="EP-001-SCN-001-SHT-002",
                state=self.status_state,
                span_count=1,
                boundary_count=0,
                requirement_count=0,
                approved_keyframe_count=0,
                qc_passed_count=0,
                assembly_present=False,
                message="Monolithic.",
            )
        from vscs.application.production_execution import TimedSpanAcceptanceStatus

        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-001-SHT-002",
            state=self.status_state,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=0,
            qc_passed_count=0,
            assembly_present=False,
            message="One governed Introduction Keyframe approval remains.",
            requirement_ids=("GIKR-001",),
            pending_keyframe_requirement_ids=("GIKR-001",),
            pending_qc_requirement_ids=("GIKR-001",),
        )


def test_workspace_surfaces_timed_span_acceptance_and_blocks_monolithic_start(
    qtbot,
    tmp_path: Path,
) -> None:
    package = tmp_path / "production_package.json"
    package.write_text("{}", encoding="utf-8")
    service = _TimedSpanWorkspaceService(
        package,
        TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
    )
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)

    workspace.refresh()
    workspace.table.selectRow(0)

    assert "KEYFRAME_REQUIRED" in workspace.timed_span_state.text()
    assert "Spans 2" in workspace.timed_span_detail.text()
    assert workspace.approve_introduction_keyframe_button.isEnabled()
    assert not workspace.start_button.isEnabled()


def test_workspace_preserves_start_for_monolithic_shot(qtbot, tmp_path: Path) -> None:
    package = tmp_path / "production_package.json"
    package.write_text("{}", encoding="utf-8")
    service = _TimedSpanWorkspaceService(
        package,
        TimedSpanAcceptanceState.NOT_APPLICABLE,
    )
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)

    workspace.refresh()
    workspace.table.selectRow(0)

    assert "NOT_APPLICABLE" in workspace.timed_span_state.text()
    assert workspace.start_button.isEnabled()
