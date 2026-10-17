"""Checkpoint 2: append-only assembly revision and source evidence tests."""

import json
from dataclasses import replace

import pytest

from vscs.application.assembly_contracts import (
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyTimelineRevision,
    ShotSelection,
)
from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
)
from vscs.infrastructure.assembly_timeline import (
    AssemblyEvidenceError,
    AssemblyMediaEvidenceValidator,
    JsonAssemblyTimelineRepository,
)
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository


def _revision(checksum="a" * 64, media_state="generated"):
    scope = AssemblyScope("PROD", AssemblyScopeKind.EPISODE, "EP-1", "SET-1", "b" * 64)
    shot = ShotSelection(
        scene_id="SCN-1",
        shot_id="SHT-1",
        generated_media_id="GM-1",
        media_revision="1",
        file_checksum=checksum,
        approval_evidence_ref=None,
        source_in_frame=0,
        source_out_frame=24,
        sequence_index=0,
        media_state=media_state,
    )
    return AssemblyTimelineRevision("ASM-1", "REV-1", scope, (shot,), 24, 1)


def _media(tmp_path, payload=b"video bytes"):
    location = tmp_path / "managed" / "video.mp4"
    location.parent.mkdir(parents=True)
    location.write_bytes(payload)
    import hashlib

    checksum = hashlib.sha256(payload).hexdigest()
    service = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(tmp_path / ".vscs" / "generated_media")
    )
    service.register(
        GeneratedMedia(
            media_id="GM-1",
            kind=GeneratedMediaKind.VIDEO,
            scope=GeneratedMediaScope("PROD", "EP-1", "PT-1", "SCN-1", "SHT-1"),
            provenance=GeneratedMediaProvenance("EXEC-1", "provider", "JOB-1"),
            file=GeneratedMediaFile("managed/video.mp4", checksum, len(payload)),
        )
    )
    return service, location, checksum


def test_revision_round_trip_is_immutable_and_fingerprint_verified(tmp_path):
    repo = JsonAssemblyTimelineRepository(tmp_path)
    revision = _revision()
    repo.create(revision)
    assert repo.get("ASM-1", "REV-1") == revision
    with pytest.raises(AssemblyEvidenceError, match="already exists"):
        repo.create(revision)
    assert repo.get("ASM-1", "REV-1").fingerprint == revision.fingerprint


def test_corrupted_revision_fails_closed(tmp_path):
    repo = JsonAssemblyTimelineRepository(tmp_path)
    path = repo.create(_revision())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["timeline"]["selections"][0]["source_out_frame"] = 99
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(AssemblyEvidenceError, match="fingerprint"):
        repo.get("ASM-1", "REV-1")
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(AssemblyEvidenceError, match="unreadable"):
        repo.get("ASM-1", "REV-1")


def test_revision_filename_identity_is_safe(tmp_path):
    repo = JsonAssemblyTimelineRepository(tmp_path)
    with pytest.raises(AssemblyEvidenceError, match="Unsafe"):
        repo.get("../../unsafe", "REV-1")


def test_generated_media_record_and_bytes_are_verified(tmp_path):
    media, location, checksum = _media(tmp_path)
    validator = AssemblyMediaEvidenceValidator(tmp_path, media)
    revision = _revision(checksum)
    assert validator.validate(revision, final_use=False).allowed
    assert not validator.validate(revision, final_use=True).allowed
    location.write_bytes(b"tampered")
    result = validator.validate(revision, final_use=False)
    assert not result.allowed
    assert "bytes do not match evidence" in " ".join(result.blockers)


def test_media_mismatch_and_missing_reference_block(tmp_path):
    media, _location, checksum = _media(tmp_path)
    validator = AssemblyMediaEvidenceValidator(tmp_path, media)
    revision = _revision(checksum)
    mismatched = replace(revision, selections=(replace(revision.selections[0], shot_id="WRONG"),))
    assert not validator.validate(mismatched, final_use=False).allowed
    nonexistent = replace(
        revision, selections=(replace(revision.selections[0], generated_media_id="MISSING"),)
    )
    assert not validator.validate(nonexistent, final_use=False).allowed
    bad_revision = replace(
        revision, selections=(replace(revision.selections[0], media_revision="bad"),)
    )
    assert not validator.validate(bad_revision, final_use=False).allowed


def test_provisional_historical_recovery_never_becomes_final_media(tmp_path):
    media, _location, checksum = _media(tmp_path)
    revision = _revision(checksum)
    assert (
        not AssemblyMediaEvidenceValidator(tmp_path, media)
        .validate(revision, final_use=True)
        .allowed
    )
