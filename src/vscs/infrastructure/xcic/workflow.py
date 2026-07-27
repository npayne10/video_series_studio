"""Load and patch XCIC API workflows using an external mapping contract."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from vscs.infrastructure.xcic.models import XCICGenerationJob


class XCICWorkflowError(RuntimeError):
    """Raised when an XCIC API workflow or mapping cannot be applied."""


class XCICWorkflowPatcher:
    """Patch a ComfyUI API workflow without hard-coding node IDs in VSCS."""

    def __init__(self, workflow_path: Path, mapping_path: Path, profile_path: Path) -> None:
        self.workflow_path = workflow_path
        self.mapping_path = mapping_path
        self.profile_path = profile_path

    def build(self, job: XCICGenerationJob) -> dict[str, Any]:
        workflow = self._read_object(self.workflow_path, "workflow")
        mapping = self._read_object(self.mapping_path, "mapping")
        profile = self._read_object(self.profile_path, "profile")
        values: dict[str, Any] = {
            "positive_prompt": job.positive_prompt,
            "negative_prompt": job.negative_prompt,
            "width": job.width,
            "height": job.height,
            "seed": job.seed,
            "steps": job.steps,
            "cfg": job.cfg,
            "directory": str(job.candidate_directory),
            "candidate_directory": str(job.candidate_directory),
            "filename": job.candidate_filename,
            "candidate_filename": job.candidate_filename,
            "enable_turbo_mode": job.enable_turbo_mode,
        }
        values.update(self._profile_values(profile))
        patched = copy.deepcopy(workflow)
        for key, value in values.items():
            target = self._find_target(mapping, key)
            if target is not None:
                self._assign(patched, target[0], target[1], value, key)
        return patched

    @staticmethod
    def _read_object(path: Path, label: str) -> dict[str, Any]:
        resolved = path.expanduser().resolve(strict=False)
        try:
            value = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise XCICWorkflowError(f"Unable to read XCIC {label} {resolved}: {exc}") from exc
        if not isinstance(value, dict):
            raise XCICWorkflowError(f"XCIC {label} must be a JSON object: {resolved}")
        return value

    @staticmethod
    def _profile_values(profile: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for container in (profile, profile.get("models", {}), profile.get("settings", {})):
            if isinstance(container, dict):
                for key, value in container.items():
                    if isinstance(value, (str, int, float, bool)):
                        values.setdefault(str(key), value)
        return values

    @staticmethod
    def _find_target(mapping: dict[str, Any], key: str) -> tuple[str, str] | None:
        candidates = [mapping.get(key)]
        for section_name in ("inputs", "mapping", "nodes", "fields"):
            section = mapping.get(section_name)
            if isinstance(section, dict):
                candidates.append(section.get(key))
        for candidate in candidates:
            if isinstance(candidate, dict):
                node = candidate.get("node_id", candidate.get("node", candidate.get("id")))
                input_name = candidate.get("input", candidate.get("field", candidate.get("name")))
                if node is not None and input_name:
                    return str(node), str(input_name)
            if isinstance(candidate, (list, tuple)) and len(candidate) >= 2:
                return str(candidate[0]), str(candidate[1])
            if isinstance(candidate, str) and "." in candidate:
                node, input_name = candidate.split(".", 1)
                return node, input_name
        return None

    @staticmethod
    def _assign(
        workflow: dict[str, Any], node_id: str, input_name: str, value: Any, key: str
    ) -> None:
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            raise XCICWorkflowError(f"Mapping for '{key}' references missing workflow node {node_id}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise XCICWorkflowError(f"Workflow node {node_id} has no API-format inputs object")
        inputs[input_name] = value
