"""Checkpoint 4B.2: partial Drafts cannot fabricate or bypass media authority."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.assembly_contracts import AssemblyScope, AssemblyScopeKind
from vscs.application.episode_draft_selection import (
    approval_evidence_reference,
    approved_media_choices,
    build_partial_draft,
    publish_partial_draft,
)
from vscs.application.episode_shot_set_resolver import EpisodeShotSet


def _media(shot="SHT-001", state="approved"):
    return SimpleNamespace(
        media_id="GM-001",
        kind=SimpleNamespace(value="video"),
        scope=SimpleNamespace(
            shot_id=shot, scene_id="SCN-001", episode_id="EP-001", production_id="PROD-1"
        ),
        state=SimpleNamespace(value=state),
        governance_history=(
            (
                SimpleNamespace(
                    to_state=SimpleNamespace(value="approved"),
                    from_state=SimpleNamespace(value="under_review"),
                    actor="test-operator",
                    reason="QC accepted",
                    occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
                ),
            )
            if state == "approved"
            else ()
        ),
        file=SimpleNamespace(checksum_sha256="a" * 64, size_bytes=100),
        revision=1,
    )


def _scope():
    return AssemblyScope(
        production_id="PROD-1",
        scope_kind=AssemblyScopeKind.EPISODE,
        scope_id="EP-001",
        declared_shot_set_revision="GOVERNED-1",
        story_structure_fingerprint="b" * 64,
    )


def _authority():
    return EpisodeShotSet("EP-001", ("SHT-001", "SHT-002"), ())


def test_choices_exclude_pending_approval():
    choices = approved_media_choices(_authority(), (_media(), _media(state="generated")))
    assert choices[0].eligible
    assert not choices[1].eligible


def test_partial_draft_preserves_missing_shots_without_placeholder_media():
    revision = build_partial_draft(
        _authority(),
        _scope(),
        "ASM-1",
        "REV-1",
        (("SHT-001", (media := _media()), 0, 24, approval_evidence_reference(media)),),
    )
    assert len(revision.selections) == 1
    assert revision.selections[0].shot_id == "SHT-001"
    assert revision.selections[0].approval_evidence_ref == approval_evidence_reference(media)


def test_draft_rejects_media_without_human_approval_reference():
    with pytest.raises(ValueError, match="Approval evidence reference"):
        build_partial_draft(
            _authority(),
            _scope(),
            "ASM-1",
            "REV-1",
            (("SHT-001", _media(), 0, 24, ""),),
        )


def test_draft_rejects_mismatched_media_shot():
    with pytest.raises(ValueError, match="Shot identity"):
        build_partial_draft(
            _authority(),
            _scope(),
            "ASM-1",
            "REV-1",
            (
                (
                    "SHT-001",
                    (media := _media(shot="SHT-999")),
                    0,
                    24,
                    approval_evidence_reference(media),
                ),
            ),
        )


def test_partial_draft_publication_fails_closed():
    revision = build_partial_draft(
        _authority(),
        _scope(),
        "ASM-1",
        "REV-1",
        (("SHT-001", (media := _media()), 0, 24, approval_evidence_reference(media)),),
    )
    repo, validator = Mock(), Mock()
    validator.validate.return_value = SimpleNamespace(
        allowed=False, blockers=("Media bytes mismatch",)
    )
    with pytest.raises(ValueError, match="Media bytes mismatch"):
        publish_partial_draft(revision, repo, validator)
    repo.create.assert_not_called()
    validator.validate.return_value = SimpleNamespace(allowed=True, blockers=())
    publish_partial_draft(revision, repo, validator)
    repo.create.assert_called_once_with(revision)


def test_approval_reference_cannot_be_substituted():
    with pytest.raises(ValueError, match="Approval evidence reference"):
        build_partial_draft(
            _authority(),
            _scope(),
            "ASM-1",
            "REV-1",
            (("SHT-001", _media(), 0, 24, "UNRELATED-QC"),),
        )


def test_recorded_approval_reference_is_deterministic():
    media = _media()
    first = approval_evidence_reference(media)
    assert first is not None
    assert first == approval_evidence_reference(media)
    assert first.startswith("GM-APPROVAL-SHA256-")


def test_partial_draft_allows_other_incomplete_shots_but_not_selected_unready_shot():
    from vscs.application.episode_shot_set_resolver import EpisodeShotSet

    media = _media()
    authority = EpisodeShotSet(
        "EP-001", ("SHT-001", "SHT-002"), ("SHT-002: planning review outstanding",)
    )
    selected = (("SHT-001", media, 0, 24, approval_evidence_reference(media)),)
    draft = build_partial_draft(authority, _scope(), "ASM-PARTIAL", "REV-1", selected)
    assert tuple(item.shot_id for item in draft.selections) == ("SHT-001",)
    blocked = EpisodeShotSet(
        "EP-001", ("SHT-001", "SHT-002"), ("SHT-001: planning review outstanding",)
    )
    with pytest.raises(ValueError, match="Planning or review blockers"):
        build_partial_draft(blocked, _scope(), "ASM-PARTIAL", "REV-1", selected)
