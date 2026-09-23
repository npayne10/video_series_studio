from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import vscs.infrastructure.production_execution.ltx25_keyframe_backend as ltx25_module
from vscs.application.production_execution import (
    KEYFRAME_ACCEPTANCE_CRITERIA,
    CompiledProductionPackage,
    GovernedShotKeyframe,
    GovernedShotKeyframeStore,
    ProviderAudioAction,
    ProviderAudioPolicyMode,
    resolve_provider_audio_policy,
)
from vscs.application.provider_execution import ProviderExecutionOutput
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    CurrentAuthorityLTX25GovernedKeyframeCompilationService,
    LocalComfyUIProductionExecutionBackend,
)
from vscs.infrastructure.production_execution.provider_audio_runtime import (
    ProviderAudioGovernanceRuntime,
)


class _FakeAudioRuntime(ProviderAudioGovernanceRuntime):
    def __init__(self) -> None:
        self.ffmpeg = "ffmpeg"
        self.ffprobe = "ffprobe"

    def _strip_audio(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())

    def _audio_stream_count(self, path: Path) -> int:
        assert path.is_file()
        return 0


def test_no_dialogue_resolves_to_silent_visual_and_discards_provider_audio() -> None:
    policy = resolve_provider_audio_policy(
        {"action_performance": {"spoken_content": ""}, "dialogue": []}
    )

    assert policy.mode is ProviderAudioPolicyMode.SILENT_VISUAL
    assert policy.provider_audio_action is ProviderAudioAction.DISCARD
    assert policy.authoritative_audio_source == "vscs_audio_pipeline"


def test_dialogue_resolves_to_canonical_dialogue_but_still_discards_provider_audio() -> None:
    policy = resolve_provider_audio_policy(
        {
            "action_performance": {"spoken_content": "Report the reading."},
            "dialogue": [{"text": "Report the reading."}],
        }
    )

    assert policy.mode is ProviderAudioPolicyMode.CANONICAL_DIALOGUE
    assert policy.provider_audio_action is ProviderAudioAction.DISCARD
    assert policy.authoritative_audio_source == "vscs_audio_pipeline"


def test_explicit_generated_ambience_preserves_provider_audio_for_mix() -> None:
    policy = resolve_provider_audio_policy({"provider_audio_policy": "generated_ambience"})

    assert policy.mode is ProviderAudioPolicyMode.GENERATED_AMBIENCE
    assert policy.provider_audio_action is ProviderAudioAction.PRESERVE_FOR_MIX


def test_silent_visual_runtime_strips_video_audio_and_drops_audio_only_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "provider"
    source.mkdir()
    (source / "shot.mp4").write_bytes(b"video-container")
    (source / "shot.wav").write_bytes(b"provider-audio")
    outputs = (
        ProviderExecutionOutput(
            output_id="PEO-VIDEO",
            relative_path="shot.mp4",
            media_kind="production_video",
        ),
        ProviderExecutionOutput(
            output_id="PEO-AUDIO",
            relative_path="shot.wav",
            media_kind="audio",
        ),
    )
    policy = resolve_provider_audio_policy({"dialogue": []})

    result = _FakeAudioRuntime().apply(
        policy,
        execution_id="PEX-A005",
        outputs=outputs,
        source_root=source,
        staging_root=tmp_path / "governed",
    )

    assert len(result.outputs) == 1
    output = result.outputs[0]
    assert output.media_kind == "production_video"
    assert output.relative_path == "video/PEO-VIDEO.mp4"
    metadata = dict(output.metadata)
    assert metadata["provider_audio_policy"] == "silent_visual"
    assert metadata["provider_audio_action"] == "discarded"
    assert metadata["provider_audio_authority"] == "vscs_audio_pipeline"
    assert metadata["provider_audio_original_path"] == "shot.mp4"
    assert metadata["provider_video_stream_copy"] == "true"
    assert "discarded 1 separate audio output" in result.note


def test_generated_ambience_runtime_keeps_original_source_bytes(tmp_path: Path) -> None:
    source = tmp_path / "provider"
    source.mkdir()
    (source / "shot.mp4").write_bytes(b"provider-container")
    output = ProviderExecutionOutput(
        output_id="PEO-VIDEO",
        relative_path="shot.mp4",
        media_kind="production_video",
    )
    policy = resolve_provider_audio_policy({"provider_audio_policy": "generated_ambience"})

    result = _FakeAudioRuntime().apply(
        policy,
        execution_id="PEX-A006",
        outputs=(output,),
        source_root=source,
        staging_root=tmp_path / "governed",
    )

    assert result.source_root == source.resolve()
    assert result.outputs[0].relative_path == "shot.mp4"
    metadata = dict(result.outputs[0].metadata)
    assert metadata["provider_audio_action"] == "preserved"


def test_candidate_c_compiled_payload_declares_silent_visual_audio_authority(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    image = project / "opening.png"
    image.write_bytes(b"approved-opening")
    record = GovernedShotKeyframe(
        shot_id="EP-001-SCN-001-SHT-001",
        image_path="opening.png",
        image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        approved_by="Neill Payne",
        approved_at="2026-09-22T19:00:00+02:00",
        acceptance_criteria=KEYFRAME_ACCEPTANCE_CRITERIA,
    )
    GovernedShotKeyframeStore(project).save(record)
    compiled = CompiledProductionPackage(
        task_id="PT-VIDEO-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=record.shot_id,
        profile="production",
        authority_id="UPD-SHT-001",
        authority_revision=1,
        authority_fingerprint="authority",
        approved_by="Neill Payne",
        source_package_id="PP-SHT-001",
        source_package_fingerprint="source",
        source_schema_version="1.0",
        universal_text="governed shot",
        positive_prompt="positive",
        negative_prompt="negative",
        previous_approved_final_frame=None,
        filename_prefix="XORIX/EP-001/PT-VIDEO-001",
        width=1280,
        height=720,
        frame_count=144,
        frames_per_second=24,
        cfg=1.0,
        ic_lora_strength=1.0,
        seed=42,
        composition_plan={},
        production_authority={
            "action_performance": {"spoken_content": ""},
            "dialogue": [],
        },
        package_fingerprint="placeholder",
        motion_prompt="Sandra notices the reading while James remains focused forward.",
    )
    service = CurrentAuthorityLTX25GovernedKeyframeCompilationService(project)

    payload = service._comfyui_payload(compiled)

    audio = payload["provider_audio_policy"]
    assert audio["mode"] == "silent_visual"
    assert audio["provider_audio_action"] == "discard"
    assert audio["authoritative_audio_source"] == "vscs_audio_pipeline"
    assert payload["_vscs_manifest"]["compiler"].startswith("VSCS Phase 20.18.2.2h")


def test_candidate_c_pre_ingestion_hook_applies_compiled_audio_policy(
    monkeypatch, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = tmp_path / "provider"
    source.mkdir()
    (source / "shot.mp4").write_bytes(b"provider-container")
    package_path = project / "production_package.json"
    package_path.write_text("{}\n", encoding="utf-8")
    policy = resolve_provider_audio_policy({"dialogue": []}).to_dict()

    class _ExecutionProfiles:
        def profile_for_execution(self, execution_id: str) -> str:
            assert execution_id == "PEX-A005"
            return "production"

    class _PackageCompilation:
        def require_current(self, task: object, *, profile: str) -> SimpleNamespace:
            del task
            assert profile == "production"
            return SimpleNamespace(path=package_path)

        def _read_json(self, path: Path) -> dict[str, object]:
            assert path == package_path
            return {"provider_audio_policy": policy}

    backend = object.__new__(LocalComfyUIProductionExecutionBackend)
    backend.project_directory = project
    backend.comfyui_output_directory = source
    backend.execution_profiles = _ExecutionProfiles()
    backend.package_compilation = _PackageCompilation()
    monkeypatch.setattr(ltx25_module, "ProviderAudioGovernanceRuntime", _FakeAudioRuntime)

    output = ProviderExecutionOutput(
        output_id="PEO-VIDEO",
        relative_path="shot.mp4",
        media_kind="production_video",
    )

    governed_outputs, governed_root, note = backend._prepare_outputs_for_ingestion(
        SimpleNamespace(),
        SimpleNamespace(execution_id="PEX-A005"),
        (output,),
    )

    assert (
        governed_root
        == (project / ".vscs" / "provider_executions" / "audio_governance" / "PEX-A005").resolve()
    )
    assert len(governed_outputs) == 1
    governed = governed_outputs[0]
    assert governed.relative_path == "video/PEO-VIDEO.mp4"
    metadata = dict(governed.metadata)
    assert metadata["provider_audio_policy"] == "silent_visual"
    assert metadata["provider_audio_action"] == "discarded"
    assert metadata["provider_audio_authority"] == "vscs_audio_pipeline"
    assert metadata["provider_video_stream_copy"] == "true"
    assert "authoritative audio remains with VSCS" in note
