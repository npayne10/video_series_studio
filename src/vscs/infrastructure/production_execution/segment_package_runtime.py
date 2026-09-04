"""Materialize governed provider-segment Production Package derivatives.

The parent Production Package remains the only Shot authority. Segment packages are
provider-execution derivatives that narrow frame count/seed/output identity. Segments
after the first add a separate continuity input while preserving every original
governed LTX Ingredients reference unchanged.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


class SegmentPackageMaterializationError(RuntimeError):
    """Raised when a segmented provider package cannot be derived safely."""


class SegmentPackageMaterializer:
    """Create immutable fingerprinted per-segment package derivatives."""

    ROOT = Path(".vscs") / "provider_executions" / "segments"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)

    def read_parent(self, path: Path) -> dict[str, Any]:
        resolved = Path(path).expanduser().resolve(strict=False)
        if not resolved.is_file():
            raise SegmentPackageMaterializationError(
                f"Production Package does not exist: {resolved}"
            )
        try:
            raw = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SegmentPackageMaterializationError(
                f"Production Package cannot be read as JSON: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise SegmentPackageMaterializationError("Production Package root must be an object")
        plan = raw.get("provider_execution_plan")
        if not isinstance(plan, dict):
            raise SegmentPackageMaterializationError(
                "Production Package has no provider_execution_plan"
            )
        return raw

    def materialize(
        self,
        *,
        parent: dict[str, Any],
        task_id: str,
        segment: dict[str, Any],
        continuity_input_path: str | None = None,
    ) -> Path:
        plan = parent.get("provider_execution_plan")
        if not isinstance(plan, dict) or plan.get("mode") != "segmented":
            raise SegmentPackageMaterializationError(
                "Segment materialization requires a segmented provider execution plan"
            )
        parent_manifest = parent.get("_vscs_manifest")
        if not isinstance(parent_manifest, dict):
            raise SegmentPackageMaterializationError(
                "Production Package has no VSCS compilation manifest"
            )
        parent_fingerprint = str(parent_manifest.get("package_fingerprint") or "").strip()
        if not parent_fingerprint:
            raise SegmentPackageMaterializationError(
                "Production Package manifest has no package_fingerprint"
            )

        segment_id = str(segment.get("segment_id") or "").strip()
        frame_count = _positive_int(segment.get("frame_count"), "segment frame_count")
        seed = _nonnegative_int(segment.get("seed"), "segment seed")
        index = _positive_int(segment.get("index"), "segment index")
        if not segment_id:
            raise SegmentPackageMaterializationError("Segment has no segment_id")
        if index > 1 and not continuity_input_path:
            raise SegmentPackageMaterializationError(
                f"{segment_id} requires the previous segment final frame"
            )

        content = copy.deepcopy(parent)
        content["frame_count"] = frame_count
        content["seed"] = seed

        acpp = content.get("acpp")
        if not isinstance(acpp, dict):
            raise SegmentPackageMaterializationError("Production Package has no ACPP object")
        timing = acpp.get("timing")
        if not isinstance(timing, dict):
            raise SegmentPackageMaterializationError("Production Package ACPP has no timing object")
        timing["frames"] = frame_count
        generation = acpp.get("generation")
        if not isinstance(generation, dict):
            raise SegmentPackageMaterializationError(
                "Production Package ACPP has no generation object"
            )
        generation["seed"] = seed
        output = acpp.get("output")
        if not isinstance(output, dict):
            output = {}
            acpp["output"] = output
        base_prefix = str(output.get("filename_prefix") or task_id).strip() or task_id
        output["filename_prefix"] = f"{base_prefix}/segments/{segment_id}"

        content["provider_segment"] = {
            "schema_version": "1.1",
            "segment_id": segment_id,
            "index": index,
            "start_frame": int(segment.get("start_frame", 0)),
            "end_frame": int(segment.get("end_frame", frame_count - 1)),
            "frame_count": frame_count,
            "seed": seed,
            "parent_package_fingerprint": parent_fingerprint,
            "continuity_input": str(segment.get("continuity_input") or ""),
            "continuity_input_path": continuity_input_path,
        }

        if continuity_input_path is not None:
            self._bind_continuity_input(content, Path(continuity_input_path))

        manifest = content.get("_vscs_manifest")
        assert isinstance(manifest, dict)
        manifest["parent_package_fingerprint"] = parent_fingerprint
        manifest["provider_segment_id"] = segment_id
        payload = dict(content)
        payload.pop("_vscs_manifest", None)
        segment_fingerprint = _fingerprint(payload)
        manifest["package_fingerprint"] = segment_fingerprint

        directory = self._package_directory(task_id, parent_fingerprint) / "packages"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{segment_id}-{segment_fingerprint[:12].upper()}.json"
        if path.is_file():
            return path
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def _bind_continuity_input(self, content: dict[str, Any], path: Path) -> None:
        resolved = path.expanduser().resolve(strict=False)
        if not resolved.is_file():
            raise SegmentPackageMaterializationError(
                f"Segment continuity frame does not exist: {resolved}"
            )
        checksum = hashlib.sha256(resolved.read_bytes()).hexdigest()
        plan = content.get("reference_plan")
        if not isinstance(plan, dict):
            raise SegmentPackageMaterializationError(
                "Segment continuity requires a provider ReferencePlan"
            )
        multi = plan.get("provider_multi_reference")
        if not isinstance(multi, dict) or multi.get("mode") != "ltx_ingredients_iclora":
            raise SegmentPackageMaterializationError(
                "Segment continuity requires the LTX Ingredients multi-reference contract"
            )
        references = multi.get("references")
        if not isinstance(references, list) or not references:
            raise SegmentPackageMaterializationError(
                "LTX Ingredients multi-reference contract has no governed references"
            )

        multi["continuity"] = {
            "role": "previous_segment_final_frame",
            "path": str(resolved),
            "file_checksum": checksum,
            "reference_fingerprint": checksum,
            "provider_ready": True,
        }

    def _package_directory(self, task_id: str, package_fingerprint: str) -> Path:
        identity = hashlib.sha256(f"{task_id}:{package_fingerprint}".encode()).hexdigest()[:16]
        return self.project_directory / self.ROOT / task_id / identity


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SegmentPackageMaterializationError(f"{label} must be a positive integer")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise SegmentPackageMaterializationError(f"{label} must be a non-negative integer")
    return value


def _fingerprint(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()
