from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

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
    GovernedMiniMaxH3SpanOrchestrationService,
    MiniMaxH3SpanExecution,
    MiniMaxH3SpanOrchestrationError,
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
    requirements = IntroductionKeyframeRequirementPlan.from_dict(raw)
    requirement = requirements.requirements[0]
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
        approved_at="2026-10-03T13:00:00+02:00",
    )
    store.save(record, requirement)


class _Provider:
    def __init__(self, root: Path, *, fail_sequence: int | None = None) -> None:
        self.root = root
        self.fail_sequence = fail_sequence
        self.executions: list[MiniMaxH3SpanExecution] = []
        self.freed = False

    def render(self, execution: MiniMaxH3SpanExecution) -> Path:
        self.executions.append(execution)
        if execution.sequence_number == self.fail_sequence:
            raise MiniMaxH3SpanOrchestrationError("provider failed")
        path = self.root / f"provider-{execution.sequence_number:03d}.mp4"
        path.write_bytes(f"raw-{execution.provider_frame_count}".encode())
        return path

    def free_models_and_memory(self) -> None:
        self.freed = True


class _Normalizer:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int]] = []

    def normalize(
        self,
        source_path: Path,
        destination_path: Path,
        *,
        provider_frame_count: int,
        governed_frame_count: int,
        frames_per_second: int,
    ) -> Path:
        assert source_path.is_file()
        self.calls.append((provider_frame_count, governed_frame_count, frames_per_second))
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(f"normalized-{governed_frame_count}".encode())
        return destination_path


@dataclass
class _AssemblyEvidence:
    final_path: str


class _Assembler:
    def __init__(self) -> None:
        self.span_paths: tuple[Path, ...] = ()
        self.compiled_package: dict[str, object] | None = None

    def assemble(
        self,
        compiled_package: dict[str, object],
        span_paths: tuple[Path, ...],
        output_path: Path,
    ) -> _AssemblyEvidence:
        self.compiled_package = compiled_package
        self.span_paths = span_paths
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"assembled-144")
        return _AssemblyEvidence(final_path=str(output_path))


def test_h3_orchestration_renders_normalizes_and_assembles_exact_span_sequence(
    tmp_path: Path,
) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    provider = _Provider(tmp_path)
    normalizer = _Normalizer()
    assembler = _Assembler()
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=provider,
        normalizer=normalizer,
        assembler=assembler,
    )

    result = service.run(compiled)

    assert len(provider.executions) == 2
    first, second = provider.executions
    assert (first.governed_frame_count, first.provider_frame_count) == (96, 103)
    assert (second.governed_frame_count, second.provider_frame_count) == (48, 55)
    assert first.guide_frame_idx == second.guide_frame_idx == 0
    assert "REF-ROS" not in tuple(slot.reference_id for slot in first.reference_slots)
    assert "REF-ROS" in tuple(slot.reference_id for slot in second.reference_slots)
    assert normalizer.calls == [(103, 96, 24), (55, 48, 24)]
    assert tuple(path.name for path in assembler.span_paths) == (
        "span-001.mp4",
        "span-002.mp4",
    )
    assert assembler.compiled_package is not None
    assert assembler.compiled_package["internal_render_spans"] == compiled.internal_render_spans
    assert result.final_path.is_file()
    assert result.plan_id.startswith("H3SPANPLAN-")
    assert provider.freed is True


def test_h3_orchestration_persists_provider_plan_and_output_manifest(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    provider = _Provider(tmp_path)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=provider,
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    result = service.run(compiled)

    manifest = next(
        (tmp_path / ".vscs" / "h3_span_orchestration").rglob("orchestration.json")
    )
    content = manifest.read_text(encoding="utf-8")
    assert '"provider": "minimax-h3-ref2va"' in content
    assert '"assembly_policy": "concatenate_normalized_span_outputs_in_sequence"' in content
    assert '"guide_frame_idx": 0' in content
    assert '"temporal_asset_gate": false' in content
    assert str(result.final_path) in content


def test_h3_orchestration_frees_provider_memory_when_second_span_fails(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    provider = _Provider(tmp_path, fail_sequence=2)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=provider,
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    with pytest.raises(MiniMaxH3SpanOrchestrationError, match="provider failed"):
        service.run(compiled)

    assert [item.sequence_number for item in provider.executions] == [1, 2]
    assert provider.freed is True


def test_h3_orchestration_rejects_final_output_outside_project(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    provider = _Provider(tmp_path)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=provider,
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    with pytest.raises(
        MiniMaxH3SpanOrchestrationError,
        match="inside the VSCS project",
    ):
        service.run(
            compiled,
            output_path=tmp_path.parent / "outside.mp4",
        )


def test_h3_orchestration_requires_all_provider_outputs_to_exist(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)

    class MissingProvider(_Provider):
        def render(self, execution: MiniMaxH3SpanExecution) -> Path:
            self.executions.append(execution)
            return self.root / "missing.mp4"

    provider = MissingProvider(tmp_path)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=provider,
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    with pytest.raises(
        MiniMaxH3SpanOrchestrationError,
        match="missing span output",
    ):
        service.run(compiled)

    assert provider.freed is True


def test_h3_orchestration_blocks_without_approved_introduction_keyframe(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=_Provider(tmp_path),
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    with pytest.raises(
        MiniMaxH3SpanOrchestrationError,
        match="authority is invalid",
    ):
        service.run(compiled)


def test_h3_orchestration_uses_requested_project_relative_final_path(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=_Provider(tmp_path),
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    result = service.run(compiled, output_path=Path("Media Output") / "SHT-002.mp4")

    assert result.final_path == (tmp_path / "Media Output" / "SHT-002.mp4").resolve()
    assert result.final_path.is_file()


def test_h3_orchestration_result_preserves_raw_and_normalized_span_order(tmp_path: Path) -> None:
    compiled = _compiled(tmp_path)
    _approve_intro(tmp_path, compiled)
    service = GovernedMiniMaxH3SpanOrchestrationService(
        tmp_path,
        provider=_Provider(tmp_path),
        normalizer=_Normalizer(),
        assembler=_Assembler(),
    )

    result = service.run(compiled)

    assert tuple(path.name for path in result.raw_span_paths) == (
        "provider-001.mp4",
        "provider-002.mp4",
    )
    assert tuple(path.name for path in result.normalized_span_paths) == (
        "span-001.mp4",
        "span-002.mp4",
    )
