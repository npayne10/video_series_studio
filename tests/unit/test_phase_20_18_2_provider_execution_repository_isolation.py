"""Regression coverage for provider execution runtime-file isolation."""

from __future__ import annotations

import json

import pytest

from vscs.application.provider_execution import DurableExecutionJobRepositoryError
from vscs.infrastructure.provider_execution import JsonDurableExecutionJobRepository


def test_repository_ignores_sibling_runtime_metadata(tmp_path) -> None:
    root = tmp_path / "provider_executions"
    root.mkdir()
    (root / "hardware_capability.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "provider_id": "LOCAL-COMFYUI-01",
                "capabilities": ["video_generation"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    repository = JsonDurableExecutionJobRepository(root)

    assert repository.list_active() == ()
    assert repository.list_for_task("PT-001") == ()


def test_repository_keeps_pex_execution_documents_strict(tmp_path) -> None:
    root = tmp_path / "provider_executions"
    root.mkdir()
    (root / "PEX-BROKEN-A001.json").write_text(
        json.dumps({"schema_version": "1.0", "not_execution_job": {}}) + "\n",
        encoding="utf-8",
    )

    repository = JsonDurableExecutionJobRepository(root)

    with pytest.raises(DurableExecutionJobRepositoryError, match="execution_job"):
        repository.list_active()
