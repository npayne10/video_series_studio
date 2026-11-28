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


def test_incompatible_provider_output_type_is_reported() -> None:
    inventory = _inventory()
    inventory["LoadImage"]["output"] = ["STRING"]
    report = inspect_provider_compatibility(_graph(), inventory)
    assert report.incompatible_link_types == ("camera.image",)
    assert not report.generation_authorized


def _switch_graph() -> dict:
    return {
        "left": {"class_type": "PrimitiveInt", "inputs": {"value": 4}},
        "right": {"class_type": "PrimitiveInt", "inputs": {"value": 40}},
        "select": {
            "class_type": "ComfySwitchNode",
            "inputs": {
                "switch": True,
                "on_false": ["left", 0],
                "on_true": ["right", 0],
            },
        },
        "sink": {"class_type": "IntSink", "inputs": {"value": ["select", 0]}},
    }


def _switch_inventory() -> dict:
    return {
        "PrimitiveInt": {
            "input": {"required": {"value": ["INT"]}},
            "output": ["INT"],
        },
        "PrimitiveFloat": {
            "input": {"required": {"value": ["FLOAT"]}},
            "output": ["FLOAT"],
        },
        "ComfySwitchNode": {
            "input": {
                "required": {
                    "switch": ["BOOLEAN"],
                    "on_false": ["SWITCH_ANY"],
                    "on_true": ["SWITCH_ANY"],
                }
            },
            "output": ["SWITCH_ANY"],
        },
        "IntSink": {
            "input": {"required": {"value": ["INT"]}},
            "output": [],
        },
    }


def test_matching_dynamic_switch_branches_infer_integer_type() -> None:
    report = inspect_provider_compatibility(_switch_graph(), _switch_inventory())
    assert not report.incompatible_link_types
    assert not report.unresolved_switch_types
    assert not report.generation_authorized


def test_mixed_dynamic_switch_branches_fail_closed() -> None:
    graph = _switch_graph()
    graph["right"]["class_type"] = "PrimitiveFloat"
    report = inspect_provider_compatibility(graph, _switch_inventory())
    assert "select" in report.unresolved_switch_types
    assert not report.generation_authorized


def test_missing_dynamic_switch_branch_fails_closed() -> None:
    graph = _switch_graph()
    graph["select"]["inputs"].pop("on_true")
    report = inspect_provider_compatibility(graph, _switch_inventory())
    assert "select" in report.unresolved_switch_types
    assert not report.generation_authorized


def test_cycle_in_dynamic_switch_fails_closed() -> None:
    graph = _switch_graph()
    graph["select"]["inputs"]["on_true"] = ["select", 0]
    report = inspect_provider_compatibility(graph, _switch_inventory())
    assert "select" in report.unresolved_switch_types
    assert not report.generation_authorized


def test_reviewed_master_placeholder_is_unresolved_not_unavailable() -> None:
    graph = _graph()
    graph["1"] = graph.pop("source")
    graph["camera"]["inputs"]["image"] = ["1", 0]
    graph["1"]["inputs"]["image"] = "__VSCS_PENDING_MASTER_BINDING__"
    report = inspect_provider_compatibility(graph, _inventory())
    assert report.unresolved_source_bindings == ("1.image",)
    assert not report.unavailable_model_selections
    assert not report.generation_authorized


def test_other_missing_image_is_still_unavailable() -> None:
    graph = _graph()
    graph["source"]["inputs"]["image"] = "unapproved.png"
    report = inspect_provider_compatibility(graph, _inventory())
    assert report.unavailable_model_selections
    assert not report.generation_authorized
