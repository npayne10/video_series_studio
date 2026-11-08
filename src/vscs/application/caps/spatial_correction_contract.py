"""B.5.26F F3: sealed, non-executable spatial correction evidence contract.

This is a read-only governance boundary. It does not infer edit-workflow
capability, authorize ComfyUI execution or issue operator consent.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SpatialCorrectionContractError(RuntimeError):
    """Source, edit scope or provider evidence is unsafe or has changed."""


@dataclass(frozen=True, slots=True)
class SpatialCorrectionContract:
    """Immutable evidence bundle; never itself an execution permission."""

    asset_id: str
    source_reference_id: int
    original_reference_id: int
    correction_attempt: int
    project_root: Path
    source_path: Path
    source_sha256: str
    quality_report_path: Path
    quality_report_sha256: str
    specification_fingerprint: str
    review_fingerprint: str
    accepted_fields: tuple[tuple[str, str], ...]
    mask_path: Path | None
    mask_sha256: str | None
    workflow_path: Path
    workflow_sha256: str
    workflow_id: str
    model_identifier: str
    evidence_sha256: str

    @property
    def execution_authorized(self) -> bool:
        """F3 always fails closed: an F4 consent and provider adapter are required."""
        return False

    def _evidence(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "asset_id": self.asset_id,
            "source_reference_id": self.source_reference_id,
            "original_reference_id": self.original_reference_id,
            "correction_attempt": self.correction_attempt,
            "project_root": str(self.project_root),
            "source_path": str(self.source_path),
            "source_sha256": self.source_sha256,
            "quality_report_path": str(self.quality_report_path),
            "quality_report_sha256": self.quality_report_sha256,
            "specification_fingerprint": self.specification_fingerprint,
            "review_fingerprint": self.review_fingerprint,
            "accepted_fields": list(self.accepted_fields),
            "mask_path": str(self.mask_path) if self.mask_path is not None else None,
            "mask_sha256": self.mask_sha256,
            "workflow_path": str(self.workflow_path),
            "workflow_sha256": self.workflow_sha256,
            "workflow_id": self.workflow_id,
            "model_identifier": self.model_identifier,
        }

    def verify_seal(self) -> None:
        expected = _digest(json.dumps(self._evidence(), sort_keys=True).encode("utf-8"))
        if expected != self.evidence_sha256:
            raise SpatialCorrectionContractError("Spatial correction contract seal changed")


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read_hashed(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise SpatialCorrectionContractError(f"Missing or unreadable evidence: {path}") from exc
    return digest.hexdigest()


def _contained_file(path: Path, directory: Path, *, suffix: str) -> Path:
    root = directory.resolve(strict=False)
    resolved = path.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise SpatialCorrectionContractError("Cross-project or escaped evidence path") from exc
    if not relative.parts or resolved.suffix.lower() != suffix or not resolved.is_file():
        raise SpatialCorrectionContractError("Evidence path missing or invalid file type")
    if path.is_symlink():
        raise SpatialCorrectionContractError("Symlink evidence path is not permitted")
    return resolved


def _validated_mask(path: Path, project: Path, asset_id: str, size: tuple[int, int]) -> Path:
    directory = project / "Canonical Assets" / asset_id / ".metadata" / "spatial_masks"
    resolved = _contained_file(path, directory, suffix=".png")
    try:
        with Image.open(resolved) as image:
            if image.format != "PNG" or image.mode != "L" or image.size != size:
                raise SpatialCorrectionContractError(
                    "Mask must be an 8-bit grayscale PNG matching the source dimensions"
                )
            image.verify()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise SpatialCorrectionContractError("Mask is not a valid PNG image") from exc
    return resolved


def _validated_source(plan: CandidateRegenerationPlan, project: Path) -> Path:
    expected = (
        project / "Canonical Assets" / plan.source.asset_id / "Images" / "Visual Candidates"
    )
    path = _contained_file(plan.source.image_path, expected, suffix=".png")
    if _read_hashed(path) != plan.source.image_sha256:
        raise SpatialCorrectionContractError("Source Candidate image hash changed")
    if plan.source.reference_role != "supplementary" or plan.source.reference_status != "candidate":
        raise SpatialCorrectionContractError("Source must remain a supplementary Candidate")
    return path


def _source_size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise SpatialCorrectionContractError("Source Candidate must be PNG")
            size = image.size
            image.verify()
            return size
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise SpatialCorrectionContractError("Source Candidate is not valid PNG") from exc


def prepare_spatial_contract(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    *,
    workflow_path: Path,
    trusted_workflow_directory: Path,
    workflow_id: str,
    model_identifier: str,
    mask_path: Path | None = None,
) -> SpatialCorrectionContract:
    """Build a sealed source/mask/workflow contract; no execution or persistence."""
    service.verify_current(plan)
    project = plan.source.project_root.resolve(strict=False)
    if project != plan.source.project_root or not project.is_dir():
        raise SpatialCorrectionContractError("Active project root is not canonical")
    if not 1 <= plan.attempt <= plan.max_attempts <= 2:
        raise SpatialCorrectionContractError("Invalid bounded correction attempt")
    source = _validated_source(plan, project)
    size = _source_size(source)
    report_dir = project / "Canonical Assets" / plan.source.asset_id / ".metadata" / "evaluation"
    report = _contained_file(plan.report_path, report_dir, suffix=".json")
    if _read_hashed(report) != plan.report_sha256:
        raise SpatialCorrectionContractError("Source semantic report changed")
    if not plan.preparation.ready_for_master_candidate:
        raise SpatialCorrectionContractError("Reviewed CAP is no longer ready")
    if (
        plan.source.specification_fingerprint != plan.preparation.specification_fingerprint
        or plan.source.review_fingerprint != plan.preparation.review_fingerprint
        or plan.source.accepted_fields != plan.preparation.accepted_fields
    ):
        raise SpatialCorrectionContractError("Reviewed CAP authority disagrees with source")
    if not plan.source.accepted_fields:
        raise SpatialCorrectionContractError("No accepted CAP constraints exist")
    if not workflow_id.strip() or not model_identifier.strip():
        raise SpatialCorrectionContractError("Workflow and model identifiers are required")
    workflow = _contained_file(workflow_path, trusted_workflow_directory, suffix=".json")
    try:
        graph = json.loads(workflow.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpatialCorrectionContractError("Editing workflow JSON cannot be read") from exc
    if not isinstance(graph, dict) or not graph or "nodes" in graph:
        raise SpatialCorrectionContractError("Editing workflow must be an API-format graph")
    if not all(
        isinstance(node, dict)
        and isinstance(node.get("class_type"), str)
        and isinstance(node.get("inputs"), dict)
        for node in graph.values()
    ):
        raise SpatialCorrectionContractError("Editing workflow contains malformed nodes")
    mask = (
        _validated_mask(mask_path, project, plan.source.asset_id, size)
        if mask_path is not None
        else None
    )
    mask_hash = _read_hashed(mask) if mask is not None else None
    workflow_hash = _read_hashed(workflow)
    evidence = {
        "schema_version": 1,
        "asset_id": plan.source.asset_id,
        "source_reference_id": plan.source.reference_id,
        "original_reference_id": plan.original_reference_id,
        "correction_attempt": plan.attempt,
        "project_root": str(project),
        "source_path": str(source),
        "source_sha256": plan.source.image_sha256,
        "quality_report_path": str(report),
        "quality_report_sha256": plan.report_sha256,
        "specification_fingerprint": plan.source.specification_fingerprint,
        "review_fingerprint": plan.source.review_fingerprint,
        "accepted_fields": list(plan.source.accepted_fields),
        "mask_path": str(mask) if mask is not None else None,
        "mask_sha256": mask_hash,
        "workflow_path": str(workflow),
        "workflow_sha256": workflow_hash,
        "workflow_id": workflow_id,
        "model_identifier": model_identifier,
    }
    seal = _digest(json.dumps(evidence, sort_keys=True).encode("utf-8"))
    return SpatialCorrectionContract(
        asset_id=plan.source.asset_id,
        source_reference_id=plan.source.reference_id,
        original_reference_id=plan.original_reference_id,
        correction_attempt=plan.attempt,
        project_root=project,
        source_path=source,
        source_sha256=plan.source.image_sha256,
        quality_report_path=report,
        quality_report_sha256=plan.report_sha256,
        specification_fingerprint=plan.source.specification_fingerprint,
        review_fingerprint=plan.source.review_fingerprint,
        accepted_fields=plan.source.accepted_fields,
        mask_path=mask,
        mask_sha256=mask_hash,
        workflow_path=workflow,
        workflow_sha256=workflow_hash,
        workflow_id=workflow_id,
        model_identifier=model_identifier,
        evidence_sha256=seal,
    )


def verify_spatial_contract(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
) -> None:
    """Revalidate all signed-off evidence before any future F4 provider boundary."""
    contract.verify_seal()
    service.verify_current(plan)
    if (
        contract.source_reference_id != plan.source.reference_id
        or contract.original_reference_id != plan.original_reference_id
        or contract.correction_attempt != plan.attempt
        or contract.specification_fingerprint != plan.source.specification_fingerprint
        or contract.review_fingerprint != plan.source.review_fingerprint
        or contract.accepted_fields != plan.source.accepted_fields
    ):
        raise SpatialCorrectionContractError("Correction plan authority changed")
    if _read_hashed(contract.source_path) != contract.source_sha256:
        raise SpatialCorrectionContractError("Source Candidate changed")
    if _read_hashed(contract.quality_report_path) != contract.quality_report_sha256:
        raise SpatialCorrectionContractError("Semantic review report changed")
    if _read_hashed(contract.workflow_path) != contract.workflow_sha256:
        raise SpatialCorrectionContractError("Editing workflow changed")
    if contract.mask_path is not None:
        if contract.mask_sha256 is None:
            raise SpatialCorrectionContractError("Mask hash missing")
        _validated_mask(
            contract.mask_path,
            contract.project_root,
            contract.asset_id,
            _source_size(contract.source_path),
        )
        if _read_hashed(contract.mask_path) != contract.mask_sha256:
            raise SpatialCorrectionContractError("Editing mask changed")
