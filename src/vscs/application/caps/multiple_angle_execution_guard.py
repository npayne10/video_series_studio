"""Issue #61 B.2F: offline-only, crash-auditable qualification staging.

No ComfyUI transport or generation entry point exists in this module.
Staging requires an explicit opt-in and is never production authorisation.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
)
from vscs.application.caps.multiple_angle_runtime_readiness import (
    MultipleAngleRuntimeReadiness,
    _contained_path,
)
from vscs.domain.caps import CanonicalReferenceLifecycle


@dataclass(frozen=True)
class OfflineQualificationStaging:
    qualification_id: str
    queue_path: Path
    manifest_path: Path
    reservation_path: Path
    output_path: Path
    queue_sha256: str
    state: str

    @property
    def generation_authorized(self) -> bool:
        return False


def _fresh_master(
    service: DerivedReferenceGenerationService, plan: MultipleAngleRuntimeReadiness
) -> Path:
    project, entries, master, _record, path = service._resolve_locked_master(plan.asset_id)
    if not path.resolve(strict=False).is_relative_to(project.resolve(strict=False)):
        raise DerivedReferenceGenerationError("MASTER source escapes project boundary")
    if master.reference_id != plan.master_reference_id:
        raise DerivedReferenceGenerationError("MASTER authority changed since readiness")
    if hashlib.sha256(path.read_bytes()).hexdigest() != plan.master_sha256:
        raise DerivedReferenceGenerationError("MASTER image changed since readiness")
    if any(
        entry.view == plan.view
        and entry.lifecycle
        not in {
            CanonicalReferenceLifecycle.ARCHIVED,
            CanonicalReferenceLifecycle.REJECTED,
        }
        for entry in entries
    ):
        raise DerivedReferenceGenerationError("Active view conflicts with staged qualification")
    return path


def _exclusive_json(path: Path, payload: dict[str, Any]) -> str:
    """Create only new files; fsync before allowing the next staged record."""
    data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return hashlib.sha256(data).hexdigest()


def _paths(plan: MultipleAngleRuntimeReadiness, project: Path) -> tuple[Path, Path, Path]:
    queue = _contained_path(project, plan.queue_path)
    output = _contained_path(project, plan.output_path)
    if queue.name != f"multiple_angle_{plan.qualification_id}.json":
        raise DerivedReferenceGenerationError("Unrecognised qualification queue filename")
    if not output.name.endswith(f"_qualification_{plan.qualification_id}.png"):
        raise DerivedReferenceGenerationError("Unrecognised qualification output filename")
    manifest = _contained_path(project, queue.with_suffix(".manifest.json"))
    reservation = _contained_path(project, queue.with_suffix(".reservation.json"))
    return manifest, reservation, output


def stage_offline_qualification(
    service: DerivedReferenceGenerationService,
    plan: MultipleAngleRuntimeReadiness,
    *,
    allow_offline_staging: bool = False,
) -> OfflineQualificationStaging:
    """Persist audit-only queue evidence, never submit it to any provider."""
    if not allow_offline_staging:
        raise DerivedReferenceGenerationError("Explicit offline staging consent is required")
    project, _entries, _master, _record, _path = service._resolve_locked_master(
        plan.asset_id
    )
    project = project.resolve(strict=False)
    master_path = _fresh_master(service, plan)
    queue = _contained_path(project, plan.queue_path)
    manifest, reservation, output = _paths(plan, project)
    if (
        queue.exists()
        or manifest.exists()
        or reservation.exists()
        or output.exists()
    ):
        raise DerivedReferenceGenerationError("Qualification queue/output collision")
    job = plan.proposed_queue["jobs"][0]
    if (
        job.get("qualification_id") != plan.qualification_id
        or job.get("master_sha256") != plan.master_sha256
        or job.get("reference_inputs") != [str(master_path)]
        or job.get("output", {}).get("candidate_filename") != output.name
        or job.get("output", {}).get("candidate_directory") != str(output.parent)
        or plan.proposed_graph["1"]["inputs"]["queue_file"] != str(queue)
    ):
        raise DerivedReferenceGenerationError("Proposed queue does not match MASTER binding")

    queue.parent.mkdir(parents=True, exist_ok=True)
    # Re-evaluate the container and MASTER after filesystem staging setup.
    queue = _contained_path(project, queue)
    manifest, reservation, output = _paths(plan, project)
    _fresh_master(service, plan)
    created: list[Path] = []
    try:
        _exclusive_json(
            reservation,
            {
                "qualification_id": plan.qualification_id,
                "output_path": str(output),
                "state": "reserved_offline",
            },
        )
        created.append(reservation)
        queue_hash = _exclusive_json(queue, plan.proposed_queue)
        created.append(queue)
        _exclusive_json(
            manifest,
            {
                "qualification_id": plan.qualification_id,
                "asset_id": plan.asset_id,
                "view": plan.view.value,
                "master_reference_id": plan.master_reference_id,
                "master_sha256": plan.master_sha256,
                "queue_sha256": queue_hash,
                "queue_path": str(queue),
                "output_path": str(output),
                "state": "staged_offline_unsubmitted",
                "generation_authorized": False,
            },
        )
        created.append(manifest)
    except BaseException:
        # Roll back only paths that this invocation created.
        for created_path in reversed(created):
            created_path.unlink(missing_ok=True)
        raise
    return OfflineQualificationStaging(
        qualification_id=plan.qualification_id,
        queue_path=queue,
        manifest_path=manifest,
        reservation_path=reservation,
        output_path=output,
        queue_sha256=queue_hash,
        state="staged_offline_unsubmitted",
    )


def inspect_offline_qualification(
    staged: OfflineQualificationStaging,
) -> tuple[str, tuple[str, ...]]:
    """Read-only restart/recovery inspection; never trust a missing manifest."""
    errors: list[str] = []
    try:
        manifest = json.loads(staged.manifest_path.read_text(encoding="utf-8"))
        reservation = json.loads(staged.reservation_path.read_text(encoding="utf-8"))
        queue_hash = hashlib.sha256(staged.queue_path.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        return "invalid", (f"Incomplete staging records: {exc}",)
    if (
        manifest.get("qualification_id") != staged.qualification_id
        or reservation.get("qualification_id") != staged.qualification_id
        or manifest.get("queue_sha256") != queue_hash
        or staged.queue_sha256 != queue_hash
        or manifest.get("state") != "staged_offline_unsubmitted"
        or manifest.get("queue_path") != str(staged.queue_path)
        or manifest.get("output_path") != str(staged.output_path)
        or reservation.get("output_path") != str(staged.output_path)
    ):
        errors.append("Qualification provenance or queue digest mismatch")
    if staged.output_path.exists():
        errors.append("Output exists without governed provider reconciliation")
    if staged.manifest_path.with_suffix(".cancelled.json").exists():
        return "cancelled", tuple(errors)
    return ("invalid" if errors else "staged_offline_unsubmitted"), tuple(errors)


def cancel_offline_qualification(staged: OfflineQualificationStaging) -> Path:
    """Append a cancellation record; preserve immutable queue and history."""
    status, errors = inspect_offline_qualification(staged)
    if status != "staged_offline_unsubmitted" or errors:
        raise DerivedReferenceGenerationError("Qualification cannot be cancelled safely")
    cancellation = staged.manifest_path.with_suffix(".cancelled.json")
    _exclusive_json(
        cancellation,
        {
            "qualification_id": staged.qualification_id,
            "queue_sha256": staged.queue_sha256,
            "state": "cancelled_without_submission",
        },
    )
    return cancellation
