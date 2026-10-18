"""Checkpoint 2: immutable, validated replacement-decision evidence."""

import json
from unittest.mock import Mock

import pytest

from vscs.application.episode_timeline_revision_management import (
    prepare_successor_revision,
    publish_successor_revision,
)
from vscs.infrastructure.assembly_replacement_decisions import (
    JsonReplacementDecisionRepository,
    ReplacementDecision,
    ReplacementDecisionError,
)
from test_phase_20_18_2_3_7_4_timeline_successor import (
    _authority,
    _previous,
    _selection,
)


def _case():
    predecessor = _previous()
    candidate = prepare_successor_revision(
        predecessor,
        revision_id="REV-002",
        authority=_authority(),
        replacements=(_selection("SHT-001", "GM-NEW"),),
        replacement_reason="New approved source footage",
    )
    decision = ReplacementDecision(
        decision_id="RD-001",
        assembly_id=predecessor.assembly_id,
        predecessor_revision_id=predecessor.revision_id,
        successor_revision_id=candidate.revision_id,
        predecessor_fingerprint=predecessor.fingerprint,
        successor_fingerprint=candidate.fingerprint,
        shot_id="SHT-001",
        previous_selection=predecessor.selections[0],
        replacement_selection=candidate.selections[0],
        operator_id="TEST-OPERATOR",
        justification="New source was reviewed and approved",
    )
    return predecessor, candidate, decision


def test_persisted_decision_round_trip_is_immutable(tmp_path):
    _, _, decision = _case()
    repository = JsonReplacementDecisionRepository(tmp_path)
    path = repository.create(decision)
    assert repository.get("RD-001") == decision
    with pytest.raises(ReplacementDecisionError, match="already exists"):
        repository.create(decision)
    assert path.exists()


def test_tampered_decision_rejected(tmp_path):
    _, _, decision = _case()
    repository = JsonReplacementDecisionRepository(tmp_path)
    path = repository.create(decision)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["decision"]["justification"] = "Altered without checksum update"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(ReplacementDecisionError, match="invalid"):
        repository.get("RD-001")


def test_replacement_publication_requires_matching_persisted_decision(tmp_path):
    predecessor, candidate, decision = _case()
    repository = JsonReplacementDecisionRepository(tmp_path)
    repository.create(decision)
    timeline = Mock()
    timeline.get.return_value = predecessor
    validator = Mock()
    validator.validate.return_value.allowed = True
    validator.validate.return_value.blockers = ()
    publish_successor_revision(
        candidate,
        repository=timeline,
        validator=validator,
        authority=_authority(),
        expected_predecessor_fingerprint=predecessor.fingerprint,
        decision_repository=repository,
        replacement_decision_ids=("RD-001",),
    )
    timeline.create.assert_called_once_with(candidate)
    timeline.create.reset_mock()
    with pytest.raises(ValueError, match="persisted replacement decisions"):
        publish_successor_revision(
            candidate,
            repository=timeline,
            validator=validator,
            authority=_authority(),
            expected_predecessor_fingerprint=predecessor.fingerprint,
        )
    timeline.create.assert_not_called()


def test_unrelated_decision_cannot_authorize_other_successor(tmp_path):
    predecessor, candidate, decision = _case()
    decisions = JsonReplacementDecisionRepository(tmp_path)
    decisions.create(decision)
    changed_candidate = prepare_successor_revision(
        predecessor,
        revision_id="REV-003",
        authority=_authority(),
        replacements=(_selection("SHT-001", "GM-NEW"),),
        replacement_reason="A separate successor",
    )
    timeline = Mock()
    timeline.get.return_value = predecessor
    with pytest.raises(ValueError, match="does not match revision evidence"):
        publish_successor_revision(
            changed_candidate,
            repository=timeline,
            validator=Mock(),
            authority=_authority(),
            expected_predecessor_fingerprint=predecessor.fingerprint,
            decision_repository=decisions,
            replacement_decision_ids=("RD-001",),
        )
    timeline.create.assert_not_called()
