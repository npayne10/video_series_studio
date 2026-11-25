"""Issue #61 B.2D provider compatibility checks must fail closed offline."""

from vscs.application.caps.multiple_angle_provider_preflight import (
    inspect_provider_compatibility,
)


def _graph() -> dict:
    return {
        "source": {"class_type": "LoadImage", "inputs": {"image": "master.png"}},
        "camera": {
            "class_type": "CameraAngle",
            "inputs": {"image": ["source", 0], "horizontal_angle": 0},
        },
        "out": {"class_type": "SaveImage", "inputs": {"images": ["camera", 0]}},
    }


def _inventory() -> dict:
    return {
        "LoadImage": {
            "input": {"required": {"image": [["master.png"]]}},
            "output": ["IMAGE"],
        },
        "CameraAngle": {
            "input": {
                "required": {
                    "image": ["IMAGE"],
                    "horizontal_angle": ["INT"],
                }
            },
            "output": ["IMAGE", "STRING"],
        },
        "SaveImage": {
            "input": {"required": {"images": ["IMAGE"]}},
            "output": [],
        },
    }


def test_compatible_interfaces_still_block_gpu_execution() -> None:
    report = inspect_provider_compatibility(_graph(), _inventory())
    assert not report.missing_node_types
    assert not report.missing_input_names
    assert not report.invalid_links
    assert not report.unavailable_model_selections
    assert not report.generation_authorized
    assert any("VRAM" in blocker for blocker in report.blockers)
    assert any("approval" in blocker for blocker in report.blockers)


def test_missing_inventory_and_custom_nodes_fail_closed() -> None:
    report = inspect_provider_compatibility(_graph(), None)
    assert "CameraAngle" in report.missing_node_types
    assert any("inventory" in blocker for blocker in report.blockers)
    assert not report.generation_authorized


def test_missing_required_widget_and_missing_source_are_detected() -> None:
    graph = _graph()
    graph["camera"]["inputs"]["unknown_option"] = "bad"
    graph["out"]["inputs"]["images"] = ["absent", 0]
    report = inspect_provider_compatibility(graph, _inventory())
    assert "camera.unknown_option" in report.missing_input_names
    assert report.invalid_links
    assert not report.generation_authorized


def test_output_port_and_model_selection_are_detected() -> None:
    graph = _graph()
    graph["camera"]["inputs"]["image"] = ["source", 1]
    graph["source"]["inputs"]["image"] = "not-installed.png"
    report = inspect_provider_compatibility(graph, _inventory())
    assert report.invalid_links
    assert report.unavailable_model_selections
    assert not report.generation_authorized


def test_empty_and_malformed_graphs_fail_closed() -> None:
    assert not inspect_provider_compatibility({}, _inventory()).generation_authorized
    graph = _graph()
    graph["source"] = {"class_type": "LoadImage", "inputs": []}
    report = inspect_provider_compatibility(graph, _inventory())
    assert report.invalid_links
    assert not report.generation_authorized
