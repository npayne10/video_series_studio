"""One-use, operator-authorised GPU qualification and governed output intake.

The CAP generation UI exposes this only as a distinct operator-confirmed trial;
authorization and a qualified ComfyUI environment are required for invocation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from PIL import Image, UnidentifiedImageError

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
)
from vscs.application.caps.multiple_angle_binding import MultipleAngleOfflineCompiler
from vscs.application.caps.multiple_angle_execution_guard import (
    OfflineQualificationStaging,
    _exclusive_json,
    _fresh_master,
    inspect_offline_qualification,
)
from vscs.application.caps.multiple_angle_provider_preflight import (
    inspect_provider_compatibility,
)
from vscs.application.caps.multiple_angle_runtime_readiness import (
    MultipleAngleRuntimeReadiness,
    _contained_path,
)


class QualifiedComfyUIClient(Protocol):
    def object_info(self) -> dict[str, Any]: ...
    def healthcheck(self) -> None: ...
    def submit(self, prompt: dict[str, Any]) -> str: ...
    def wait(self, prompt_id: str, timeout_seconds: float = 3600.0) -> dict[str, Any]: ...
    def fetch_output_image(self, image: dict[str, Any]) -> bytes: ...


@dataclass(frozen=True)
class MultipleAngleExecutionResult:
    qualification_id: str
    prompt_id: str
    output_sha256: str
    reference_record_id: int
    audit_path: Path
    status: str = "candidate_pending_human_qc"

    @property
    def production_approved(self) -> bool:
        return False


def execute_qualified_multiple_angle(
    service: DerivedReferenceGenerationService,
    plan: MultipleAngleRuntimeReadiness,
    staged: OfflineQualificationStaging,
    *,
    client: QualifiedComfyUIClient,
    model_root: Path,
    authorization: str,
    timeout_seconds: float = 3600.0,
) -> MultipleAngleExecutionResult:
    """Submit exactly one staged job; never retry or overwrite after a failure.

    An immutable attempt record is written *before* submission, so an
    interrupted/uncertain operation cannot silently be submitted again.
    """
    if authorization != f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}":
        raise DerivedReferenceGenerationError(
            "Separate qualification-specific GPU authorization required"
        )
    if staged.qualification_id != plan.qualification_id or staged.queue_path != plan.queue_path:
        raise DerivedReferenceGenerationError("Staged qualification does not match readiness")
    state, errors = inspect_offline_qualification(staged)
    if state != "staged_offline_unsubmitted" or errors:
        raise DerivedReferenceGenerationError("Qualification staging is invalid or already used")
    _fresh_master(service, plan)
    compiled = MultipleAngleOfflineCompiler(service).compile(
        plan.asset_id,
        plan.view,
        seed=plan.proposed_queue["jobs"][0]["seed"],
        model_root=model_root,
    )
    if compiled.missing_model_files or not model_root.is_dir():
        raise DerivedReferenceGenerationError("Missing required multiple-angle model files")
    info = client.object_info()
    report = inspect_provider_compatibility(plan.proposed_graph, info)
    if any(
        (
            report.missing_node_types,
            report.missing_input_names,
            report.invalid_links,
            report.incompatible_link_types,
            report.unresolved_switch_types,
            report.unresolved_source_bindings,
            report.unavailable_model_selections,
        )
    ):
        raise DerivedReferenceGenerationError("Live ComfyUI node/model graph compatibility failed")
    queue = json.loads(staged.queue_path.read_text(encoding="utf-8"))
    if queue != plan.proposed_queue:
        raise DerivedReferenceGenerationError("Submitted queue differs from reviewed proposal")
    if staged.output_path.exists():
        raise DerivedReferenceGenerationError("Refusing to overwrite an existing output")
    client.healthcheck()
    _fresh_master(service, plan)
    project = service.references.caps.assets.projects.project_directory
    if project is None:
        raise DerivedReferenceGenerationError("No active project")
    _contained_path(project, staged.output_path).parent.mkdir(parents=True, exist_ok=True)
    if _contained_path(project, staged.output_path) != staged.output_path:
        raise DerivedReferenceGenerationError("Qualification output path changed during staging")
    if staged.output_path.exists():
        raise DerivedReferenceGenerationError("Qualification output collision before submission")
    attempt = staged.queue_path.with_suffix(".submission.json")
    _exclusive_json(
        attempt,
        {
            "qualification_id": plan.qualification_id,
            "master_sha256": plan.master_sha256,
            "queue_sha256": staged.queue_sha256,
            "state": "submission_attempt_reserved",
        },
    )
    # After this point a transport failure is uncertain, never implicitly safe to retry.
    prompt_id = client.submit(plan.proposed_graph)
    receipt = staged.queue_path.with_suffix(".prompt.json")
    _exclusive_json(receipt, {"qualification_id": plan.qualification_id, "prompt_id": prompt_id})
    history = client.wait(prompt_id, timeout_seconds=timeout_seconds)
    if not isinstance(history, dict) or not (
        isinstance(history.get("status"), dict) and history["status"].get("completed") is True
    ):
        raise DerivedReferenceGenerationError("ComfyUI did not confirm successful completion")
    _fresh_master(service, plan)
    outputs = history.get("outputs")
    saved = outputs.get("2") if isinstance(outputs, dict) else None
    images = saved.get("images") if isinstance(saved, dict) else None
    if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
        raise DerivedReferenceGenerationError("Expected exactly one ComfyUI SaveImage output")
    descriptor = images[0]
    filename = descriptor.get("filename")
    if not isinstance(filename, str) or not filename.startswith(
        f"VSCS_QUALIFICATION_{plan.qualification_id}_"
    ):
        raise DerivedReferenceGenerationError("SaveImage filename is not scoped to qualification")
    data = client.fetch_output_image(descriptor)
    if (
        not isinstance(data, bytes)
        or len(data) < 24
        or len(data) > 100 * 1024 * 1024
        or not data.startswith(b"\x89PNG\r\n\x1a\n")
    ):
        raise DerivedReferenceGenerationError("Provider output is not a bounded PNG")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG" or min(image.size) < 64 or max(image.size) > 8192:
                raise DerivedReferenceGenerationError("Qualified PNG dimensions are invalid")
            image.verify()
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise DerivedReferenceGenerationError("ComfyUI returned a corrupt PNG") from exc
    path = staged.output_path
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor_fd = os.open(path, flags, 0o600)
    with os.fdopen(descriptor_fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    digest = hashlib.sha256(data).hexdigest()
    audit = staged.queue_path.with_suffix(".reconciled.json")
    _exclusive_json(
        audit,
        {
            "qualification_id": plan.qualification_id,
            "prompt_id": prompt_id,
            "master_reference_id": plan.master_reference_id,
            "master_sha256": plan.master_sha256,
            "output_sha256": digest,
            "output_path": str(path),
            "state": "output_reconciled_pending_candidate_registration",
        },
    )
    reference_id = service.register_qualified_candidate(
        plan.asset_id,
        plan.view,
        output_path=path,
        master_reference_id=plan.master_reference_id,
        master_sha256=plan.master_sha256,
        qualification_id=plan.qualification_id,
        provider_name="ComfyUI — Qwen Multiple Angles Qualification",
        seed=queue["jobs"][0]["seed"],
    )
    _exclusive_json(
        staged.queue_path.with_suffix(".candidate.json"),
        {
            "qualification_id": plan.qualification_id,
            "reference_record_id": reference_id,
            "output_sha256": digest,
            "state": "candidate_pending_human_qc",
        },
    )
    return MultipleAngleExecutionResult(
        plan.qualification_id, prompt_id, digest, reference_id, audit
    )
