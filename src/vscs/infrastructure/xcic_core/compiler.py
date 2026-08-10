"""Compile and sanitise ComfyUI workflows for XCIC Core v1.0."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

UUID_TYPE_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
EDITOR_ONLY_NODE_TYPES = {
    "MarkdownNote",
    "Note",
    "Note Plus",
    "PrimitiveNode",
    "Reroute",
    "GetNode",
    "SetNode",
    "Fast Groups Bypasser",
    "Fast Groups Muter",
}


class XCICCoreCompileError(RuntimeError):
    """Raised when an editable workflow cannot become an API graph."""


def _is_editor_only(class_type: Any) -> bool:
    value = str(class_type or "").strip()
    if not value or UUID_TYPE_RE.fullmatch(value):
        return True
    if value in EDITOR_ONLY_NODE_TYPES:
        return True
    normalised = value.lower().replace("_", " ").replace("-", " ")
    return normalised in {
        "markdownnote",
        "markdown note",
        "note",
        "note plus",
        "reroute",
        "primitive node",
        "get node",
        "set node",
    }


def is_api_workflow(data: dict[str, Any]) -> bool:
    return bool(data) and all(
        isinstance(value, dict) and "class_type" in value for value in data.values()
    )


def sanitise_api_workflow(data: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    removed = {
        str(node_id)
        for node_id, node in data.items()
        if not isinstance(node, dict) or _is_editor_only(node.get("class_type"))
    }
    clean = {str(node_id): node for node_id, node in data.items() if str(node_id) not in removed}
    dangling: list[str] = []
    for node_id, node in clean.items():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue
        for name, value in inputs.items():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in removed:
                dangling.append(f"node {node_id} input {name} -> removed editor node {value[0]}")
    if dangling:
        raise XCICCoreCompileError(
            "Workflow contains executable links through editor-only nodes: " + "; ".join(dangling)
        )
    if not clean:
        raise XCICCoreCompileError("No executable nodes remain after workflow sanitisation")
    return clean, tuple(sorted(removed))


def ui_to_api(data: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
    if is_api_workflow(data):
        return sanitise_api_workflow(data)
    nodes = data.get("nodes")
    links = data.get("links", [])
    if not isinstance(nodes, list):
        raise XCICCoreCompileError(
            "Unsupported workflow JSON: expected API graph or ComfyUI UI workflow with nodes"
        )
    link_map = {int(link[0]): link for link in links if isinstance(link, list) and len(link) >= 6}
    skipped = {
        str(node.get("id"))
        for node in nodes
        if isinstance(node, dict) and _is_editor_only(node.get("type"))
    }
    api: dict[str, Any] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id"))
        class_type = node.get("type")
        if not node_id or not class_type or node_id in skipped:
            continue
        inputs: dict[str, Any] = {}
        widget_names: list[str] = []
        for item in node.get("inputs", []):
            if not isinstance(item, dict):
                continue
            if item.get("widget") is not None:
                widget_names.append(str(item.get("name")))
            link_id = item.get("link")
            if link_id is not None and int(link_id) in link_map:
                link = link_map[int(link_id)]
                source_id = str(link[1])
                if source_id in skipped:
                    raise XCICCoreCompileError(
                        f"Node {node_id} input {item.get('name')} is linked through editor-only node {source_id}"
                    )
                inputs[str(item["name"])] = [source_id, int(link[2])]
        for name, value in zip(widget_names, node.get("widgets_values", []), strict=False):
            inputs.setdefault(name, value)
        api[node_id] = {
            "class_type": class_type,
            "inputs": inputs,
            "_meta": {"title": node.get("title") or class_type},
        }
    clean, removed_after = sanitise_api_workflow(api)
    return clean, tuple(sorted(skipped.union(removed_after)))


def compile_workflow(source: Path, target: Path) -> tuple[dict[str, Any], tuple[str, ...]]:
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise XCICCoreCompileError("Workflow JSON must contain an object")
        api, removed = ui_to_api(raw)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(api, indent=2), encoding="utf-8")
        return api, removed
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, XCICCoreCompileError):
            raise
        raise XCICCoreCompileError(f"Workflow compilation failed: {exc}") from exc
