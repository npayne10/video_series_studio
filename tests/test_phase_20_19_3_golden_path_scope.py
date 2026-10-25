"""Golden-path scope requires a separate native project and active H3 hold."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.golden_path_scope import (
    GoldenPathScopeError,
    inspect_golden_path_scope,
)


def _roots(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "GOLDEN-PATH" / "project" / "Episode Audit"
    (project / "database").mkdir(parents=True)
    (project / "project.vscs").write_text("name: Episode Audit", encoding="utf-8")
    h3 = tmp_path / "H3_ACCEPTANCE" / "RUN-001"
    h3.mkdir(parents=True)
    (h3 / ".vscs_h3_live_hold.json").write_text(
        json.dumps(
            {
                "status": "H3_LIVE_GENERATION_ON_HOLD",
                "provider_submission_authorized": False,
            }
        ),
        encoding="utf-8",
    )
    return project, h3


def test_isolated_native_project_passes_without_mutation(tmp_path: Path):
    project, h3 = _roots(tmp_path)
    before = (project / "project.vscs").read_bytes()
    result = inspect_golden_path_scope(
        audit_project=project,
        h3_acceptance_root=h3,
        prohibited_project_roots=(tmp_path / "VSCS TSR2",),
    )
    assert result["status"] == "ISOLATED_NATIVE_PROJECT_READY_FOR_UI_TRACE"
    assert result["provider_submitted"] is False
    assert result["governed_task_created"] is False
    assert (project / "project.vscs").read_bytes() == before


def test_rejects_audit_inside_h3_acceptance(tmp_path: Path):
    _, h3 = _roots(tmp_path)
    project = h3 / "project"
    (project / "database").mkdir(parents=True)
    (project / "project.vscs").write_text("name: forbidden", encoding="utf-8")
    with pytest.raises(GoldenPathScopeError, match="H3 acceptance"):
        inspect_golden_path_scope(
            audit_project=project,
            h3_acceptance_root=h3,
            prohibited_project_roots=(),
        )


def test_rejects_project_inside_protected_root(tmp_path: Path):
    project, h3 = _roots(tmp_path)
    with pytest.raises(GoldenPathScopeError, match="protected production"):
        inspect_golden_path_scope(
            audit_project=project,
            h3_acceptance_root=h3,
            prohibited_project_roots=(project.parent.parent,),
        )


def test_missing_or_inactive_hold_blocks(tmp_path: Path):
    project, h3 = _roots(tmp_path)
    hold = h3 / ".vscs_h3_live_hold.json"
    hold.unlink()
    with pytest.raises(GoldenPathScopeError, match="hold evidence missing"):
        inspect_golden_path_scope(
            audit_project=project,
            h3_acceptance_root=h3,
            prohibited_project_roots=(),
        )
    hold.write_text(
        json.dumps({"status": "RELEASED", "provider_submission_authorized": True}),
        encoding="utf-8",
    )
    with pytest.raises(GoldenPathScopeError, match="not confirmed on hold"):
        inspect_golden_path_scope(
            audit_project=project,
            h3_acceptance_root=h3,
            prohibited_project_roots=(),
        )
