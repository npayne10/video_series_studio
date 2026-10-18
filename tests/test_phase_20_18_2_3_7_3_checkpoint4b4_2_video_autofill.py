"""Verified video-frame metadata autofill, with no approval or publication mutation."""

import hashlib
import json
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vscs.application.episode_video_frame_inspection import read_approved_video_frames
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _record(data, *, state="approved", checksum=None):
    return SimpleNamespace(
        media_id="GM-1",
        kind=SimpleNamespace(value="video"),
        state=SimpleNamespace(value=state),
        governance_history=(SimpleNamespace(to_state=SimpleNamespace(value="approved")),),
        file=SimpleNamespace(
            relative_path="media/approved.mp4",
            size_bytes=len(data),
            checksum_sha256=checksum or hashlib.sha256(data).hexdigest(),
        ),
    )


def test_reads_exact_approved_frame_count_after_checksum(tmp_path):
    folder = tmp_path / "media"
    folder.mkdir()
    (folder / "approved.mp4").write_bytes(b"verified-video-bytes")
    record = _record(b"verified-video-bytes")
    result = SimpleNamespace(
        stdout=json.dumps({"streams": [{"nb_read_frames": "144", "avg_frame_rate": "24/1"}]})
    )
    with patch(
        "vscs.application.episode_video_frame_inspection.subprocess.run", return_value=result
    ) as run:
        details = read_approved_video_frames(tmp_path, record)
    assert details.frame_count == 144
    assert details.duration_seconds == 6
    assert run.call_args.args[0][-1] == str(folder / "approved.mp4")


def test_rejects_modified_bytes_without_running_probe(tmp_path):
    folder = tmp_path / "media"
    folder.mkdir()
    (folder / "approved.mp4").write_bytes(b"tampered")
    with patch("vscs.application.episode_video_frame_inspection.subprocess.run") as run:
        with pytest.raises(ValueError, match="checksum or size mismatch"):
            read_approved_video_frames(tmp_path, _record(b"original"))
    run.assert_not_called()


def test_rejects_pending_qc(tmp_path):
    with pytest.raises(ValueError, match="human-approved"):
        read_approved_video_frames(tmp_path, _record(b"bytes", state="generated"))


def test_rejects_missing_or_invalid_frame_count(tmp_path):
    folder = tmp_path / "media"
    folder.mkdir()
    (folder / "approved.mp4").write_bytes(b"bytes")
    with patch(
        "vscs.application.episode_video_frame_inspection.subprocess.run",
        return_value=SimpleNamespace(stdout='{"streams":[{"avg_frame_rate":"24/1"}]}'),
    ):
        with pytest.raises(ValueError, match="frame count or frame rate"):
            read_approved_video_frames(tmp_path, _record(b"bytes"))


def test_ui_autofill_requires_staged_approved_media(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._autofill_source_frames()
    assert workspace.draft_status.text().startswith("BLOCKED:")
    assert not workspace.complete_button.isEnabled()
