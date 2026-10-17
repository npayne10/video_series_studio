"""Phase 20.18.2.3.7.3: governed episode Shot-set completion tests."""

from dataclasses import replace

import pytest

from vscs.application.assembly_contracts import (
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyTimelineRevision,
    AssemblyValidation,
    ShotSelection,
)
from vscs.application.shot_set_completion import (
    ShotSetCompletionService,
    ShotSetDeclarationError,
)
from vscs.infrastructure.shot_set_completion import (
    GovernedShotSetCompletion,
    JsonShotSetCompletionRepository,
)


def _timeline(state="approved"):
    scope = AssemblyScope("PROD-1", AssemblyScopeKind.EPISODE, "EP-1", "SET-1", "a" * 64)
    shot = ShotSelection(
        "SCN-1",
        "SHT-1",
        "GM-1",
        "1",
        "b" * 64,
        "QC-1" if state == "approved" else None,
        0,
        24,
        0,
        state,
    )
    return AssemblyTimelineRevision("ASM-1", "REV-1", scope, (shot,), 24, 1)


class _Verifier:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = 0

    def validate(self, revision, *, final_use):
        assert final_use
        self.calls += 1
        if self.allowed:
            return AssemblyValidation(True, ())
        return AssemblyValidation(False, ("Authoritative media approval missing",))


def test_readiness_requires_expected_coverage_and_human_approved_source():
    service = ShotSetCompletionService()
    timeline = _timeline()
    okay = service.assess(
        timeline.scope,
        ("SHT-1",),
        timeline.selections,
        media_validation=AssemblyValidation(True, ()),
    )
    assert okay.ready
    assert len(okay.fingerprint) == 64
    missing = service.assess(
        timeline.scope,
        ("SHT-1", "SHT-2"),
        timeline.selections,
        media_validation=AssemblyValidation(True, ()),
    )
    assert not missing.ready
    unapproved = _timeline("generated")
    result = service.assess(
        unapproved.scope,
        ("SHT-1",),
        unapproved.selections,
        media_validation=AssemblyValidation(True, ()),
    )
    assert not result.ready


def test_handoff_rechecks_authoritative_evidence(tmp_path):
    verifier = _Verifier()
    process = GovernedShotSetCompletion(verifier, JsonShotSetCompletionRepository(tmp_path))
    timeline = _timeline()
    readiness = process.assess(timeline, ("SHT-1",))
    verifier.allowed = False
    with pytest.raises(ShotSetDeclarationError, match="blocked"):
        process.declare(
            timeline,
            ("SHT-1",),
            declaration_id="DECL-1",
            operator_id="operator",
            observed_fingerprint=readiness.fingerprint,
        )
    assert process.repository.get("DECL-1") is None
    assert verifier.calls == 2


def test_explicit_operator_fingerprint_required_and_append_only(tmp_path):
    verifier = _Verifier()
    repository = JsonShotSetCompletionRepository(tmp_path)
    process = GovernedShotSetCompletion(verifier, repository)
    timeline = _timeline()
    readiness = process.assess(timeline, ("SHT-1",))
    with pytest.raises(ShotSetDeclarationError, match="changed"):
        process.declare(
            timeline,
            ("SHT-1",),
            declaration_id="DECL-1",
            operator_id="operator",
            observed_fingerprint="0" * 64,
        )
    declaration = process.declare(
        timeline,
        ("SHT-1",),
        declaration_id="DECL-1",
        operator_id="operator",
        observed_fingerprint=readiness.fingerprint,
    )
    assert repository.get("DECL-1") == declaration
    with pytest.raises(ShotSetDeclarationError, match="already exists"):
        process.declare(
            timeline,
            ("SHT-1",),
            declaration_id="DECL-1",
            operator_id="operator",
            observed_fingerprint=readiness.fingerprint,
        )


def test_revision_reopening_requires_new_shot_set_revision(tmp_path):
    process = GovernedShotSetCompletion(_Verifier(), JsonShotSetCompletionRepository(tmp_path))
    timeline = _timeline()
    first = process.declare(
        timeline,
        ("SHT-1",),
        declaration_id="DECL-1",
        operator_id="operator",
        observed_fingerprint=process.assess(timeline, ("SHT-1",)).fingerprint,
    )
    with pytest.raises(ShotSetDeclarationError, match="new Shot-set revision"):
        process.declare(
            timeline,
            ("SHT-1",),
            declaration_id="DECL-2",
            operator_id="operator",
            observed_fingerprint=process.assess(timeline, ("SHT-1",)).fingerprint,
            predecessor_declaration_id=first.declaration_id,
        )
    new_timeline = replace(
        timeline,
        revision_id="REV-2",
        scope=replace(timeline.scope, declared_shot_set_revision="SET-2"),
    )
    newer = process.declare(
        new_timeline,
        ("SHT-1",),
        declaration_id="DECL-2",
        operator_id="operator",
        observed_fingerprint=process.assess(new_timeline, ("SHT-1",)).fingerprint,
        predecessor_declaration_id=first.declaration_id,
    )
    assert newer.predecessor_declaration_id == first.declaration_id


def test_corrupt_declaration_and_unsafe_identifier_are_rejected(tmp_path):
    repo = JsonShotSetCompletionRepository(tmp_path)
    with pytest.raises(ShotSetDeclarationError, match="Unsafe"):
        repo.get("../outside")
    p = repo.root / "DECL-1.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"unexpected": true}', encoding="utf-8")
    with pytest.raises(ShotSetDeclarationError, match="invalid"):
        repo.get("DECL-1")
