"""Unit coverage for XCIC Core Rendering Library v1.0."""

from __future__ import annotations

import json
from pathlib import Path

from vscs.infrastructure.xcic_core.compiler import sanitise_api_workflow
from vscs.infrastructure.xcic_core.models import XCICCoreJob
from vscs.infrastructure.xcic_core.queue import XCICCoreQueueWriter


def test_sanitise_api_workflow_removes_notes() -> None:
    graph = {
        "1": {"class_type": "MarkdownNote", "inputs": {}},
        "2": {"class_type": "KSampler", "inputs": {"seed": 4}},
    }
    clean, removed = sanitise_api_workflow(graph)
    assert set(clean) == {"2"}
    assert removed == ("1",)


def test_queue_writer_uses_loader_contract(tmp_path: Path) -> None:
    queue = tmp_path / "queue.json"
    job = XCICCoreJob(
        job_id="job-1",
        asset_id="CAP-SHP-004",
        positive_prompt="A grounded spacecraft",
        negative_prompt="fantasy",
        candidate_directory=tmp_path / "output",
        candidate_filename="candidate.png",
        width=1664,
        height=928,
        seed=4,
    )
    XCICCoreQueueWriter().write(queue, (job,))
    payload = json.loads(queue.read_text(encoding="utf-8"))
    assert payload["job_count"] == 1
    assert payload["jobs"][0]["positive_prompt"] == "A grounded spacecraft"
    assert payload["jobs"][0]["output"]["candidate_filename"] == "candidate.png"
