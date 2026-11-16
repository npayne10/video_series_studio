"""F5.4.2 C4A: non-executable, source-bound masked-provider preparation.

This module designs the future C4 consent/validation boundary. It cannot
stage images, submit a prompt, reserve attempts, or register Candidates.
A static graph with mask nodes is *not* evidence of working inference.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
)
from vscs.application.caps.human_reviewed_mask_evidence import (
    prepare_reviewed_mask,
)
from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.persistent_human_review import (
    list_existing_mask_versions,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.application.caps.qwen_mask_aware_qualification import (
    build_experimental_masked_graph,
    validate_experimental_graph,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot

_SHA = re.compile(r"^[a-f0-9]{64}$")
_ACK = "REVIEW ONLY"


@dataclass(frozen=True, slots=True)
class C4ProviderPreparation:
    """Sealed offline evidence; no representation can grant execution."""

    asset_id: str
    reference_id: int
    source_sha256: str
    proposal_sha256: str
    selected_mask_sha256: str | None
    managed_workflow_sha256: str | None
    derived_graph_sha256: str | None
    mask_matches_current_proposal: bool
    mask_node_wiring_validated_offline: bool
    blockers: tuple[str, ...]
    evidence_sha256: str

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def mask_provider_compatibility_verified(self) -> bool:
        return False

    @property
    def pixel_preservation_verified(self) -> bool:
        return False

    @property
    def attempt_reservation_allowed(self) -> bool:
        return False

    @property
    def candidate_registration_allowed(self) -> bool:
        return False

    def verify_seal(self) -> None:
        if not _SHA.fullmatch(self.source_sha256) or not _SHA.fullmatch(self.proposal_sha256):
            raise GeometryCorrectionError("C4A input digest is invalid")
        raw = json.dumps(
            {
                "asset_id": self.asset_id,
                "reference_id": self.reference_id,
                "source": self.source_sha256,
                "proposal": self.proposal_sha256,
                "mask": self.selected_mask_sha256,
                "managed_graph": self.managed_workflow_sha256,
                "derived_graph": self.derived_graph_sha256,
                "mask_current": self.mask_matches_current_proposal,
                "topology": self.mask_node_wiring_validated_offline,
                "blockers": self.blockers,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if hashlib.sha256(raw).hexdigest() != self.evidence_sha256:
            raise GeometryCorrectionError("C4A provider preparation seal mismatch")

    def describe(self) -> str:
        self.verify_seal()
        return "\n".join(
            (
                "F5.4.2 C4A - MASKED CORRECTION PROVIDER CONTRACT PREPARATION",
                "OFFLINE ONLY: NO GENERATION OR ATTEMPT RESERVATION",
                f"Asset: {self.asset_id} | Source Candidate: {self.reference_id}",
                f"Source SHA-256: {self.source_sha256}",
                f"Reviewed C1 SHA-256: {self.proposal_sha256}",
                f"Selected C2 mask SHA-256: {self.selected_mask_sha256 or 'none'}",
                f"Mask bound to current C1: {self.mask_matches_current_proposal}",
                f"Managed workflow SHA-256: {self.managed_workflow_sha256 or 'unavailable'}",
                f"Derived offline masked graph SHA-256: {self.derived_graph_sha256 or 'unavailable'}",
                f"Mask node topology validated offline: {self.mask_node_wiring_validated_offline}",
                f"C4A evidence SHA-256: {self.evidence_sha256}",
                "Provider compatibility: NOT VERIFIED; runtime mask behavior: NOT VERIFIED",
                "Pixel preservation: NOT VERIFIED; 16 GiB GPU execution: NOT VERIFIED",
                "Operator authorization: NOT GRANTED; C4 production: BLOCKED",
                "Blockers:",
                *(f"- {item}" for item in self.blockers),
            )
        )


@dataclass(frozen=True, slots=True)
class C4ConsentPreview:
    """Explicit operator acknowledgement of *review*, never generation consent."""

    preparation_sha256: str
    acknowledgment: str

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def attempt_reservation_allowed(self) -> bool:
        return False


def acknowledge_c4_review(
    preparation: C4ProviderPreparation, *, operator_text: str
) -> C4ConsentPreview:
    """Never upgrade an offline review acknowledgement into production consent."""
    preparation.verify_seal()
    if operator_text != _ACK:
        raise GeometryCorrectionError("Type REVIEW ONLY to acknowledge C4A non-execution")
    return C4ConsentPreview(preparation.evidence_sha256, operator_text)


def prepare_c4_provider_contract(
    snapshot: CandidateQualitySnapshot,
    proposal: GovernedCorrectionProposal,
    *,
    selected_mask_path: Path | None,
    workflow_path: Path | None = None,
) -> C4ProviderPreparation:
    """Strict offline validation with a sealed, non-executable preparation result."""
    proposal.verify_seal()
    if (
        proposal.asset_id != snapshot.asset_id
        or proposal.source_reference_id != snapshot.reference_id
        or proposal.source_sha256 != snapshot.image_sha256
        or proposal.accepted_fields != snapshot.accepted_fields
    ):
        raise GeometryCorrectionError("C4A proposal does not match source/CAP requirements")

    versions = list_existing_mask_versions(snapshot, proposal=proposal)
    selected = next((v for v in versions if v.path == selected_mask_path), None)
    expected = prepare_reviewed_mask(
        proposal,
        source_path=snapshot.image_path,
        reviewer_confirmed_mask=True,
    )
    blockers: list[str] = []
    if selected_mask_path is None:
        blockers.append("A currently reviewed C2 mask must be selected explicitly")
    elif selected is None:
        blockers.append("Selected mask is not a verified saved C2 artifact")
    elif not selected.matches_current_proposal:
        blockers.append("HISTORICAL mask cannot be bound to current C1 proposal")
    elif selected.sha256 != expected.mask_sha256:
        blockers.append("Selected C2 mask differs from deterministic source-bound evidence")

    managed_sha: str | None = None
    derived_sha: str | None = None
    topology_ok = False
    workflow = workflow_path if workflow_path is not None else default_workflow_path()
    try:
        managed = inspect_managed_qwen_edit_workflow(workflow)
        managed_sha = managed.workflow_sha256
        graph = build_experimental_masked_graph(workflow_path=workflow)
        validate_experimental_graph(graph)
        # Never bind an unreviewed source, mask filename or a queue placeholder.
        if (
            graph["F541B_MASK"]["inputs"]["channel"] != "red"
            or graph["F541B_LATENT_MASK"]["inputs"]["mask"] != ["F541B_MASK", 0]
            or graph["170:169"]["inputs"]["latent_image"] != ["F541B_LATENT_MASK", 0]
            or graph["F541B_COMPOSITE"]["inputs"]["destination"] != ["170:160", 0]
            or graph["F541B_COMPOSITE"]["inputs"]["source"] != ["170:158", 0]
            or graph["F541B_COMPOSITE"]["inputs"]["mask"] != ["F541B_MASK", 0]
            or graph["9"]["inputs"]["images"] != ["F541B_COMPOSITE", 0]
        ):
            blockers.append("Experimental mask/source/composite topology changed")
        else:
            derived_sha = hashlib.sha256(
                json.dumps(graph, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            topology_ok = True
    except (KeyError, IndexError, OSError, TypeError, ValueError, RuntimeError) as exc:
        blockers.append(f"Qwen graph topology unavailable: {type(exc).__name__}")

    blockers.extend(
        (
            "The XCIC managed Qwen correction builder rejects governed mask inputs",
            "The experimental graph is not bound to source/mask files for a C4 run",
            "Live ComfyUI node semantics, mask polarity and peak 16 GiB VRAM untested",
            "No post-generation protected-pixel or semantic correctness evidence",
            "C4 consent, isolated output, attempt journal and registration are not implemented",
            "Candidate 4 protected final Attempt 2/2 remains unavailable",
        )
    )
    fields: dict[str, Any] = {
        "asset_id": snapshot.asset_id,
        "reference_id": snapshot.reference_id,
        "source": snapshot.image_sha256,
        "proposal": proposal.proposal_sha256,
        "mask": selected.sha256 if selected is not None else None,
        "managed_graph": managed_sha,
        "derived_graph": derived_sha,
        "mask_current": bool(selected and selected.matches_current_proposal),
        "topology": topology_ok,
        "blockers": tuple(blockers),
    }
    digest = hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return C4ProviderPreparation(
        asset_id=snapshot.asset_id,
        reference_id=snapshot.reference_id,
        source_sha256=snapshot.image_sha256,
        proposal_sha256=proposal.proposal_sha256,
        selected_mask_sha256=fields["mask"],
        managed_workflow_sha256=managed_sha,
        derived_graph_sha256=derived_sha,
        mask_matches_current_proposal=bool(selected and selected.matches_current_proposal),
        mask_node_wiring_validated_offline=topology_ok,
        blockers=tuple(blockers),
        evidence_sha256=digest,
    )


@dataclass(frozen=True, slots=True)
class C4PixelAudit:
    """Read-only output-comparison evidence; never approval or execution authority."""

    source_sha256: str
    mask_sha256: str
    result_sha256: str
    protected_pixels: int
    changed_protected_pixels: int
    editable_pixels: int

    @property
    def protected_pixels_identical(self) -> bool:
        return self.changed_protected_pixels == 0

    @property
    def candidate_registration_allowed(self) -> bool:
        return False


def audit_external_masked_result(
    snapshot: CandidateQualitySnapshot,
    proposal: GovernedCorrectionProposal,
    *,
    selected_mask_path: Path,
    external_result_path: Path,
) -> C4PixelAudit:
    """Audit an existing external PNG without writing anything or approving it.

    Even a zero-difference result is *not* geometry correctness or proof of
    safe provider behavior. This accepts no path under the active project.
    """
    preparation = prepare_c4_provider_contract(
        snapshot, proposal, selected_mask_path=selected_mask_path
    )
    if not preparation.mask_matches_current_proposal:
        raise GeometryCorrectionError("C4A pixel audit requires current C1-matched C2 mask")
    project = snapshot.project_root.resolve(strict=True)
    if (
        external_result_path.is_symlink()
        or not external_result_path.is_file()
        or external_result_path.suffix.lower() != ".png"
    ):
        raise GeometryCorrectionError("C4A audit output must be an existing ordinary PNG")
    result_path = external_result_path.resolve(strict=True)
    if project == result_path or project in result_path.parents:
        raise GeometryCorrectionError("C4A audit must use an external disposable result")

    source_bytes = snapshot.image_path.read_bytes()
    mask_bytes = selected_mask_path.read_bytes()
    output_bytes = result_path.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != snapshot.image_sha256:
        raise GeometryCorrectionError("C4A source digest changed")
    if hashlib.sha256(mask_bytes).hexdigest() != preparation.selected_mask_sha256:
        raise GeometryCorrectionError("C4A mask digest changed")
    try:
        with (
            Image.open(snapshot.image_path) as source,
            Image.open(selected_mask_path) as mask,
            Image.open(result_path) as result,
        ):
            if (
                source.format != "PNG"
                or mask.format != "PNG"
                or result.format != "PNG"
                or source.mode != "RGB"
                or result.mode != "RGB"
                or mask.mode != "L"
                or source.size != mask.size
                or source.size != result.size
            ):
                raise GeometryCorrectionError(
                    "C4A pixel audit requires equal-sized RGB source/output and L mask"
                )
            before = source.tobytes()
            after = result.tobytes()
            selection = mask.tobytes()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise GeometryCorrectionError("C4A PNG evidence cannot be decoded") from exc
    protected_pixels = 0
    changed = 0
    editable = 0
    for pixel, bit in enumerate(selection):
        if bit == 255:
            editable += 1
            continue
        if bit != 0:
            raise GeometryCorrectionError("C4A mask contains non-binary pixel values")
        protected_pixels += 1
        offset = pixel * 3
        if before[offset : offset + 3] != after[offset : offset + 3]:
            changed += 1
    if editable == 0 or protected_pixels == 0:
        raise GeometryCorrectionError("C4A mask must have editable and protected pixels")
    return C4PixelAudit(
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
        mask_sha256=hashlib.sha256(mask_bytes).hexdigest(),
        result_sha256=hashlib.sha256(output_bytes).hexdigest(),
        protected_pixels=protected_pixels,
        changed_protected_pixels=changed,
        editable_pixels=editable,
    )
