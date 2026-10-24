"""Q3.1.3.5.8d.2: safe native-project asset seeding, no approval or generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.h3_disposable_shot_seed import (
    seed_disposable_single_shot,
)
from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceError,
)


def _project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "RUN-001"
    project = root / "project" / "H3 Isolated Acceptance"
    (project / "assets" / "reference").mkdir(parents=True)
    (project / "database").mkdir()
    (project / "project.vscs").write_text("name: H3 Isolated Acceptance", encoding="utf-8")
    (root / ".vscs_h3_disposable_acceptance").write_text(
        "Q3.1.3.5.8", encoding="utf-8"
    )
    return root, project


def test_seed_creates_only_unapproved_reference_and_brief(tmp_path: Path):
    root, project = _project(tmp_path)
    result = seed_disposable_single_shot(acceptance_root=root, project_directory=project)
    assert result["status"] == "SEED_CREATED_NOT_GOVERNED"
    reference = Path(result["reference"])
    assert reference.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    brief = json.loads(Path(result["brief"]).read_text(encoding="utf-8"))
    assert brief["approved"] is False
    assert brief["task_id"] is None
    assert not (project / "production").exists()


def test_second_seed_refuses_overwrite(tmp_path: Path):
    root, project = _project(tmp_path)
    result = seed_disposable_single_shot(acceptance_root=root, project_directory=project)
    before = Path(result["reference"]).read_bytes()
    with pytest.raises(H3IsolatedAcceptanceError, match="already present"):
        seed_disposable_single_shot(acceptance_root=root, project_directory=project)
    assert Path(result["reference"]).read_bytes() == before


def test_external_project_rejected(tmp_path: Path):
    root, _ = _project(tmp_path)
    outside = tmp_path / "original-project"
    outside.mkdir()
    with pytest.raises(H3IsolatedAcceptanceError, match="disposable"):
        seed_disposable_single_shot(acceptance_root=root, project_directory=outside)


def test_native_project_required(tmp_path: Path):
    root, project = _project(tmp_path)
    (project / "project.vscs").unlink()
    with pytest.raises(H3IsolatedAcceptanceError, match="native"):
        seed_disposable_single_shot(acceptance_root=root, project_directory=project)
