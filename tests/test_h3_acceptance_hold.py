"""Phase 20.19.1 hold protects H3 isolated live execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.h3_acceptance_hold import (
    assert_not_on_hold,
    create_hold,
    hold_path,
)
from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceError,
)


def _scope(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "RUN-001"
    project = root / "project" / "H3 Isolated Acceptance"
    (project / "database").mkdir(parents=True)
    (project / "assets" / "reference").mkdir(parents=True)
    (root / ".vscs_h3_disposable_acceptance").write_text("Q3.1.3.5.8", encoding="utf-8")
    (project / "project.vscs").write_text("name: disposable", encoding="utf-8")
    (project / "h3_acceptance_single_shot_brief.json").write_text(
        '{"approved":false}', encoding="utf-8"
    )
    (project / "assets" / "reference" / "h3_acceptance_console.png").write_bytes(
        b"synthetic-reference"
    )
    return root, project


def test_hold_is_write_once_and_blocks_live_entry(tmp_path: Path):
    root, project = _scope(tmp_path)
    evidence = create_hold(root, project)
    assert evidence["status"] == "H3_LIVE_GENERATION_ON_HOLD"
    assert evidence["provider_submission_authorized"] is False
    original = hold_path(root).read_bytes()
    with pytest.raises(H3IsolatedAcceptanceError, match="on hold"):
        assert_not_on_hold(root)
    with pytest.raises(H3IsolatedAcceptanceError, match="already exists"):
        create_hold(root, project)
    assert hold_path(root).read_bytes() == original


def test_hold_rejects_external_project_without_writes(tmp_path: Path):
    root, _ = _scope(tmp_path)
    external = tmp_path / "production"
    external.mkdir()
    with pytest.raises(H3IsolatedAcceptanceError, match="disposable root"):
        create_hold(root, external)
    assert not hold_path(root).exists()


def test_missing_marker_rejected(tmp_path: Path):
    root, project = _scope(tmp_path)
    (root / ".vscs_h3_disposable_acceptance").unlink()
    with pytest.raises(H3IsolatedAcceptanceError, match="disposable marker"):
        create_hold(root, project)
    assert not hold_path(root).exists()


def test_unheld_scope_is_not_blocked(tmp_path: Path):
    root, _ = _scope(tmp_path)
    assert_not_on_hold(root)
