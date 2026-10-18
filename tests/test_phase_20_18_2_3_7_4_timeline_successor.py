"""Phase 20.18.2.3.7.4 immutable Draft successor governance tests."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.assembly_contracts import (
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyTimelineRevision,
    ShotSelection,
)
from vscs.application.episode_shot_set_resolver import EpisodeShotSet
from vscs.application.episode_timeline_revision_management import (
    prepare_successor_revision,
    publish_successor_revision,
)


def _selection(shot: str, media: str, index: int = 0) -> ShotSelection:
    return ShotSelection(
        scene_id="SCN-001",
        shot_id=shot,
        generated_media_id=media,
        media_revision="1",
        file_checksum="a" * 64,
        approval_evidence_ref="HUMAN-QC",
        source_in_frame=0,
        source_out_frame=144,
        sequence_index=index,
        media_state="approved",
    )


def _previous() -> AssemblyTimelineRevision:
    scope = AssemblyScope(
        production_id="PROD-1",
        scope_kind=AssemblyScopeKind.EPISODE,
        scope_id="EP-001",
        declared_shot_set_revision="PS-001",
        story_structure_fingerprint="b" * 64,
    )
    return AssemblyTimelineRevision(
        assembly_id="ASM-EP-001",
        revision_id="REV-001",
        scope=scope,
        selections=(_selection("SHT-001", "GM-1"),),
        frame_rate_num=24,
        frame_rate_den=1,
    )


def _authority() -> EpisodeShotSet:
    return EpisodeShotSet("EP-001", ("SHT-001", "SHT-002"), ())


def test_successor_adds_shot_and_preserves_predecessor_evidence():
    old = _previous()
    next_revision = prepare_successor_revision(
        old, revision_id="REV-002", authority=_authority(),
        additions=(_selection("SHT-002", "GM-2"),),
    )
    assert next_revision.predecessor_revision == "REV-001"
    assert [item.shot_id for item in next_revision.selections] == ["SHT-001", "SHT-002"]
    assert next_revision.selections[0] == old.selections[0]
    assert old.revision_id == "REV-001"


def test_silent_replacement_and_unapproved_additions_block():
    with pytest.raises(ValueError, match="governed replacement"):
        prepare_successor_revision(
            _previous(), revision_id="REV-002", authority=_authority(),
            additions=(_selection("SHT-001", "GM-NEW"),),
        )
    with pytest.raises(ValueError, match="justification"):
        prepare_successor_revision(
            _previous(), revision_id="REV-002", authority=_authority(),
            replacements=(_selection("SHT-001", "GM-NEW"),),
        )
    with pytest.raises(ValueError, match="human-approved"):
        prepare_successor_revision(
            _previous(), revision_id="REV-002", authority=_authority(),
            additions=(replace(_selection("SHT-002", "GM-2"), media_state="generated"),),
        )


def test_successor_publication_requires_current_predecessor_and_media_bytes():
    old = _previous()
    candidate = prepare_successor_revision(
        old, revision_id="REV-002", authority=_authority(),
        additions=(_selection("SHT-002", "GM-2"),),
    )
    repo = Mock()
    repo.get.return_value = old
    validator = Mock()
    validator.validate.return_value = SimpleNamespace(allowed=True, blockers=())
    publish_successor_revision(
        candidate, repository=repo, validator=validator,
        authority=_authority(), expected_predecessor_fingerprint=old.fingerprint,
    )
    repo.create.assert_called_once_with(candidate)
    with pytest.raises(ValueError, match="Predecessor"):
        publish_successor_revision(
            candidate, repository=repo, validator=validator,
            authority=_authority(), expected_predecessor_fingerprint="stale",
        )


def test_replacement_requires_justification_at_publish_boundary():
    old = _previous()
    candidate = prepare_successor_revision(
        old, revision_id="REV-002", authority=_authority(),
        replacements=(_selection("SHT-001", "GM-NEW"),),
        replacement_reason="Operator reviewed new QC evidence",
    )
    repo, validator = Mock(), Mock()
    repo.get.return_value = old
    with pytest.raises(ValueError, match="justification"):
        publish_successor_revision(
            candidate, repository=repo, validator=validator,
            authority=_authority(), expected_predecessor_fingerprint=old.fingerprint,
        )
    repo.create.assert_not_called()
