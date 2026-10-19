"""Phase 3.7.5 read-only preview readiness and fail-closed UI checks."""

from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import Mock, patch

from vscs.application.episode_assembly_preview import inspect_assembly_preview
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace
from vscs.application.assembly_contracts import (
    AssemblyScope, AssemblyScopeKind, AssemblyTimelineRevision, ShotSelection,
)


def _previous():
    return AssemblyTimelineRevision(
        assembly_id="ASM-1", revision_id="REV-1",
        scope=AssemblyScope("PROD-1", AssemblyScopeKind.EPISODE, "EP-001", "PS-1", "b" * 64),
        selections=(ShotSelection("SCN-1", "SHT-1", "GM-1", "1", "a" * 64,
                                 "HUMAN-QC", 0, 144, 0, "approved"),),
        frame_rate_num=24, frame_rate_den=1,
    )


def test_preview_manifest_valid_approved_frames(tmp_path):
    revision = _previous()
    selection = revision.selections[0]
    media = SimpleNamespace(
        scope=SimpleNamespace(
            production_id=revision.scope.production_id,
            episode_id=revision.scope.scope_id,
            scene_id=selection.scene_id,
            shot_id=selection.shot_id,
        ),
        revision=selection.media_revision,
        file=SimpleNamespace(checksum_sha256=selection.file_checksum),
    )
    validator = Mock()
    validator.validate.return_value = SimpleNamespace(blockers=())
    service = Mock()
    service.get.return_value = media
    details = SimpleNamespace(
        relative_path="generated_media/sample.mp4",
        frame_count=144,
        frame_rate=Fraction(24, 1),
    )
    with (
        patch(
            "vscs.application.episode_assembly_preview.approval_evidence_reference",
            return_value=selection.approval_evidence_ref,
        ),
        patch(
            "vscs.application.episode_assembly_preview.read_approved_video_frames",
            return_value=details,
        ),
    ):
        result = inspect_assembly_preview(
            revision, project_directory=tmp_path, media_service=service, validator=validator
        )
    assert result.ready
    assert result.total_frames == 144
    assert result.segments[0].timeline_start_frame == 0
    assert result.segments[0].timeline_end_frame == 144
    validator.validate.assert_called_once_with(revision, final_use=True)


def test_preview_rejects_out_of_bounds_source_frames(tmp_path):
    revision = _previous()
    selection = revision.selections[0]
    record = SimpleNamespace(
        scope=SimpleNamespace(
            production_id=revision.scope.production_id,
            episode_id=revision.scope.scope_id,
            scene_id=selection.scene_id,
            shot_id=selection.shot_id,
        ),
        revision=selection.media_revision,
        file=SimpleNamespace(checksum_sha256=selection.file_checksum),
    )
    validator, service = Mock(), Mock()
    validator.validate.return_value = SimpleNamespace(blockers=())
    service.get.return_value = record
    with (
        patch(
            "vscs.application.episode_assembly_preview.approval_evidence_reference",
            return_value=selection.approval_evidence_ref,
        ),
        patch(
            "vscs.application.episode_assembly_preview.read_approved_video_frames",
            return_value=SimpleNamespace(frame_count=24, frame_rate=Fraction(24)),
        ),
    ):
        result = inspect_assembly_preview(
            revision, project_directory=tmp_path, media_service=service, validator=validator
        )
    assert not result.ready
    assert any("exceeds actual decoded frames" in error for error in result.blockers)


def test_preview_ui_blocks_without_inspected_revision(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._inspect_playback_preview()
    assert "BLOCKED" in workspace.preview_status.text()
    assert workspace.preview_table.rowCount() == 0
    assert not workspace.complete_button.isEnabled()
