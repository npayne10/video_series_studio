"""Stage B.2D: read-only provider interface and controlled-execution preflight.

Static compatibility evidence is not a successful ComfyUI invocation. This
module never submits prompts or writes project, queue or candidate files.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProviderCompatibilityPreflight:
    checked_nodes: tuple[str, ...]
    missing_node_types: tuple[str, ...]
    missing_input_names: tuple[str, ...]
    invalid_links: tuple[str, ...]
    incompatible_link_types: tuple[str, ...]
    unavailable_model_selections: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def generation_authorized(self) -> bool:
        return False


def inspect_provider_compatibility(
    graph: dict[str, Any],
    object_info: dict[str, Any] | None,
) -> ProviderCompatibilityPreflight:
    """Check graph references and advertised node inputs without execution."""
    missing_types: set[str] = set()
    missing_inputs: set[str] = set()
    bad_links: set[str] = set()
    type_mismatches: set[str] = set()
    unavailable_models: set[str] = set()
    checked: set[str] = set()
    blockers: list[str] = []

    if not isinstance(graph, dict) or not graph:
        return ProviderCompatibilityPreflight(
            (), (), (), (), (), (), ("A nonempty API graph is required",)
        )
    if object_info is None or not isinstance(object_info, dict):
        blockers.append("Saved ComfyUI /object_info inventory is required")
        object_info = {}

    for node_id, node in graph.items():
        if not isinstance(node, dict):
            bad_links.add(f"{node_id}: node is not an object")
            continue
        node_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(node_type, str) or not isinstance(inputs, dict):
            bad_links.add(f"{node_id}: invalid API node declaration")
            continue
        checked.add(node_type)
        definition = object_info.get(node_type)
        if not isinstance(definition, dict):
            missing_types.add(node_type)
        declared: dict[str, Any] = {}
        if isinstance(definition, dict):
            spec = definition.get("input")
            if isinstance(spec, dict):
                for key in ("required", "optional", "hidden"):
                    entry = spec.get(key)
                    if isinstance(entry, dict):
                        declared.update(entry)
            else:
                missing_inputs.add(f"{node_id}: missing provider input schema")

        for input_name, value in inputs.items():
            if isinstance(definition, dict) and input_name not in declared:
                missing_inputs.add(f"{node_id}.{input_name}")
            if isinstance(value, list) and len(value) == 2:
                upstream, port = value
                if isinstance(upstream, str) and isinstance(port, int):
                    source = graph.get(upstream)
                    if not isinstance(source, dict):
                        bad_links.add(f"{node_id}.{input_name}: unknown source {upstream}")
                    else:
                        source_type = source.get("class_type")
                        source_definition = (
                            object_info.get(source_type)
                            if isinstance(source_type, str)
                            else None
                        )
                        if isinstance(source_definition, dict):
                            outputs = source_definition.get("output")
                            if isinstance(outputs, list):
                                if not 0 <= port < len(outputs):
                                    bad_links.add(f"{node_id}.{input_name}: invalid output port")
                                elif input_name in declared:
                                    expected = declared[input_name]
                                    if (
                                        isinstance(expected, list)
                                        and expected
                                        and isinstance(expected[0], str)
                                        and expected[0] != outputs[port]
                                        and expected[0] not in ("*", "ANY")
                                    ):
                                        type_mismatches.add(f"{node_id}.{input_name}")
                    continue
            if input_name in declared and isinstance(value, str):
                option_spec = declared[input_name]
                if (
                    isinstance(option_spec, list)
                    and option_spec
                    and isinstance(option_spec[0], list)
                    and value not in option_spec[0]
                ):
                    unavailable_models.add(f"{node_id}.{input_name}: {value}")

    if missing_types:
        blockers.append("Required provider node classes are unavailable")
    if missing_inputs:
        blockers.append("Provider node input interfaces differ from reviewed graph")
    if bad_links:
        blockers.append("Graph contains invalid references or output ports")
    if type_mismatches:
        blockers.append("Provider link data types are incompatible")
    if unavailable_models:
        blockers.append("Node widget selections are absent from provider inventory")

    # These requirements are never satisfied by static interface inspection.
    blockers.extend(
        (
            "Custom MASTER loader to CameraAngle runtime type compatibility is unverified",
            "Camera azimuth orientation and canonical identity require visual QC",
            "RTX 5060 Ti 16 GB VRAM fit and inference stability are unverified",
            "Governed unique staging, MASTER freshness recheck and output reconciliation "
            "are not implemented",
            "Separate operator approval is required before any GPU qualification",
        )
    )
    return ProviderCompatibilityPreflight(
        checked_nodes=tuple(sorted(checked)),
        missing_node_types=tuple(sorted(missing_types)),
        missing_input_names=tuple(sorted(missing_inputs)),
        invalid_links=tuple(sorted(bad_links)),
        incompatible_link_types=tuple(sorted(type_mismatches)),
        unavailable_model_selections=tuple(sorted(unavailable_models)),
        blockers=tuple(blockers),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline ComfyUI provider compatibility audit")
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--object-info", type=Path, required=True)
    args = parser.parse_args()
    try:
        graph = json.loads(args.workflow.read_text(encoding="utf-8"))
        info = json.loads(args.object_info.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot read supplied evidence: {exc}")
    report = inspect_provider_compatibility(graph, info)
    print(
        json.dumps(
            {
                "checked_nodes": report.checked_nodes,
                "missing_node_types": report.missing_node_types,
                "missing_input_names": report.missing_input_names,
                "invalid_links": report.invalid_links,
                "incompatible_link_types": report.incompatible_link_types,
                "unavailable_model_selections": report.unavailable_model_selections,
                "blockers": report.blockers,
                "generation_authorized": report.generation_authorized,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
