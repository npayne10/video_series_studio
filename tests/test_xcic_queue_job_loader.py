"""B.5.26 XCIC custom-node contract shared with VSCS queue writer."""

import importlib.util
import json
from pathlib import Path

import pytest

from vscs.infrastructure.xcic_core.models import XCICCoreJob
from vscs.infrastructure.xcic_core.queue import XCICCoreQueueWriter

NODE_PATH = (
    Path(__file__).resolve().parents[1] / "custom_nodes" / "vscs_xcic" / "xcic_queue_loader.py"
)
spec = importlib.util.spec_from_file_location("vscs_xcic_queue_loader_test", NODE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
XCICQueueJobLoader = module.XCICQueueJobLoader


def _queue(tmp_path: Path, *, index: int = 0) -> Path:
    path = tmp_path / "xcic_generation_queue.json"
    jobs = (
        XCICCoreJob(
            job_id="job-1",
            asset_id="STORY-LOC-001",
            positive_prompt="A fixed engineering control room",
            negative_prompt="no invented features",
            candidate_directory=tmp_path / "outputs",
            candidate_filename="candidate.png",
            width=1280,
            height=720,
            seed=42,
            steps=4,
            cfg=1.0,
            quality_mode="standard",
        ),
        XCICCoreJob(
            job_id="job-2",
            asset_id="STORY-LOC-001",
            positive_prompt="Alternative reviewed reference view",
            negative_prompt="no changed geometry",
            candidate_directory=tmp_path / "outputs2",
            candidate_filename="candidate2.png",
            width=1024,
            height=1024,
            seed=43,
            steps=8,
            cfg=2.0,
            quality_mode="standard",
        ),
    )
    XCICCoreQueueWriter().write(path, jobs)
    return path


def test_loader_contract_matches_workflow_output_indices(tmp_path):
    path = _queue(tmp_path)
    result = XCICQueueJobLoader.load_job(str(path), 0, "standard")
    assert result == (
        "A fixed engineering control room",
        "no invented features",
        1280,
        720,
        42,
        4,
        1.0,
        str(tmp_path / "outputs"),
        "candidate.png",
    )
    assert len(XCICQueueJobLoader.RETURN_TYPES) == 9
    assert XCICQueueJobLoader.RETURN_TYPES == (
        "STRING",
        "STRING",
        "INT",
        "INT",
        "INT",
        "INT",
        "FLOAT",
        "STRING",
        "STRING",
    )
    assert "quality_mode" in XCICQueueJobLoader.INPUT_TYPES()["required"]


def test_loader_selects_indexed_job(tmp_path):
    path = _queue(tmp_path)
    result = XCICQueueJobLoader.load_job(str(path), 1)
    assert result[0] == "Alternative reviewed reference view"
    assert result[4] == 43
    assert result[8] == "candidate2.png"


@pytest.mark.parametrize("index", [-1, 2])
def test_loader_rejects_out_of_range_job(tmp_path, index):
    path = _queue(tmp_path)
    with pytest.raises(ValueError, match="out of range"):
        XCICQueueJobLoader.load_job(str(path), index)


def test_loader_rejects_wrong_schema(tmp_path):
    path = _queue(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = "0.1"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        XCICQueueJobLoader.load_job(str(path), 0)


def test_loader_rejects_wrong_quality_mode(tmp_path):
    path = _queue(tmp_path)
    with pytest.raises(ValueError, match="quality_mode differs"):
        XCICQueueJobLoader.load_job(str(path), 0, "quality")


def test_loader_rejects_path_traversal_in_filename(tmp_path):
    path = _queue(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["jobs"][0]["output"]["candidate_filename"] = "../unsafe.png"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="safe PNG filename"):
        XCICQueueJobLoader.load_job(str(path), 0)


def test_loader_rejects_invalid_dimensions(tmp_path):
    path = _queue(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["jobs"][0]["width"] = -1
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="width"):
        XCICQueueJobLoader.load_job(str(path), 0)


def test_loader_rejects_job_count_mismatch(tmp_path):
    path = _queue(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["job_count"] = 100
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="job_count"):
        XCICQueueJobLoader.load_job(str(path), 0)
