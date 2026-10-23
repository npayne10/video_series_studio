"""Q3.1.3.5.3 persisted-source to real compiler fail-closed acceptance.

Every filesystem is an isolated pytest tmp_path. No provider or production output runs.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from vscs.infrastructure.production_execution.h3_persisted_authority_gate import (
    verify_persisted_h3_reference_authority,
)
from vscs.infrastructure.production_execution.h3_reference_selection_governance import (
    H3ReferenceGovernanceError,
)

from test_h3_persisted_both_repositories_acceptance import _loader, _write_records


def _verify(tmp_path):
    loader = _loader(tmp_path)
    return verify_persisted_h3_reference_authority(
        reference_root=tmp_path,
        tasks=loader.tasks,
        packages=loader.packages,
        original=SimpleNamespace(
            task_id="TASK-TEST",
            source_package_id="PKG-TEST",
            shot_id="SHT-TEST",
            profile="production",
        ),
        execution=SimpleNamespace(),
        projection=SimpleNamespace(),
    )


def test_real_persisted_sources_reach_real_compiler_and_reject_missing_approval_inputs(
    tmp_path,
):
    task_path, package_path = _write_records(tmp_path)
    before = (task_path.read_bytes(), package_path.read_bytes())
    with pytest.raises(
        H3ReferenceGovernanceError, match="cannot be independently recompiled"
    ) as error:
        _verify(tmp_path)
    assert "Universal Production Description authority is not compiled" in str(
        error.value.__cause__
    )
    assert (task_path.read_bytes(), package_path.read_bytes()) == before


def test_real_compiler_rejects_changed_task_authority_fingerprint(tmp_path):
    task_path, package_path = _write_records(tmp_path)
    raw = json.loads(package_path.read_text(encoding="utf-8"))
    package = raw["production_packages"][0]
    package["validation"] = {
        "universal_description_complete": True,
        "cross_authority_consistent": True,
    }
    package["universal_description"] = {"production": {"universal_text": "Test shot"}}
    package_path.write_text(json.dumps(raw), encoding="utf-8")
    before = (task_path.read_bytes(), package_path.read_bytes())
    with pytest.raises(
        H3ReferenceGovernanceError, match="cannot be independently recompiled"
    ) as error:
        _verify(tmp_path)
    assert "authority fingerprint does not match" in str(error.value.__cause__)
    assert (task_path.read_bytes(), package_path.read_bytes()) == before


def test_persisted_source_replacement_blocks_before_real_recompilation(tmp_path):
    task_path, package_path = _write_records(tmp_path)
    raw = json.loads(package_path.read_text(encoding="utf-8"))
    raw["production_packages"][0]["package_id"] = "REPLACED"
    package_path.write_text(json.dumps(raw), encoding="utf-8")
    before = (task_path.read_bytes(), package_path.read_bytes())
    with pytest.raises(H3ReferenceGovernanceError, match="exactly one"):
        _verify(tmp_path)
    assert (task_path.read_bytes(), package_path.read_bytes()) == before
