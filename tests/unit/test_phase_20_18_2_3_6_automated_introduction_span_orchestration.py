from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from vscs.application.production_execution import (
    AutomatedBoundaryValidationState,
    CanonicalInjectionAsset,
    GovernedInternalRenderSpanCompiler,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedIntroductionKeyframeStore,
    InjectionRegionAuthority,
    IntroductionBoundaryProviderCapabilities,
    IntroductionBoundaryStrategy,
    IntroductionIdentityCandidateStatus,
    IntroductionInjectionCandidateStatus,
    IntroductionInjectionDecision,
    IntroductionInjectionResult,
    IntroductionInjectionSide,
    ProductionExecutionCandidate,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
    TimedCanonicalReferenceActivationCompiler,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    request_from_requirement,
)
from vscs.application.production_execution.automated_introduction_boundary import (
    AutomatedIntroductionBoundaryResult,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
from vscs.application.rendering import WorkflowCompatibilityValidator, WorkflowManifest
from vscs.application.timed_asset_presence import (
    AssetPresenceIntroduction,
    TimedAssetKind,
    TimedAssetPresence,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.production_execution.automated_introduction_boundary import (
    ComfyUIIntroductionBoundarySynthesizer,
)
from vscs.infrastructure.production_execution.automated_span_orchestration import (
    AutomatedTimedSpanOrchestrationService,
    GovernedInternalBoundaryFrameExtractor,
)
from vscs.infrastructure.production_execution.automated_span_provider import (
    LTX25AutomatedSpanProvider,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    SpanMediaObservation,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_service import (
    TimedSpanFunctionalAcceptanceService,
)
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png(path: Path, value: tuple[int, int, int] = (10, 20, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1280, 720), value).save(path)
    return path


def _timed(
    introduction: AssetPresenceIntroduction = AssetPresenceIntroduction.ENTER,
) -> TimedAssetPresencePlan:
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
                asset_id="CAP-LOC-021",
                asset_kind=TimedAssetKind.LOCATION,
                from_frame=0,
                through_frame=143,
            ),
            TimedAssetPresence(
                asset_id="CAP-CHR-005",
                asset_kind=TimedAssetKind.CHARACTER,
                from_frame=96,
                through_frame=143,
                introduction=introduction,
                canonical_reference_ids=("REF-ROS",),
            ),
        ),
    )


def _reference_plan(project: Path) -> dict[str, object]:
    james = _png(project / "refs" / "james.png", (40, 50, 60))
    sandra = _png(project / "refs" / "sandra.png", (70, 80, 90))
    ros = _png(project / "refs" / "ros.png", (100, 110, 120))
    composition = _png(project / "refs" / "composition.png", (20, 20, 20))
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
        },
        "references": [
            {
                "reference_id": "REF-JAMES",
                "role": "secondary_identity",
                "asset_id": "CAP-CHR-001",
                "label": "Commander James Spence",
                "source_path": str(james),
                "file_checksum": _sha(james),
            },
            {
                "reference_id": "REF-SANDRA",
                "role": "primary_identity",
                "asset_id": "CAP-CHR-003",
                "label": "Captain Sandra Crawford",
                "source_path": str(sandra),
                "file_checksum": _sha(sandra),
            },
            {
                "reference_id": "REF-ROS",
                "role": "secondary_identity",
                "asset_id": "CAP-CHR-005",
                "label": "Major Ros Rohsgard",
                "source_path": str(ros),
                "file_checksum": _sha(ros),
            },
            {
                "reference_id": "REF-COMPOSITION",
                "role": "scene_composition_anchor",
                "asset_id": None,
                "label": "Iron Horizon bridge composition",
                "source_path": str(composition),
                "file_checksum": _sha(composition),
                "contains_environments": ["CAP-LOC-021"],
            },
        ],
        "diagnostics": [],
    }


def _authority(
    project: Path,
    *,
    introduction: AssetPresenceIntroduction = AssetPresenceIntroduction.ENTER,
) -> tuple[
    TimedAssetPresencePlan,
    Any,
    Any,
    Any,
    dict[str, object],
]:
    timed = _timed(introduction)
    spans = GovernedInternalRenderSpanCompiler().compile(timed)
    reference_plan = _reference_plan(project)
    activation = TimedCanonicalReferenceActivationCompiler().compile(
        timed,
        spans,
        reference_plan,
    )
    requirements = GovernedIntroductionKeyframeRequirementCompiler().compile(
        spans,
        activation,
    )
    return timed, spans, activation, requirements, reference_plan


def _candidate_package(
    project: Path,
    *,
    introduction: AssetPresenceIntroduction = AssetPresenceIntroduction.APPEAR,
) -> tuple[Path, dict[str, object]]:
    timed, spans, activation, requirements, reference_plan = _authority(
        project,
        introduction=introduction,
    )
    opening = _png(project / "keyframes" / "opening.png", (5, 5, 5))
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
        "keyframe_strength": 0.9,
        "seed": 42,
        "composition_plan": {"reference_plan": reference_plan},
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
            "approved_at": "2026-09-25T18:00:00+02:00",
            "acceptance_criteria": ["composition_approved"],
            "status": "approved",
            "source_kind": "governed_closing_boundary",
        },
        "reference_plan": reference_plan,
        "provider_video_rebaseline": {"active_candidate": "C"},
        "provider_execution_plan": {
            "provider": "ltx-2.5",
            "mode": "governed_multi_span_automated_orchestration",
            "governed_frame_count": 144,
            "provider_frame_count": 145,
            "automatic_provider_submission": True,
            "monolithic_submission_permitted": False,
        },
        "_vscs_manifest": {
            "task_id": "PT-VIDEO-SHT-002",
            "production_id": "XORIX",
            "episode_id": "EP-001",
            "scene_id": "SCN-001",
            "shot_id": timed.shot_id,
            "authority_id": "UPD-SHT-002",
            "package_fingerprint": "parent-package-fingerprint",
        },
    }
    path = project / "production" / "compiled" / "production_package.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    return path, raw


def test_strategy_ladder_prefers_direct_then_synthesis_then_manual() -> None:
    direct = IntroductionBoundaryProviderCapabilities(
        provider_id="future-provider",
        direct_timed_reference_asset_kinds=frozenset({"character", "ship"}),
        supports_reference_aware_image_synthesis=True,
    )
    synth = IntroductionBoundaryProviderCapabilities(
        provider_id="ltx-2.5",
        supports_reference_aware_image_synthesis=True,
    )
    manual = IntroductionBoundaryProviderCapabilities(provider_id="legacy")

    assert (
        direct.strategy_for(("character",))
        is IntroductionBoundaryStrategy.DIRECT_PROVIDER_REFERENCE
    )
    assert synth.strategy_for(("character",)) is IntroductionBoundaryStrategy.SYNTHESIZED_KEYFRAME
    assert manual.strategy_for(("character",)) is IntroductionBoundaryStrategy.MANUAL_FALLBACK


def test_request_compilation_pins_source_and_introduced_reference(tmp_path: Path) -> None:
    timed, _spans, _activation, requirements, reference_plan = _authority(tmp_path)
    requirement = requirements.requirements[0]
    source = _png(tmp_path / "boundaries" / "frame-95.png", (1, 2, 3))

    request = request_from_requirement(
        requirement,
        source_boundary_image_path=source,
        source_boundary_image_sha256=_sha(source),
        reference_plan=reference_plan,
        timed_asset_presence=timed.to_dict(),
        width=1280,
        height=720,
        source_package_fingerprint="package-fingerprint",
        seed=138,
    )

    assert request.source_global_frame_index == 95
    assert request.target_global_frame_index == 96
    assert request.introduced_asset_ids == ("CAP-CHR-005",)
    assert request.introduced_asset_kinds == ("character",)
    assert request.introduced_reference_ids == ("REF-ROS",)
    assert len(request.introduced_reference_sha256) == 1
    assert "Major Ros Rohsgard" in request.positive_prompt
    assert "This is an ENTER transition" in request.positive_prompt
    assert "immutable identity authority" in request.positive_prompt
    assert "generic substitute" in request.positive_prompt
    assert "first visible phase" in request.positive_prompt
    assert "exactly one new human figure" in request.positive_prompt
    assert "extreme left or right edge" in request.positive_prompt
    assert "outside the central half" in request.positive_prompt
    assert "only a partial body is visible" in request.positive_prompt
    assert "no additional background crew" in request.positive_prompt
    assert "oversized entrant" in request.negative_prompt
    assert "second entrant" in request.negative_prompt
    assert "fully arrived" in request.positive_prompt
    assert "Do not replace, duplicate" in request.positive_prompt
    assert "teleportation" in request.negative_prompt
    assert "wrong face" in request.negative_prompt


def test_automated_structural_keyframe_can_condition_provider_before_final_visual_qc(
    tmp_path: Path,
) -> None:
    _timed_plan, _spans, _activation, requirements, _reference_plan_value = _authority(tmp_path)
    requirement = requirements.requirements[0]
    source = _png(tmp_path / "boundary.png", (1, 1, 1))
    intro = _png(tmp_path / "intro.png", (2, 2, 2))
    store = GovernedIntroductionKeyframeStore(tmp_path)
    record = store.create_record(
        requirement,
        image_path=intro.relative_to(tmp_path).as_posix(),
        image_sha256=_sha(intro),
        source_boundary_image_path=source.relative_to(tmp_path).as_posix(),
        source_boundary_image_sha256=_sha(source),
        approved_by="VSCS Automation — test provider",
        approved_at="2026-09-25T18:30:00+02:00",
        acceptance_criteria=(
            "source_boundary_continuity_preserved",
            "target_span_first_emitted_frame_correct",
        ),
        approval_mode="automated_structural",
        automated_validation_findings=(
            "source_boundary_checksum_verified",
            "introduced_reference_checksums_verified",
            "output_geometry_verified",
            "final_visual_qc_deferred_to_assembled_shot",
        ),
    )

    saved = store.save(record, requirement)
    current = store.require_approved(requirement)

    assert saved.approval_mode == "automated_structural"
    assert current.keyframe_id == saved.keyframe_id
    assert "introduced_assets_present" not in current.acceptance_criteria


def test_automated_keyframe_identity_detects_validation_mode_tampering(
    tmp_path: Path,
) -> None:
    _timed_plan, _spans, _activation, requirements, _reference_plan_value = _authority(tmp_path)
    requirement = requirements.requirements[0]
    source = _png(tmp_path / "boundary-tamper.png", (3, 3, 3))
    intro = _png(tmp_path / "intro-tamper.png", (4, 4, 4))
    store = GovernedIntroductionKeyframeStore(tmp_path)
    record = store.create_record(
        requirement,
        image_path=intro.relative_to(tmp_path).as_posix(),
        image_sha256=_sha(intro),
        source_boundary_image_path=source.relative_to(tmp_path).as_posix(),
        source_boundary_image_sha256=_sha(source),
        approved_by="VSCS Automation — test provider",
        approved_at="2026-09-25T18:35:00+02:00",
        acceptance_criteria=("source_boundary_continuity_preserved",),
        approval_mode="automated_structural",
        automated_validation_findings=(
            "source_boundary_checksum_verified",
            "introduced_reference_checksums_verified",
            "output_geometry_verified",
        ),
    )
    store.save(record, requirement)

    store_path = tmp_path / ".vscs" / "governed_introduction_keyframes.json"
    raw = json.loads(store_path.read_text(encoding="utf-8"))
    raw["introduction_keyframes"][0]["approval_mode"] = "human"
    store_path.write_text(json.dumps(raw), encoding="utf-8")

    from vscs.application.production_execution import GovernedIntroductionKeyframeError

    with pytest.raises(GovernedIntroductionKeyframeError, match="identity"):
        store.require_approved(requirement)


class _SynthesisClient:
    def __init__(self) -> None:
        self.prompt: dict[str, Any] | None = None

    def healthcheck(self) -> None:
        return None

    def validate_nodes(self, prompt: dict[str, Any]) -> None:
        assert prompt["1"]["class_type"] == "VSCSIntroductionBoundaryPackageLoaderV1"

    def submit(self, prompt: dict[str, Any]) -> str:
        self.prompt = prompt
        request_file = Path(prompt["1"]["inputs"]["request_file"])
        payload = json.loads(request_file.read_text(encoding="utf-8"))
        output = Path(payload["output_directory"]) / payload["output_filename"]
        source = Path(payload["source_boundary_image_path"])
        with Image.open(source) as image:
            image.convert("RGB").save(output)
        return "prompt-auto-intro"

    def wait(self, prompt_id: str, timeout_seconds: float = 3600.0) -> dict[str, Any]:
        assert prompt_id == "prompt-auto-intro"
        return {"status": {"completed": True}}


def test_qwen_synthesizer_uses_boundary_plus_canonical_reference_without_manual_images(
    tmp_path: Path,
) -> None:
    timed, _spans, _activation, requirements, reference_plan = _authority(tmp_path)
    requirement = requirements.requirements[0]
    source = _png(tmp_path / "boundary" / "frame-95.png", (11, 12, 13))
    request = request_from_requirement(
        requirement,
        source_boundary_image_path=source,
        source_boundary_image_sha256=_sha(source),
        reference_plan=reference_plan,
        timed_asset_presence=timed.to_dict(),
        width=1280,
        height=720,
        source_package_fingerprint="package-fingerprint",
        seed=96,
    )
    client = _SynthesisClient()
    synth = ComfyUIIntroductionBoundarySynthesizer(
        tmp_path,
        client=client,  # type: ignore[arg-type]
    )

    result = synth.synthesize(request)

    assert result.validation_state is AutomatedBoundaryValidationState.PASSED
    assert Path(result.image_path).is_file()
    assert result.source_boundary_image_sha256 == _sha(source)
    assert result.introduced_reference_ids == ("REF-ROS",)
    assert client.prompt is not None
    request_file = Path(client.prompt["1"]["inputs"]["request_file"])
    runtime_request = json.loads(request_file.read_text(encoding="utf-8"))
    assert runtime_request["introduced_reference_ids"] == ["REF-ROS"]
    assert runtime_request["source_boundary_image_path"] == str(source.resolve())


def test_qwen_synthesis_attempts_use_immutable_request_scoped_paths(
    tmp_path: Path,
) -> None:
    timed, _spans, _activation, requirements, reference_plan = _authority(tmp_path)
    requirement = requirements.requirements[0]
    source = _png(tmp_path / "boundary" / "frame-95.png", (11, 12, 13))
    request = request_from_requirement(
        requirement,
        source_boundary_image_path=source,
        source_boundary_image_sha256=_sha(source),
        reference_plan=reference_plan,
        timed_asset_presence=timed.to_dict(),
        width=1280,
        height=720,
        source_package_fingerprint="package-fingerprint",
        seed=96,
    )
    synth = ComfyUIIntroductionBoundarySynthesizer(
        tmp_path,
        client=_SynthesisClient(),  # type: ignore[arg-type]
    )

    first = synth.synthesize(request)
    first_path = Path(first.image_path)
    first_sha = _sha(first_path)

    retry_request = replace(request, seed=request.seed + 1)
    second = synth.synthesize(retry_request)
    second_path = Path(second.image_path)

    assert retry_request.request_id != request.request_id
    assert second_path != first_path
    assert first_path.is_file()
    assert second_path.is_file()
    assert _sha(first_path) == first_sha
    assert request.request_id in first_path.parts
    assert retry_request.request_id in second_path.parts


def test_incremental_builder_emits_span_one_before_intro_keyframe_exists(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(tmp_path)

    package_set = LTX25TimedSpanAcceptancePackageBuilder(tmp_path).build(
        package_path,
        through_sequence=1,
    )
    first = json.loads(package_set.package_paths[0].read_text(encoding="utf-8"))

    assert len(package_set.package_paths) == 1
    assert first["timed_span_execution"]["global_start_frame"] == 0
    assert first["timed_span_execution"]["global_through_frame"] == 95
    assert first["provider_execution_plan"]["provider_frame_count"] == 97


class _FakeSpanProvider:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0
        self.free_calls = 0

    def render(self, package_path: Path) -> Path:
        self.calls += 1
        package = json.loads(package_path.read_text(encoding="utf-8"))
        sequence = package["timed_span_execution"]["sequence_number"]
        path = self.root / f"span-{sequence:03d}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"span-{sequence}".encode())
        return path

    def free_models_and_memory(self) -> None:
        self.free_calls += 1


class _FakeExtractor(GovernedInternalBoundaryFrameExtractor):
    def extract(
        self,
        span_path: Path,
        *,
        local_frame_index: int,
        shot_id: str,
        requirement_id: str,
        global_frame_index: int,
    ) -> Path:
        assert span_path.name == "span-001.mp4"
        assert local_frame_index == 95
        assert global_frame_index == 95
        return _png(
            self.project_directory
            / ".vscs"
            / "automated_introduction_boundaries"
            / shot_id
            / requirement_id
            / "source-frame-000095.png",
            (9, 9, 9),
        )


class _FakeSynthesizer:
    def preflight(self) -> None:
        return None

    def synthesize(self, request: Any) -> AutomatedIntroductionBoundaryResult:
        target = (
            Path(request.source_boundary_image_path).parent
            / f"frame-{request.target_global_frame_index:06d}.png"
        )
        _png(target, (8, 8, 8))
        return AutomatedIntroductionBoundaryResult(
            request_id=request.request_id,
            requirement_id=request.requirement_id,
            image_path=str(target),
            image_sha256=_sha(target),
            provider_name="Fake Qwen",
            model="Qwen Image Edit 2511",
            source_boundary_image_path=request.source_boundary_image_path,
            source_boundary_image_sha256=request.source_boundary_image_sha256,
            introduced_reference_ids=request.introduced_reference_ids,
            width=request.width,
            height=request.height,
            generated_at="2026-09-25T18:45:00+02:00",
            validation_state=AutomatedBoundaryValidationState.PASSED,
            validation_findings=(
                "source_boundary_checksum_verified",
                "introduced_reference_checksums_verified",
                "output_geometry_verified",
                "final_visual_qc_deferred_to_assembled_shot",
            ),
        )


class _FakeAssemblyRuntime(GovernedSpanAssemblyRuntime):
    def _observe(self, path: Path) -> SpanMediaObservation:
        candidate = Path(path).resolve(strict=False)
        if "assembled" in candidate.name:
            count = 144
        elif candidate.name == "span-001.mp4":
            count = 96
        elif candidate.name == "span-002.mp4":
            count = 48
        else:
            raise AssertionError(candidate)
        return SpanMediaObservation(candidate, count, 1280, 720, 24)

    def _verify_boundary_evidence(
        self,
        compiled_package: dict[str, Any],
        spans: Any,
        observations: tuple[SpanMediaObservation, ...],
    ) -> None:
        del compiled_package, spans, observations

    def _assemble(self, paths: tuple[Path, ...], destination: Path) -> None:
        assert len(paths) == 2
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"assembled")


def test_orchestration_renders_extracts_synthesizes_continues_and_assembles(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(tmp_path)
    provider = _FakeSpanProvider(tmp_path / "provider")
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=_FakeSynthesizer(),
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    result = service.run(package_path)

    assert provider.calls == 2
    assert len(result.span_paths) == 2
    assert len(result.synthesized_keyframe_ids) == 1
    assert result.final_path is not None
    assert result.final_path.is_file()
    assert result.acceptance_status.state is TimedSpanAcceptanceState.QC_REQUIRED
    store = GovernedIntroductionKeyframeStore(tmp_path)
    _timed_plan, _spans, _activation, requirements, _plan = _authority(
        tmp_path,
        introduction=AssetPresenceIntroduction.APPEAR,
    )
    keyframe = store.require_approved(requirements.requirements[0])
    assert keyframe.approval_mode == "automated_structural"
    assert keyframe.target_global_frame_index == 96
    span_two_package = json.loads(
        (
            tmp_path
            / ".vscs"
            / "timed_span_acceptance"
            / "packages"
            / "PT-VIDEO-SHT-002"
            / "production"
            / "span-002.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        "Continue from this exact approved Introduction Keyframe"
        in span_two_package["motion_prompt"]
    )
    assert "Do not add any unapproved subject" in span_two_package["motion_prompt"]


def test_character_enter_pauses_for_identity_approval_before_target_span(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )
    provider = _FakeSpanProvider(tmp_path / "provider")
    synthesizer = _CountingSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=synthesizer,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    result = service.run(package_path)

    assert provider.calls == 1
    assert synthesizer.calls == 1
    assert len(result.span_paths) == 1
    assert result.final_path is None
    assert result.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    candidate = TimedSpanFunctionalAcceptanceService(tmp_path).identity_candidate(package_path)
    assert candidate is not None
    assert candidate.pending
    assert candidate.introduced_asset_ids == ("CAP-CHR-005",)
    assert candidate.introduced_reference_ids == ("REF-ROS",)
    assert candidate.target_global_frame_index == 96
    assert candidate.attempt_number == 1


def test_approved_character_identity_resumes_target_span_and_assembly(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )
    provider = _FakeSpanProvider(tmp_path / "provider")
    synthesizer = _CountingSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=synthesizer,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )
    first = service.run(package_path)
    candidate = TimedSpanFunctionalAcceptanceService(tmp_path).identity_candidate(package_path)
    assert candidate is not None

    status = TimedSpanFunctionalAcceptanceService(tmp_path).approve_identity_candidate(
        package_path,
        requirement_id=candidate.requirement_id,
        approved_by="Neill Payne",
        notes="Canonical Ros identity confirmed.",
    )
    assert status.state is TimedSpanAcceptanceState.OUTPUTS_REQUIRED
    keyframe = GovernedIntroductionKeyframeStore(tmp_path).require_approved(
        _authority(
            tmp_path,
            introduction=AssetPresenceIntroduction.ENTER,
        )[3].requirements[0]
    )
    assert keyframe.approval_mode == "human"
    assert keyframe.image_sha256 == candidate.image_sha256

    second = service.run(package_path)

    assert first.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert provider.calls == 2
    assert synthesizer.calls == 1
    assert second.final_path is not None
    assert second.final_path.is_file()
    assert second.acceptance_status.state is TimedSpanAcceptanceState.QC_REQUIRED
    span_two_package = json.loads(
        (
            tmp_path
            / ".vscs"
            / "timed_span_acceptance"
            / "packages"
            / "PT-VIDEO-SHT-002"
            / "production"
            / "span-002.json"
        ).read_text(encoding="utf-8")
    )
    assert "that exact same person" in span_two_package["motion_prompt"]
    assert "Do not create, replace, duplicate" in span_two_package["motion_prompt"]


def test_rejected_character_identity_regenerates_without_rendering_target_span(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )
    provider = _FakeSpanProvider(tmp_path / "provider")
    synthesizer = _CountingSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=synthesizer,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )
    first = service.run(package_path)
    acceptance = TimedSpanFunctionalAcceptanceService(tmp_path)
    candidate_one = acceptance.identity_candidate(package_path)
    assert candidate_one is not None
    acceptance.reject_identity_candidate(
        package_path,
        requirement_id=candidate_one.requirement_id,
        rejected_by="Neill Payne",
        notes="Identity does not match canonical Ros.",
    )

    second = service.run(package_path)
    candidate_two = acceptance.identity_candidate(package_path)

    assert first.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert second.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert provider.calls == 1
    assert synthesizer.calls == 2
    assert candidate_two is not None
    assert candidate_two.pending
    assert candidate_two.result_id != candidate_one.result_id
    assert candidate_two.attempt_number == 2


def test_orchestration_resume_reuses_checksum_pinned_span_outputs(tmp_path: Path) -> None:
    package_path, _raw = _candidate_package(tmp_path)
    provider = _FakeSpanProvider(tmp_path / "provider")
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=_FakeSynthesizer(),
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    first = service.run(package_path)
    second = service.run(package_path)

    assert first.acceptance_status.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert second.acceptance_status.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert provider.calls == 2
    resume = json.loads(
        (tmp_path / ".vscs" / "automated_span_orchestration_state.json").read_text(encoding="utf-8")
    )
    spans = resume["tasks"]["PT-VIDEO-SHT-002"]["spans"]
    assert set(spans) == {"1", "2"}
    assert spans["1"]["output_sha256"] == _sha(Path(spans["1"]["output_path"]))
    assert spans["2"]["output_sha256"] == _sha(Path(spans["2"]["output_path"]))


def test_orchestration_resume_rerenders_only_tampered_span_output(tmp_path: Path) -> None:
    package_path, _raw = _candidate_package(tmp_path)
    provider = _FakeSpanProvider(tmp_path / "provider")
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=_FakeSynthesizer(),
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )
    first = service.run(package_path)
    first.span_paths[0].write_bytes(b"tampered")

    service.run(package_path)

    assert provider.calls == 3
    assert first.span_paths[0].read_bytes() == b"span-1"


class _ChangingExtractor(GovernedInternalBoundaryFrameExtractor):
    def __init__(self, project_directory: Path) -> None:
        super().__init__(project_directory)
        self.calls = 0

    def extract(
        self,
        span_path: Path,
        *,
        local_frame_index: int,
        shot_id: str,
        requirement_id: str,
        global_frame_index: int,
    ) -> Path:
        del span_path, local_frame_index
        self.calls += 1
        value = 9 if self.calls == 1 else 19
        return _png(
            self.project_directory
            / ".vscs"
            / "automated_introduction_boundaries"
            / shot_id
            / requirement_id
            / f"source-frame-{global_frame_index:06d}.png",
            (value, value, value),
        )


class _CountingSynthesizer(_FakeSynthesizer):
    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, request: Any) -> AutomatedIntroductionBoundaryResult:
        self.calls += 1
        return super().synthesize(request)


def test_orchestration_regenerates_keyframe_when_current_boundary_checksum_changes(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(tmp_path)
    provider = _FakeSpanProvider(tmp_path / "provider")
    synthesizer = _CountingSynthesizer()
    extractor = _ChangingExtractor(tmp_path)
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=synthesizer,
        extractor=extractor,
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    service.run(package_path)
    service.run(package_path)

    assert provider.calls == 3
    assert synthesizer.calls == 2


def test_orchestration_rejects_keyframe_from_stale_synthesis_request(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(tmp_path)
    provider = _FakeSpanProvider(tmp_path / "provider")
    synthesizer = _CountingSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=synthesizer,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )
    service.run(package_path)
    assert synthesizer.calls == 1

    boundary_store = service.boundaries
    root = json.loads(boundary_store.path.read_text(encoding="utf-8"))
    root["results"][-1]["request_id"] = "AIBR-STALE-SEMANTICS"
    root["results"][-1].pop("result_id", None)
    boundary_store.path.write_text(json.dumps(root, indent=2), encoding="utf-8")

    service.run(package_path)

    assert synthesizer.calls == 2
    assert provider.calls == 2


def test_orchestration_resume_discards_spans_when_package_fingerprint_changes(
    tmp_path: Path,
) -> None:
    package_path, raw = _candidate_package(tmp_path)
    provider = _FakeSpanProvider(tmp_path / "provider")
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=_FakeSynthesizer(),
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )
    service.run(package_path)

    manifest = dict(raw["_vscs_manifest"])
    manifest["package_fingerprint"] = "replacement-package-fingerprint"
    raw["_vscs_manifest"] = manifest
    package_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")

    service.run(package_path)

    assert provider.calls == 4


class _FacadeBackend:
    def __init__(self) -> None:
        self.profile: str | None = None

    def run_automated_timed_span_orchestration_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> TimedSpanAcceptanceStatus:
        assert task_id == "PT-AUTO"
        self.profile = profile
        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-001-SHT-002",
            state=TimedSpanAcceptanceState.QC_REQUIRED,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=1,
            qc_passed_count=0,
            assembly_present=True,
            message="Automated provider work complete; visual QC required.",
            requirement_ids=("GIKR-1",),
            pending_qc_requirement_ids=("GIKR-1",),
            final_frame_count=144,
        )


def test_ui_service_delegates_automated_orchestration_with_normalized_profile() -> None:
    backend = _FacadeBackend()
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    status = service.run_automated_timed_span_orchestration(
        "PT-AUTO",
        profile="Production",
    )

    assert status.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert status.final_frame_count == 144
    assert backend.profile == "production"


def test_introduction_boundary_workflow_and_deployment_assets_are_versioned() -> None:
    repository = Path(__file__).resolve().parents[2]
    workflow = json.loads(
        (
            repository
            / "src"
            / "vscs"
            / "workflows"
            / "image"
            / "VSCS_Qwen_Introduction_Boundary_Workflow_API_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert workflow["1"]["class_type"] == "VSCSIntroductionBoundaryPackageLoaderV1"
    assert workflow["9"]["inputs"]["image1"] == ["1", 0]
    assert workflow["9"]["inputs"]["image2"] == ["1", 1]
    assert workflow["20"]["inputs"]["latent_image"] == ["13", 0]
    deploy = (repository / "scripts" / "deploy_comfyui_introduction_boundary_v1.ps1").read_text(
        encoding="utf-8"
    )
    assert "VSCSIntroductionBoundaryPackageLoaderV1" in deploy


class _UiService:
    def __init__(self) -> None:
        self.candidate = ProductionExecutionCandidate(
            production_id="XORIX",
            task_id="PT-AUTO-SPAN",
            task_type=ProductionTaskType.VIDEO_GENERATION,
            task_state=ProductionTaskState.READY,
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="EP-001-SCN-001-SHT-002",
            resource_id="GPU-01",
            queue_entry_id="PQE-AUTO-SPAN",
            label="Video Generation — SHT-002",
        )

    def candidates(self) -> tuple[Any, ...]:
        return (self.candidate,)

    def package_status(self, task_id: str, *, profile: str = "production") -> Any:
        return ProductionPackageStatus(
            task_id=task_id,
            state=ProductionPackageCompilationState.COMPILED,
            profile=profile,
            path=Path("production_package.json"),
            authority_fingerprint="authority",
            package_fingerprint="package",
            source_package_id="PP-SHT-002",
            message="Compiled",
        )

    def has_execution(self, task_id: str, *, profile: str | None = None) -> bool:
        return False

    def timed_span_acceptance_status(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> TimedSpanAcceptanceStatus:
        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-001-SHT-002",
            state=TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=0,
            qc_passed_count=0,
            assembly_present=False,
            message="Automated introduction boundary required.",
            requirement_ids=("GIKR-1",),
            pending_keyframe_requirement_ids=("GIKR-1",),
            pending_qc_requirement_ids=("GIKR-1",),
        )

    def retry_override_status(self, task_id: str, *, profile: str | None = None) -> Any:
        raise RuntimeError("not needed")

    def shot_boundary_status(self, task_id: str, *, profile: str | None = None) -> Any:
        raise RuntimeError("not needed")


def test_workspace_prefers_automated_orchestration_and_keeps_manual_recovery(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    service = _UiService()
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)
    workspace.refresh()
    workspace.table.selectRow(0)

    assert not workspace.run_automated_spans_button.isEnabled()
    assert workspace.run_automated_spans_button.text() == "Run Automated Span Orchestration"
    assert "Manual Recovery" in workspace.approve_introduction_keyframe_button.text()
    assert workspace.approve_introduction_keyframe_button.isEnabled()
    assert not workspace.start_button.isEnabled()


class _IdentityGateUiService(_UiService):
    def __init__(self, root: Path) -> None:
        super().__init__()
        candidate_path = _png(root / "identity-candidate.png", (120, 90, 70))
        reference_path = _png(root / "ros-reference.png", (100, 110, 120))
        self.identity_candidate = IntroductionIdentityCandidateStatus(
            requirement_id="GIKR-1",
            result_id="AIBS-1",
            image_path=str(candidate_path),
            image_sha256=_sha(candidate_path),
            introduced_asset_ids=("CAP-CHR-005",),
            introduced_reference_ids=("REF-ROS",),
            introduced_reference_paths=(str(reference_path),),
            introduced_reference_sha256=(_sha(reference_path),),
            target_global_frame_index=96,
            attempt_number=1,
        )

    def introduction_identity_candidate(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> IntroductionIdentityCandidateStatus:
        assert task_id == "PT-AUTO-SPAN"
        assert profile == "production"
        return self.identity_candidate


def test_workspace_pauses_automation_for_pending_identity_candidate(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    service = _IdentityGateUiService(tmp_path)
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)
    workspace.refresh()
    workspace.table.selectRow(0)

    assert not workspace.run_automated_spans_button.isEnabled()
    assert workspace.view_identity_candidate_button.isEnabled()
    assert workspace.approve_identity_candidate_button.isEnabled()
    assert workspace.reject_identity_candidate_button.isEnabled()
    assert not workspace.approve_introduction_keyframe_button.isEnabled()
    assert "REVIEW_REQUIRED" in workspace.identity_candidate_state.text()
    assert "CAP-CHR-005" in workspace.identity_candidate_state.text()
    assert "REF-ROS" in workspace.identity_candidate_state.text()
    assert _sha(Path(service.identity_candidate.introduced_reference_paths[0])) in (
        workspace.identity_candidate_state.text()
    )


class _InjectionGateUiService(_UiService):
    def __init__(self, root: Path) -> None:
        super().__init__()
        candidate_path = _png(root / "injected-boundary.png", (130, 90, 60))
        source_path = _png(root / "source-boundary.png", (30, 40, 50))
        reference_path = _png(root / "ros-reference-injection.png", (100, 110, 120))
        asset = CanonicalInjectionAsset(
            asset_id="CAP-CHR-005",
            asset_kind="character",
            reference_ids=("REF-ROS",),
            reference_paths=(str(reference_path),),
            reference_sha256=(_sha(reference_path),),
        )
        region = InjectionRegionAuthority(
            side=IntroductionInjectionSide.RIGHT,
            left=0.82,
            top=0.08,
            right=1.0,
            bottom=0.96,
            partial_visibility_required=True,
            max_subject_scale_ratio=0.55,
        )
        self.injection_candidate = IntroductionInjectionCandidateStatus(
            requirement_id="GIKR-1",
            request_id="IIAR-ROS-1",
            result_id="IIAS-ROS-1",
            source_boundary_image_path=str(source_path),
            source_boundary_image_sha256=_sha(source_path),
            image_path=str(candidate_path),
            image_sha256=_sha(candidate_path),
            canonical_asset=asset,
            injection_region=region,
            target_global_frame_index=96,
            attempt_number=1,
        )
        self.approved: tuple[str, str, str] | None = None
        self.rejected: tuple[str, str, str] | None = None

    def introduction_injection_candidate(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> IntroductionInjectionCandidateStatus:
        assert task_id == "PT-AUTO-SPAN"
        assert profile == "production"
        return self.injection_candidate

    def introduction_identity_candidate(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> IntroductionIdentityCandidateStatus | None:
        return None

    def approve_introduction_injection(
        self,
        task_id: str,
        *,
        requirement_id: str,
        approved_by: str,
        notes: str = "",
        profile: str | None = None,
    ) -> TimedSpanAcceptanceStatus:
        assert task_id == "PT-AUTO-SPAN"
        assert profile == "production"
        self.approved = (requirement_id, approved_by, notes)
        return TimedSpanAcceptanceStatus(
            shot_id="EP-001-SCN-001-SHT-002",
            state=TimedSpanAcceptanceState.OUTPUTS_REQUIRED,
            span_count=2,
            boundary_count=1,
            requirement_count=1,
            approved_keyframe_count=1,
            qc_passed_count=0,
            assembly_present=False,
            message="Injection approved; target span output required.",
            requirement_ids=("GIKR-1",),
            pending_qc_requirement_ids=("GIKR-1",),
        )

    def reject_introduction_injection(
        self,
        task_id: str,
        *,
        requirement_id: str,
        rejected_by: str,
        notes: str = "",
        profile: str | None = None,
    ) -> TimedSpanAcceptanceStatus:
        assert task_id == "PT-AUTO-SPAN"
        assert profile == "production"
        self.rejected = (requirement_id, rejected_by, notes)
        return self.timed_span_acceptance_status(task_id, profile=profile)


class _LegacyCandidateOnInjectionCapableUiService(_IdentityGateUiService):
    def introduction_injection_review_supported(self) -> bool:
        return True

    def introduction_injection_candidate(
        self,
        task_id: str,
        *,
        profile: str | None = None,
    ) -> IntroductionInjectionCandidateStatus | None:
        assert task_id == "PT-AUTO-SPAN"
        assert profile == "production"
        return None


def test_workspace_ignores_stale_legacy_identity_candidate_when_injection_is_supported(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    service = _LegacyCandidateOnInjectionCapableUiService(tmp_path)
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)
    workspace.refresh()
    workspace.table.selectRow(0)

    assert workspace.injection_candidate_state.text() == "Injected Boundary QC: no candidate"
    assert "superseded by identity-locked injection authority" in (
        workspace.identity_candidate_state.text()
    )
    assert not workspace.run_automated_spans_button.isEnabled()
    assert not workspace.view_identity_candidate_button.isEnabled()
    assert not workspace.approve_identity_candidate_button.isEnabled()
    assert not workspace.reject_identity_candidate_button.isEnabled()
    assert not workspace.approve_introduction_keyframe_button.isEnabled()


def test_workspace_exposes_identity_locked_injection_review_gate(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    service = _InjectionGateUiService(tmp_path)
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)
    workspace.refresh()
    workspace.table.selectRow(0)

    candidate = service.injection_candidate
    text = workspace.injection_candidate_state.text()
    assert "REVIEW_REQUIRED" in text
    assert candidate.canonical_asset.asset_id in text
    assert candidate.canonical_asset.authority_id in text
    assert candidate.canonical_asset.reference_sha256[0] in text
    assert candidate.source_boundary_image_sha256 in text
    assert candidate.image_sha256 in text
    assert candidate.request_id in text
    assert candidate.injection_region.region_id in text
    assert "RIGHT" in text
    assert "Attempt 1" in text
    assert workspace.view_injection_candidate_button.isEnabled()
    assert workspace.approve_injection_candidate_button.isEnabled()
    assert workspace.reject_injection_candidate_button.isEnabled()
    assert not workspace.run_automated_spans_button.isEnabled()
    assert not workspace.approve_introduction_keyframe_button.isEnabled()
    assert not workspace.view_identity_candidate_button.isEnabled()
    assert workspace.view_injection_candidate_button.text() == "View Injected Candidate"
    assert workspace.approve_injection_candidate_button.text() == "Approve Injection"
    assert workspace.reject_injection_candidate_button.text() == "Reject & Regenerate"


class _InjectionFacadeBackend(_FacadeBackend):
    def __init__(self, candidate: IntroductionInjectionCandidateStatus) -> None:
        super().__init__()
        self.candidate = candidate
        self.approved: tuple[str, str, str, str] | None = None
        self.rejected: tuple[str, str, str, str] | None = None

    def introduction_injection_candidate_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> IntroductionInjectionCandidateStatus:
        assert task_id == "PT-AUTO"
        self.profile = profile
        return self.candidate

    def approve_introduction_injection_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        approved_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        self.approved = (profile, requirement_id, approved_by, notes)
        return self.run_automated_timed_span_orchestration_for_profile(
            task_id,
            profile=profile,
        )

    def reject_introduction_injection_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        rejected_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        self.rejected = (profile, requirement_id, rejected_by, notes)
        return self.run_automated_timed_span_orchestration_for_profile(
            task_id,
            profile=profile,
        )


def test_ui_service_delegates_injection_review_actions_with_normalized_profile(
    tmp_path: Path,
) -> None:
    source = _png(tmp_path / "source.png", (10, 20, 30))
    image = _png(tmp_path / "candidate.png", (40, 50, 60))
    reference = _png(tmp_path / "reference.png", (70, 80, 90))
    asset = CanonicalInjectionAsset(
        asset_id="CAP-CHR-005",
        asset_kind="character",
        reference_ids=("REF-ROS",),
        reference_paths=(str(reference),),
        reference_sha256=(_sha(reference),),
    )
    region = InjectionRegionAuthority(
        side=IntroductionInjectionSide.RIGHT,
        left=0.82,
        top=0.08,
        right=1.0,
        bottom=0.96,
        partial_visibility_required=True,
        max_subject_scale_ratio=0.55,
    )
    candidate = IntroductionInjectionCandidateStatus(
        requirement_id="GIKR-1",
        request_id="IIAR-1",
        result_id="IIAS-1",
        source_boundary_image_path=str(source),
        source_boundary_image_sha256=_sha(source),
        image_path=str(image),
        image_sha256=_sha(image),
        canonical_asset=asset,
        injection_region=region,
        target_global_frame_index=96,
        attempt_number=1,
    )
    backend = _InjectionFacadeBackend(candidate)
    service = ProductionExecutionUiService(backend)  # type: ignore[arg-type]

    observed = service.introduction_injection_candidate("PT-AUTO", profile="Production")
    approved = service.approve_introduction_injection(
        "PT-AUTO",
        requirement_id="GIKR-1",
        approved_by="Neill Payne",
        notes="Approved.",
        profile="Production",
    )
    rejected = service.reject_introduction_injection(
        "PT-AUTO",
        requirement_id="GIKR-1",
        rejected_by="Neill Payne",
        notes="Reject test.",
        profile="Production",
    )

    assert observed == candidate
    assert approved.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert rejected.state is TimedSpanAcceptanceState.QC_REQUIRED
    assert backend.approved == ("production", "GIKR-1", "Neill Payne", "Approved.")
    assert backend.rejected == ("production", "GIKR-1", "Neill Payne", "Reject test.")


def test_workspace_requires_readiness_revalidation_while_visual_qc_is_pending(
    qtbot: Any,
) -> None:
    service = _UiService()
    workspace = ProductionExecutionWorkspace(lambda: service)  # type: ignore[arg-type]
    qtbot.addWidget(workspace)
    workspace.refresh()
    workspace.table.selectRow(0)

    status = TimedSpanAcceptanceStatus(
        shot_id="EP-001-SCN-001-SHT-002",
        state=TimedSpanAcceptanceState.QC_REQUIRED,
        span_count=2,
        boundary_count=1,
        requirement_count=1,
        approved_keyframe_count=1,
        qc_passed_count=0,
        assembly_present=True,
        message="Visual QC remains pending.",
        requirement_ids=("GIKR-1",),
        pending_qc_requirement_ids=("GIKR-1",),
        final_frame_count=144,
    )
    workspace._timed_span_status = status
    workspace._render_timed_span_status(status)

    assert not workspace.run_automated_spans_button.isEnabled()
    assert workspace.record_span_qc_button.isEnabled()


def test_automated_span_request_declares_governed_keyframe_image_to_video(
    tmp_path: Path,
) -> None:
    output_directory = tmp_path / "comfy-output"
    output_directory.mkdir()
    package_path = tmp_path / "span-package.json"
    package = {
        "width": 1280,
        "height": 720,
        "fps": 24,
        "frame_count": 96,
        "seed": 42,
        "timed_span_execution": {
            "span_id": "SPAN-001",
            "sequence_number": 1,
        },
        "_vscs_manifest": {
            "task_id": "PT-VIDEO-SHT-002",
            "production_id": "XORIX",
            "episode_id": "EP-001",
            "scene_id": "SCN-001",
            "shot_id": "EP-001-SCN-001-SHT-002",
            "authority_id": "UPD-SHT-002",
        },
    }
    package_path.write_text(json.dumps(package), encoding="utf-8")

    provider = LTX25AutomatedSpanProvider(
        tmp_path,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=output_directory,
    )
    request = provider._request(package_path, package)

    assert request.metadata["generation_mode"] == "image_to_video"

    repository = Path(__file__).resolve().parents[2]
    manifest_raw = json.loads(
        (
            repository / "resources" / "workflows" / "manifests" / "ltx25_i2v_keyframe_v1.json"
        ).read_text(encoding="utf-8")
    )
    report = WorkflowCompatibilityValidator().validate(
        request,
        WorkflowManifest.from_dict(manifest_raw),
    )

    errors = tuple(
        diagnostic for diagnostic in report.diagnostics if diagnostic.severity.value == "error"
    )
    assert errors == ()


class _FakeInjectionSynthesizer:
    def __init__(self) -> None:
        self.calls = 0
        self.preflight_calls = 0

    def preflight(self) -> None:
        self.preflight_calls += 1

    def synthesize(
        self,
        request: Any,
        *,
        attempt_number: int,
    ) -> IntroductionInjectionResult:
        self.calls += 1
        target = (
            Path(request.source_boundary_image_path).parents[0]
            / request.request_id
            / f"frame-{request.target_global_frame_index:06d}.png"
        )
        _png(target, (120 + attempt_number, 20, 30))
        return IntroductionInjectionResult(
            request_id=request.request_id,
            requirement_id=request.requirement_id,
            image_path=str(target),
            image_sha256=_sha(target),
            canonical_asset_id=request.canonical_asset.authority_id,
            injection_region_id=request.injection_region.region_id,
            provider_name="Fake Identity-Locked Injection",
            model="Fake Qwen Edit",
            generated_at=f"2026-09-28T20:0{attempt_number}:00+02:00",
            attempt_number=attempt_number,
        )


def test_character_enter_uses_identity_locked_injection_and_pauses_for_review(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )
    provider = _FakeSpanProvider(tmp_path / "provider")
    legacy_synthesizer = _CountingSynthesizer()
    injection = _FakeInjectionSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=legacy_synthesizer,
        injection_synthesizer=injection,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    result = service.run(package_path)
    candidate = TimedSpanFunctionalAcceptanceService(tmp_path).injection_candidate(package_path)

    assert result.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert provider.calls == 1
    assert legacy_synthesizer.calls == 0
    assert injection.calls == 1
    assert candidate is not None
    assert candidate.pending
    assert candidate.canonical_asset.asset_id == "CAP-CHR-005"
    assert candidate.injection_region.side.value == "right"
    assert candidate.target_global_frame_index == 96
    assert candidate.attempt_number == 1


def test_approved_injection_promotes_human_keyframe_then_resumes_target_span(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )
    provider = _FakeSpanProvider(tmp_path / "provider")
    injection = _FakeInjectionSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=_CountingSynthesizer(),
        injection_synthesizer=injection,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    first = service.run(package_path)
    acceptance = TimedSpanFunctionalAcceptanceService(tmp_path)
    candidate = acceptance.injection_candidate(package_path)
    assert candidate is not None

    status = acceptance.approve_injection_candidate(
        package_path,
        requirement_id=candidate.requirement_id,
        approved_by="Neill Payne",
        notes="Canonical identity, edge placement, partial visibility, and scale approved.",
    )
    assert status.state is TimedSpanAcceptanceState.OUTPUTS_REQUIRED

    second = service.run(package_path)
    requirement = _authority(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )[3].requirements[0]
    keyframe = GovernedIntroductionKeyframeStore(tmp_path).require_approved(requirement)

    assert first.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert provider.calls == 2
    assert injection.calls == 1
    assert keyframe.approval_mode == "human"
    assert keyframe.image_sha256 == candidate.image_sha256
    assert second.final_path is not None
    assert second.acceptance_status.state is TimedSpanAcceptanceState.QC_REQUIRED


def test_rejected_injection_regenerates_new_attempt_without_rerendering_span_one(
    tmp_path: Path,
) -> None:
    package_path, _raw = _candidate_package(
        tmp_path,
        introduction=AssetPresenceIntroduction.ENTER,
    )
    provider = _FakeSpanProvider(tmp_path / "provider")
    injection = _FakeInjectionSynthesizer()
    service = AutomatedTimedSpanOrchestrationService(
        tmp_path,
        span_provider=provider,
        synthesizer=_CountingSynthesizer(),
        injection_synthesizer=injection,
        extractor=_FakeExtractor(tmp_path),
        assembly_runtime=_FakeAssemblyRuntime(tmp_path),
        managed_media_directory="Media Output",
    )

    service.run(package_path)
    acceptance = TimedSpanFunctionalAcceptanceService(tmp_path)
    first = acceptance.injection_candidate(package_path)
    assert first is not None
    acceptance.reject_injection_candidate(
        package_path,
        requirement_id=first.requirement_id,
        rejected_by="Neill Payne",
        notes="Entrance framing is not acceptable.",
    )

    second_result = service.run(package_path)
    second = acceptance.injection_candidate(package_path)

    assert second_result.acceptance_status.state is TimedSpanAcceptanceState.KEYFRAME_REQUIRED
    assert provider.calls == 1
    assert injection.calls == 2
    assert second is not None
    assert second.pending
    assert second.result_id != first.result_id
    assert second.attempt_number == 2
    assert first.decision is None
    first_review = acceptance.injection_reviews.review_for_result(first.result_id)
    assert first_review is not None
    assert first_review.decision is IntroductionInjectionDecision.REJECTED
