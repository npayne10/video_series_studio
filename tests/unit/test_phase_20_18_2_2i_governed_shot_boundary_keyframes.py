from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.application.production_execution import (
    CompiledProductionPackage,
    GovernedClosingBoundaryFrame,
    GovernedShotBoundaryError,
    GovernedShotBoundaryStore,
    ShotBoundaryContinuityMode,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaGovernanceEvent,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository
from vscs.infrastructure.production_execution.ltx25_keyframe_backend import (
    CurrentAuthorityLTX25GovernedKeyframeCompilationService,
)
from vscs.infrastructure.production_execution.shot_boundary_runtime import (
    GovernedShotBoundaryRuntime,
    GovernedShotBoundaryRuntimeError,
    VideoBoundaryObservation,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _media(
    project: Path,
    persistence: GeneratedMediaPersistenceService,
    *,
    state: GeneratedMediaState,
    media_id: str = "GM-SHT-001",
    shot_id: str = "EP-001-SCN-001-SHT-001",
    task_id: str = "PT-VIDEO-SHT-001",
) -> GeneratedMedia:
    relative = Path("Media Output") / "generated_media" / f"{media_id}.mp4"
    source = project / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"governed-video-144-frames")
    history: tuple[GeneratedMediaGovernanceEvent, ...] = ()
    if state is GeneratedMediaState.APPROVED:
        history = (
            GeneratedMediaGovernanceEvent(
                from_state=GeneratedMediaState.GENERATED,
                to_state=GeneratedMediaState.UNDER_REVIEW,
                actor="human:Neill",
                reason="Submit for acceptance",
            ),
            GeneratedMediaGovernanceEvent(
                from_state=GeneratedMediaState.UNDER_REVIEW,
                to_state=GeneratedMediaState.APPROVED,
                actor="human:Neill",
                reason="Accepted production result",
            ),
        )
    media = GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id=shot_id,
            production_task_id=task_id,
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="PEX-A005",
            provider_id="LOCAL-COMFYUI-GPU-01",
            provider_job_id="prompt-A005",
        ),
        file=GeneratedMediaFile(
            relative_path=relative.as_posix(),
            checksum_sha256=_sha(source),
            size_bytes=source.stat().st_size,
        ),
        state=state,
        governance_history=history,
    )
    persistence.save(media)
    return media


class _FakeBoundaryRuntime(GovernedShotBoundaryRuntime):
    def __init__(
        self,
        project_directory: Path,
        media: GeneratedMediaPersistenceService,
    ) -> None:
        self.project_directory = project_directory.resolve()
        self.media = media
        self.store = GovernedShotBoundaryStore(self.project_directory)
        self.ffmpeg = "ffmpeg"
        self.ffprobe = "ffprobe"
        self.extracted_index: int | None = None

    def _observe_video(self, path: Path) -> VideoBoundaryObservation:
        assert path.is_file()
        return VideoBoundaryObservation(
            frame_count=144,
            width=1280,
            height=720,
            frame_rate="24/1",
        )

    def _extract_frame(self, source: Path, frame_index: int, destination: Path) -> None:
        assert source.is_file()
        self.extracted_index = frame_index
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(f"frame-{frame_index}".encode())


def test_closing_boundary_rejects_non_approved_generated_media(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(tmp_path / "media"))
    media = _media(project, persistence, state=GeneratedMediaState.GENERATED)

    with pytest.raises(
        GovernedShotBoundaryRuntimeError,
        match="only from APPROVED Generated Media",
    ):
        _FakeBoundaryRuntime(project, persistence).publish_closing(
            media.media_id,
            published_by="Neill Payne",
        )


def test_closing_boundary_publishes_exact_final_governed_frame(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(tmp_path / "media"))
    media = _media(project, persistence, state=GeneratedMediaState.APPROVED)
    runtime = _FakeBoundaryRuntime(project, persistence)

    boundary = runtime.publish_closing(media.media_id, published_by="Neill Payne")

    assert runtime.extracted_index == 143
    assert boundary.frame_index == 143
    assert boundary.frame_count == 144
    assert boundary.width == 1280
    assert boundary.height == 720
    assert boundary.frame_rate == "24/1"
    assert boundary.source_media_id == media.media_id
    assert boundary.source_media_sha256 == media.file.checksum_sha256
    assert boundary.source_media_path == media.file.relative_path
    assert boundary.image_sha256 == _sha(project / boundary.image_path)


def test_continuous_opening_inherits_published_closing_boundary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(tmp_path / "media"))
    media = _media(project, persistence, state=GeneratedMediaState.APPROVED)
    boundary = _FakeBoundaryRuntime(project, persistence).publish_closing(
        media.media_id,
        published_by="Neill Payne",
    )
    store = GovernedShotBoundaryStore(project)

    opening = store.resolve_opening(
        "EP-001-SCN-001-SHT-002",
        {
            "continuity": {
                "shot_boundary_mode": "continuous",
                "source_shot_id": "EP-001-SCN-001-SHT-001",
            }
        },
    )

    assert opening.mode is ShotBoundaryContinuityMode.CONTINUOUS
    assert opening.inherited
    assert opening.boundary_id == boundary.boundary_id
    assert opening.image_sha256 == boundary.image_sha256
    assert opening.source_media_sha256 == boundary.source_media_sha256


@pytest.mark.parametrize(
    "mode",
    ("new_composition", "scene_entry", "discontinuity"),
)
def test_non_continuous_modes_do_not_inherit(mode: str, tmp_path: Path) -> None:
    store = GovernedShotBoundaryStore(tmp_path)

    opening = store.resolve_opening(
        "EP-001-SCN-001-SHT-002",
        {"continuity": {"shot_boundary_mode": mode}},
    )

    assert not opening.inherited
    assert opening.boundary_id is None
    assert opening.image_path is None


def test_inherited_opening_fails_closed_when_source_media_checksum_changes(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(tmp_path / "media"))
    media = _media(project, persistence, state=GeneratedMediaState.APPROVED)
    _FakeBoundaryRuntime(project, persistence).publish_closing(
        media.media_id,
        published_by="Neill Payne",
    )
    store = GovernedShotBoundaryStore(project)
    authority = {
        "continuity": {
            "shot_boundary_mode": "continuous",
            "source_shot_id": "EP-001-SCN-001-SHT-001",
        }
    }
    compiled = store.resolve_opening(
        "EP-001-SCN-001-SHT-002",
        authority,
    ).to_dict()

    source = project / media.file.relative_path
    source.write_bytes(b"changed-after-acceptance")

    with pytest.raises(GovernedShotBoundaryError, match="checksum changed"):
        store.validate_compiled_opening(
            "EP-001-SCN-001-SHT-002",
            authority,
            compiled,
        )


def test_candidate_c_compiles_inherited_boundary_as_opening_keyframe(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    source = project / "Media Output" / "accepted.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"accepted-video")
    image = project / ".vscs" / "governed_shot_boundaries" / "SHT-001" / "closing.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"closing-frame")
    closing = GovernedClosingBoundaryFrame(
        boundary_id="GBF-SHT001",
        shot_id="EP-001-SCN-001-SHT-001",
        image_path=image.relative_to(project).as_posix(),
        image_sha256=_sha(image),
        source_media_id="GM-SHT-001",
        source_execution_id="PEX-A005",
        source_media_revision=1,
        source_media_path=source.relative_to(project).as_posix(),
        source_media_sha256=_sha(source),
        frame_index=143,
        frame_count=144,
        width=1280,
        height=720,
        frame_rate="24/1",
        published_by="Neill Payne",
        published_at="2026-09-23T13:00:00+02:00",
    )
    GovernedShotBoundaryStore(project).save(closing)
    compiled = CompiledProductionPackage(
        task_id="PT-VIDEO-SHT-002",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="EP-001-SCN-001-SHT-002",
        profile="production",
        authority_id="UPD-SHT-002",
        authority_revision=1,
        authority_fingerprint="authority-002",
        approved_by="Neill Payne",
        source_package_id="PP-SHT-002",
        source_package_fingerprint="source-002",
        source_schema_version="1.0",
        universal_text="continue from the prior accepted shot",
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
            "continuity": {
                "shot_boundary_mode": "continuous",
                "source_shot_id": "EP-001-SCN-001-SHT-001",
            },
            "action_performance": {"spoken_content": ""},
            "dialogue": [],
        },
        package_fingerprint="placeholder",
        motion_prompt="Continue the accepted action without changing composition.",
    )

    payload = CurrentAuthorityLTX25GovernedKeyframeCompilationService(project)._comfyui_payload(
        compiled
    )

    opening = payload["shot_boundary_continuity"]
    keyframe = payload["governed_keyframe"]
    assert opening["mode"] == "continuous"
    assert opening["boundary_id"] == closing.boundary_id
    assert keyframe["source_kind"] == "governed_closing_boundary"
    assert keyframe["frame_index"] == 143
    assert keyframe["frame_count"] == 144
    assert payload["_vscs_manifest"]["compiler"].startswith("VSCS Phase 20.18.2.2i")
