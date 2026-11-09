"""F4B2: atomic attempt journal prevents duplicate or ambiguous submissions."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps import guided_edit_attempt_journal as journal


def _contract(tmp_path):
    asset = "STORY-LOC-001"
    metadata = tmp_path / "Canonical Assets" / asset / ".metadata"
    metadata.mkdir(parents=True)
    return SimpleNamespace(
        project_root=tmp_path,
        asset_id=asset,
        original_reference_id=12,
        correction_attempt=2,
        evidence_sha256=hashlib.sha256(b"sealed contract").hexdigest(),
        workflow_sha256=hashlib.sha256(b"workflow").hexdigest(),
        verify_seal=Mock(),
    )


def test_reservation_is_exclusive_and_preserves_unknown_outcome(tmp_path):
    contract = _contract(tmp_path)
    reservation = journal.reserve_guided_edit_attempt(contract)
    assert not reservation.execution_authorized
    payload = json.loads(reservation.journal_path.read_text(encoding="utf-8"))
    assert payload["state"] == "RESERVED_OUTCOME_UNKNOWN"
    assert payload["contract_sha256"] == contract.evidence_sha256
    with pytest.raises(journal.GuidedEditAttemptError, match="already reserved"):
        journal.reserve_guided_edit_attempt(contract)
    assert json.loads(reservation.journal_path.read_text(encoding="utf-8")) == payload
    assert contract.verify_seal.call_count == 2


def test_reservation_rejects_invalid_asset_and_attempt(tmp_path):
    contract = _contract(tmp_path)
    contract.asset_id = "../OTHER"
    with pytest.raises(journal.GuidedEditAttemptError, match="identity"):
        journal.reserve_guided_edit_attempt(contract)
    contract.asset_id = "STORY-LOC-001"
    contract.correction_attempt = 3
    with pytest.raises(journal.GuidedEditAttemptError, match="identity"):
        journal.reserve_guided_edit_attempt(contract)


def test_reservation_isolated_by_root_and_correction_attempt(tmp_path):
    contract = _contract(tmp_path)
    first = journal.reserve_guided_edit_attempt(contract)
    contract.original_reference_id = 14
    second = journal.reserve_guided_edit_attempt(contract)
    assert first.journal_path != second.journal_path
    assert first.journal_path.is_file()
    assert second.journal_path.is_file()


def test_missing_cap_metadata_never_reserves(tmp_path):
    contract = _contract(tmp_path)
    metadata = tmp_path / "Canonical Assets" / contract.asset_id / ".metadata"
    metadata.rmdir()
    with pytest.raises(journal.GuidedEditAttemptError, match="missing"):
        journal.reserve_guided_edit_attempt(contract)
