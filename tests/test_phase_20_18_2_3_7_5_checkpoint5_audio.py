"""Phase 3.7.5 Checkpoint 5 technical audio readiness regressions."""

import json
from fractions import Fraction
from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from vscs.application.episode_assembly_audio_readiness import inspect_assembly_audio
from vscs.application.episode_assembly_preview import AssemblyPreviewPlan, PreviewSegment
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _plan(blockers=()):
    segments = (
        PreviewSegment("SHT-001", "GM-1", "a.mp4", 0, 24, Fraction(24), 0, 24),
        PreviewSegment("SHT-002", "GM-2", "b.mp4", 0, 144, Fraction(24), 24, 168),
    )
    return AssemblyPreviewPlan("ASM", "REV", "f" * 64, segments, blockers, Fraction(24))


def test_audio_inspection_reports_silence_without_approval(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    (tmp_path / "b.mp4").write_bytes(b"video")
    payloads = [
        {"streams": []},
        {"streams": [{"codec_name": "aac", "channels": 2, "sample_rate": "48000"}]},
    ]
    def run(*_args, **_kwargs):
        return CompletedProcess([], 0, json.dumps(payloads.pop(0)), "")

    with patch("vscs.application.episode_assembly_audio_readiness.subprocess.run", run):
        report = inspect_assembly_audio(_plan(), tmp_path)
    assert report.silent_shots == 1
    assert report.shots[0].technical_findings
    assert report.shots[1].sample_rate == 48000
    assert "presence changes" in report.continuity_findings[0]


def test_audio_inspection_rejects_unverified_plan(tmp_path):
    with pytest.raises(ValueError, match="fully verified"):
        inspect_assembly_audio(_plan(("Unapproved media",)), tmp_path)


def test_audio_inspection_fails_closed_on_ambiguous_streams(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    streams = {
        "streams": [
            {"codec_name": "aac", "channels": 2, "sample_rate": "48000"},
            {"codec_name": "opus", "channels": 2, "sample_rate": "48000"},
        ]
    }
    with patch(
        "vscs.application.episode_assembly_audio_readiness.subprocess.run",
        return_value=CompletedProcess([], 0, json.dumps(streams), ""),
    ), pytest.raises(ValueError, match="SHT-001"):
        inspect_assembly_audio(_plan(), tmp_path)


def test_audio_ui_requires_verified_playback_plan(qtbot, tmp_path):
    widget = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(widget)
    assert not widget.audio_inspect_button.isEnabled()
    widget._inspect_audio_readiness()
    assert widget.audio_status.text().startswith("BLOCKED:")
    assert not widget.complete_button.isEnabled()
