from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image
from vscs.application.production_execution import (
    AutomatedBoundaryValidationState,
    GovernedInternalRenderSpanCompiler,
    GovernedIntroductionKeyframeRequirementCompiler,
    GovernedIntroductionKeyframeStore,
    IntroductionBoundaryProviderCapabilities,
    IntroductionBoundaryStrategy,
    TimedCanonicalReferenceActivationCompiler,
    ProductionExecutionCandidate,
    ProductionExecutionUiService,
    ProductionPackageCompilationState,
    ProductionPackageStatus,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    request_from_requirement,
)
from vscs.application.production_execution.automated_introduction_boundary import (
    AutomatedIntroductionBoundaryResult,
)
from vscs.application.production_tasks import ProductionTaskState, ProductionTaskType
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
from vscs.infrastructure.production_execution.timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
)
from vscs.infrastructure.production_execution.timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    SpanMediaObservation,
)
from vscs.presentation.widgets.production_execution_workspace import ProductionExecutionWorkspace


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png(path: Path, value: tuple[int, int, int] = (10, 20, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1280, 720), value).save(path)
    return path


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
                introduction=AssetPresenceIntroduction.ENTER,
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


def _authority(project: Path) -> tuple[
    TimedAssetPresencePlan,
    Any,
    Any,
    Any,
    dict[str, object],
]:
    timed = _timed()
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


def _candidate_package(project: Path) -> tuple[Path, dict[str, object]]:
    timed, spans, activation, requirements, reference_plan = _authority(project)
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

    assert direct.strategy_for(("character",)) is IntroductionBoundaryStrategy.DIRECT_PROVIDER_REFERENCE
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
    assert "Do not replace, duplicate" in request.positive_prompt


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
    assert result.final_path.is_file()
    assert result.acceptance_status.state is TimedSpanAcceptanceState.QC_REQUIRED
    store = GovernedIntroductionKeyframeStore(tmp_path)
    _timed_plan, _spans, _activation, requirements, _plan = _authority(tmp_path)
    keyframe = store.require_approved(requirements.requirements[0])
    assert keyframe.approval_mode == "automated_structural"
    assert keyframe.target_global_frame_index == 96


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
    deploy = (
        repository / "scripts" / "deploy_comfyui_introduction_boundary_v1.ps1"
    ).read_text(encoding="utf-8")
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

    assert workspace.run_automated_spans_button.isEnabled()
    assert workspace.run_automated_spans_button.text() == "Run Automated Span Orchestration"
    assert "Manual Recovery" in workspace.approve_introduction_keyframe_button.text()
    assert workspace.approve_introduction_keyframe_button.isEnabled()
    assert not workspace.start_button.isEnabled()
