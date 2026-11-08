"""B.5.26F read-only spatial guidance inventory and safety regression."""

import json

from vscs.application.caps.spatial_candidate_guidance import inspect_spatial_guidance
from vscs.infrastructure.xcic.config import XCICConfiguration


def _config(tmp_path, workflow):
    path = tmp_path / "workflow.json"
    if workflow is not None:
        path.write_text(json.dumps(workflow), encoding="utf-8")
    return XCICConfiguration(
        installation_root=tmp_path,
        comfyui_url="http://127.0.0.1:8188",
        text_workflow_path=path,
        text_mapping_path=tmp_path / "mapping.json",
        text_profile_path=tmp_path / "profile.json",
    )


def test_text_to_image_workflow_is_not_mistaken_for_guided_edit(tmp_path):
    config = _config(
        tmp_path,
        {
            "1": {"class_type": "XCICQueueJobLoader", "inputs": {"job_index": 0}},
            "2": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 1280}},
            "3": {"class_type": "KSampler", "inputs": {"latent_image": ["2", 0]}},
        },
    )
    report = inspect_spatial_guidance(config)
    assert report.workflow_available
    assert report.loader_count == 1
    assert not report.guided_execution_verified
    assert not report.image_nodes
    assert not report.mask_nodes
    assert not report.control_nodes
    assert "No ComfyUI request" in report.describe()


def test_unavailable_workflow_fails_closed_without_creating_files(tmp_path):
    config = _config(tmp_path, None)
    report = inspect_spatial_guidance(config)
    assert not report.workflow_available
    assert not report.guided_execution_verified
    assert "Cannot read local XCIC workflow" in report.describe()
    assert not config.text_workflow_path.exists()


def test_possible_guidance_nodes_do_not_imply_executable_edit(tmp_path):
    config = _config(
        tmp_path,
        {
            "1": {"class_type": "XCICQueueJobLoader", "inputs": {}},
            "2": {"class_type": "LoadImage", "inputs": {"image": "source.png"}},
            "3": {"class_type": "LoadImageMask", "inputs": {"mask": "mask.png"}},
            "4": {"class_type": "ControlNetApplyAdvanced", "inputs": {"image": ["2", 0]}},
        },
    )
    report = inspect_spatial_guidance(config)
    assert report.image_nodes
    assert report.mask_nodes
    assert report.control_nodes
    assert not report.guided_execution_verified
    assert any("connected paths" in blocker for blocker in report.blockers)


def test_untrusted_workflow_structure_does_not_claim_readiness(tmp_path):
    config = _config(tmp_path, {"nodes": [{"type": "LoadImage"}]})
    report = inspect_spatial_guidance(config)
    assert not report.workflow_available
    assert not report.guided_execution_verified
    assert any("UI format" in blocker for blocker in report.blockers)
