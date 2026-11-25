"""Issue #61 B.2E: governed, non-executable multiple-angle runtime readiness.

This plans source/queue/output binding in memory. It never creates directories,
queues a ComfyUI prompt, writes candidates or authorises GPU execution.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
)
from vscs.application.caps.multiple_angle_binding import (
    MultipleAngleOfflineCompiler,
    MultipleAnglePreflight,
)
from vscs.application.caps.multiple_angle_provider_preflight import (
    ProviderCompatibilityPreflight,
    inspect_provider_compatibility,
)
from vscs.domain.caps import CanonicalReferenceLifecycle, CanonicalReferenceView


@dataclass(frozen=True)
class MultipleAngleRuntimeReadiness:
    asset_id: str
    view: CanonicalReferenceView
    master_reference_id: str
    master_sha256: str
    qualification_id: str
    queue_path: Path
    output_path: Path
    proposed_graph: dict[str, Any]
    proposed_queue: dict[str, Any]
    provider_preflight: ProviderCompatibilityPreflight | None
    blockers: tuple[str, ...]

    @property
    def generation_authorized(self) -> bool:
        return False


def _contained_path(project: Path, candidate: Path) -> Path:
    """Reject symlink escapes before any path can become a future write target."""
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(project.resolve(strict=False)):
        raise DerivedReferenceGenerationError("Qualification path escapes project boundary")
    return resolved


def plan_multiple_angle_runtime(
    service: DerivedReferenceGenerationService,
    asset_id: str,
    view: CanonicalReferenceView,
    *,
    seed: int,
    qualification_id: str | None = None,
    object_info: dict[str, Any] | None = None,
    model_root: Path | None = None,
) -> MultipleAngleRuntimeReadiness:
    """Produce a scoped proposal, with no queue/output file or GPU side effects."""
    project, entries, master, _record, master_path = service._resolve_locked_master(
        asset_id
    )
    if not master_path.resolve(strict=False).is_relative_to(project.resolve(strict=False)):
        raise DerivedReferenceGenerationError("MASTER path escapes project boundary")
    active = {
        entry.view
        for entry in entries
        if entry.lifecycle
        not in {
            CanonicalReferenceLifecycle.ARCHIVED,
            CanonicalReferenceLifecycle.REJECTED,
        }
    }
    if view in active:
        raise DerivedReferenceGenerationError(
            "An active reference already exists for the requested view"
        )
    if qualification_id is None:
        qualification_id = uuid4().hex
    if (
        not qualification_id
        or len(qualification_id) != 32
        or any(ch not in "0123456789abcdef" for ch in qualification_id)
    ):
        raise DerivedReferenceGenerationError("Qualification ID must be 32 lowercase hex digits")

    before_hash = hashlib.sha256(master_path.read_bytes()).hexdigest()
    compiled: MultipleAnglePreflight = MultipleAngleOfflineCompiler(service).compile(
        asset_id,
        view,
        seed=seed,
        object_info=object_info,
        model_root=model_root,
    )
    _project_now, _entries_now, master_now, _record_now, master_path_now = (
        service._resolve_locked_master(asset_id)
    )
    after_hash = hashlib.sha256(master_path_now.read_bytes()).hexdigest()
    if (
        before_hash != compiled.master_sha256
        or before_hash != after_hash
        or master.reference_id != master_now.reference_id
        or master_path != master_path_now
    ):
        raise DerivedReferenceGenerationError(
            "MASTER changed during readiness compilation; restart qualification"
        )

    project_root = project.resolve(strict=False)
    asset = asset_id.upper()
    queue_path = _contained_path(
        project_root,
        project_root
        / ".vscs"
        / "runtime"
        / "comfyui"
        / "queues"
        / f"multiple_angle_{qualification_id}.json",
    )
    output_path = _contained_path(
        project_root,
        project_root
        / "Canonical Assets"
        / asset
        / "Images"
        / "Derived"
        / f"{view.value}_qualification_{qualification_id}.png",
    )
    if queue_path.exists() or output_path.exists():
        raise DerivedReferenceGenerationError(
            "Qualification staging collision: queue or output already exists"
        )

    graph = deepcopy(compiled.compiled_graph)
    queue = deepcopy(compiled.queue_payload)
    graph["1"]["inputs"]["queue_file"] = str(queue_path)
    graph["2"]["inputs"]["filename_prefix"] = (
        f"VSCS_QUALIFICATION_{qualification_id}"
    )
    job = queue["jobs"][0]
    job["output"]["candidate_directory"] = str(output_path.parent)
    job["output"]["candidate_filename"] = output_path.name
    job["qualification_id"] = qualification_id
    job["master_sha256"] = before_hash
    job["master_reference_id"] = master.reference_id

    provider_report = (
        inspect_provider_compatibility(graph, object_info)
        if object_info is not None
        else None
    )
    blockers = list(compiled.blockers)
    if provider_report is None:
        blockers.append("Compiled runtime graph has not been checked against node inventory")
    else:
        blockers.extend(provider_report.blockers)
    blockers.extend(
        (
            "Queue-file materialization and atomic no-overwrite reservation are unimplemented",
            "Provider output validation, unique staging and rollback are unimplemented",
            "Just-in-time MASTER authority/hash verification at submission is required",
            "ComfyUI runtime loader/CameraAngle binding is not empirically qualified",
            "16 GiB GPU VRAM budget and deterministic camera orientation are unqualified",
            "A separately authorised isolated GPU trial and human QC are required",
        )
    )
    return MultipleAngleRuntimeReadiness(
        asset_id=asset,
        view=view,
        master_reference_id=master.reference_id,
        master_sha256=before_hash,
        qualification_id=qualification_id,
        queue_path=queue_path,
        output_path=output_path,
        proposed_graph=graph,
        proposed_queue=queue,
        provider_preflight=provider_report,
        blockers=tuple(dict.fromkeys(blockers)),
    )
