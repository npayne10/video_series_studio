"""F4B2: durable, fail-closed once-only local image-edit submission journal.

An exclusive atomic reservation is created BEFORE an external submission.
Unknown outcomes are never retried automatically. This module does not
communicate with ComfyUI and does not mark any CAP Candidate approved.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.spatial_correction_contract import SpatialCorrectionContract

_SAFE_ASSET = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class GuidedEditAttemptError(RuntimeError):
    """An attempt is reserved, stale, ambiguous or otherwise unsafe."""


@dataclass(frozen=True, slots=True)
class GuidedEditAttemptReservation:
    """Durable reservation, not permission to run a provider."""

    journal_path: Path
    contract_sha256: str
    original_reference_id: int
    correction_attempt: int

    @property
    def execution_authorized(self) -> bool:
        return False


def reserve_guided_edit_attempt(
    contract: SpatialCorrectionContract,
) -> GuidedEditAttemptReservation:
    """Create a unique attempt journal, refusing all duplicate reservations."""
    contract.verify_seal()
    if (
        not _SAFE_ASSET.fullmatch(contract.asset_id)
        or not _SHA256.fullmatch(contract.evidence_sha256)
        or type(contract.original_reference_id) is not int
        or contract.original_reference_id < 1
        or type(contract.correction_attempt) is not int
        or not 1 <= contract.correction_attempt <= 2
    ):
        raise GuidedEditAttemptError("Invalid guided-edit attempt identity")
    project = contract.project_root.resolve(strict=True)
    expected = project / "Canonical Assets" / contract.asset_id / ".metadata"
    if not expected.is_dir() or expected.is_symlink():
        raise GuidedEditAttemptError("Trusted CAP metadata directory is missing")
    journal_root = expected / "guided_edit_attempts"
    if journal_root.is_symlink():
        raise GuidedEditAttemptError("Guided-edit journal directory must not be a symlink")
    journal_root.mkdir(exist_ok=True)
    if journal_root.resolve(strict=True).parent != expected.resolve(strict=True):
        raise GuidedEditAttemptError("Guided-edit journal escaped CAP metadata")
    filename = (
        f"root_{contract.original_reference_id}_attempt_{contract.correction_attempt}.json"
    )
    path = journal_root / filename
    payload = {
        "schema_version": 1,
        "governance": "reserved_no_automatic_retry",
        "asset_id": contract.asset_id,
        "original_reference_id": contract.original_reference_id,
        "attempt": contract.correction_attempt,
        "contract_sha256": contract.evidence_sha256,
        "workflow_sha256": contract.workflow_sha256,
        "state": "RESERVED_OUTCOME_UNKNOWN",
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise GuidedEditAttemptError(
            "Guided edit attempt is already reserved; reconcile its ComfyUI "
            "history and CAP Candidate before another submission"
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Deliberately keep the attempt reserved after a partial write:
        # ambiguous outcomes must never be eligible for auto-retry.
        raise
    return GuidedEditAttemptReservation(
        journal_path=path,
        contract_sha256=contract.evidence_sha256,
        original_reference_id=contract.original_reference_id,
        correction_attempt=contract.correction_attempt,
    )
