"""Q3.1.3.5.8d.1: disposable scaffolding and real-authority read-only CLI tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceError,
)
from vscs.infrastructure.production_execution.h3_live_preflight_cli import (
    initialize_disposable_scope,
    run_read_only_preflight,
)
from vscs.infrastructure.production_execution.minimax_h3_automated_execution import (
    MiniMaxH3AutomatedExecutionError,
)


def test_new_acceptance_tree_contains_only_scaffold(tmp_path: Path):
    root = tmp_path / "acceptance"
    project = initialize_disposable_scope(root)
    assert project == root / "project"
    assert (root / ".vscs_h3_disposable_acceptance").read_text(encoding="utf-8") == ("Q3.1.3.5.8")
    assert (project / "acceptance-output").is_dir()
    assert (project / "evidence").is_dir()
    assert not (project / "production").exists()


def test_preexisting_root_cannot_be_initialized_or_overwritten(tmp_path: Path):
    root = tmp_path / "acceptance"
    initialize_disposable_scope(root)
    marker = root / ".vscs_h3_disposable_acceptance"
    with pytest.raises(H3IsolatedAcceptanceError, match="existing"):
        initialize_disposable_scope(root)
    assert marker.read_text(encoding="utf-8") == "Q3.1.3.5.8"


def test_preflight_missing_governed_task_never_submits(tmp_path: Path):
    root = tmp_path / "acceptance"
    initialize_disposable_scope(root)
    input_root = tmp_path / "comfy-input"
    output_root = tmp_path / "comfy-output"
    input_root.mkdir()
    output_root.mkdir()
    with pytest.raises(MiniMaxH3AutomatedExecutionError, match="cannot find ProductionTask"):
        run_read_only_preflight(
            acceptance_root=root,
            task_id="NONEXISTENT-ACCEPTANCE-TASK",
            comfyui_input=input_root,
            comfyui_output=output_root,
        )
    assert tuple(output_root.iterdir()) == ()
    assert tuple((root / "project" / "acceptance-output").iterdir()) == ()
