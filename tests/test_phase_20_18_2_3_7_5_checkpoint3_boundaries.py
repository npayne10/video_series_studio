"""Boundary inspection is read-only, verifies adjacency, and fails closed."""

from fractions import Fraction
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

from vscs.application.episode_assembly_boundaries import (
    boundary_pair,
    extract_verified_boundary_png,
)
from vscs.application.episode_assembly_preview import AssemblyPreviewPlan, PreviewSegment
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _plan(blockers=()):
    a = PreviewSegment("SHT-001", "GM-1", "a.mp4", 0, 24, Fraction(24), 0, 24)
    b = PreviewSegment("SHT-002", "GM-2", "b.mp4", 2, 146, Fraction(24), 24, 168)
    return AssemblyPreviewPlan("ASM-1", "REV-1", "a" * 64, (a, b), blockers, Fraction(24))


def test_boundary_selects_last_included_and_first_included_source_frame():
    pair = boundary_pair(_plan(), 0)
    assert (pair.outgoing_frame, pair.incoming_frame) == (23, 2)
    assert pair.outgoing.shot_id == "SHT-001"
    with pytest.raises(ValueError, match="adjacent"):
        boundary_pair(_plan(), 1)
    with pytest.raises(ValueError, match="Verify"):
        boundary_pair(_plan(("not approved",)), 0)


def test_boundary_decoder_is_in_memory_and_checks_png(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"sample")
    segment = _plan().segments[0]
    runner = Mock(return_value=SimpleNamespace(stdout=b"\x89PNG\r\n\x1a\nimage"))
    assert extract_verified_boundary_png(tmp_path, segment, 23, runner=runner).startswith(
        b"\x89PNG"
    )
    args = runner.call_args.args[0]
    assert "-vf" in args and "-frames:v" in args
    assert args[args.index("-vf") + 1] == r"select=eq(n\,23)"
    with pytest.raises(ValueError, match="outside"):
        extract_verified_boundary_png(tmp_path, segment, 24, runner=runner)
    assert runner.call_count == 1


def test_boundary_decoder_rejects_missing_image(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"sample")
    runner = Mock(return_value=SimpleNamespace(stdout=b"not a PNG"))
    with pytest.raises(ValueError, match="valid PNG"):
        extract_verified_boundary_png(tmp_path, _plan().segments[0], 23, runner=runner)


def test_boundary_ui_blocks_until_verified(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    assert not workspace.boundary_inspect.isEnabled()
    workspace._inspect_boundary()
    assert "BLOCKED" in workspace.boundary_status.text()
    assert not workspace.complete_button.isEnabled()


def test_boundary_ui_decodes_actual_qt_png_without_geometry_expansion(
    qtbot, tmp_path, monkeypatch
):
    from vscs.presentation.widgets import episode_assembly_workspace as module

    image = QImage(16, 12, QImage.Format.Format_RGB32)
    image.fill(0xFF2377AA)
    data = QByteArray()
    buffer = QBuffer(data)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    monkeypatch.setattr(module, "extract_verified_boundary_png", lambda *_args: bytes(data))

    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._playback_plan = _plan()
    workspace._playback_project = tmp_path
    workspace.boundary_selector.addItem("SHT-001 to SHT-002", 0)
    workspace.boundary_inspect.setEnabled(True)
    workspace._inspect_boundary()

    assert workspace.boundary_outgoing_image.pixmap() is not None
    assert workspace.boundary_incoming_image.pixmap() is not None
    assert "frame 23" in workspace.boundary_status.text()
    assert "frame 2" in workspace.boundary_status.text()
    assert len(workspace.boundary_status.text()) < 260


def test_boundary_ui_never_exposes_raw_png_bytes_in_error_text(
    qtbot, tmp_path, monkeypatch
):
    from vscs.presentation.widgets import episode_assembly_workspace as module

    def fail(*_args):
        raise TypeError("Qt decoding failed: " + "binary" * 20000)

    monkeypatch.setattr(module, "extract_verified_boundary_png", fail)
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._playback_plan = _plan()
    workspace._playback_project = tmp_path
    workspace.boundary_selector.addItem("SHT-001 to SHT-002", 0)
    workspace._inspect_boundary()
    assert workspace.boundary_status.text().startswith("BLOCKED:")
    assert len(workspace.boundary_status.text()) < 240
