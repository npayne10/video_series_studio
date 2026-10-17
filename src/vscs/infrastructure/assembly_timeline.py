"""Fail-closed timeline persistence and authoritative media evidence (Phase 3.7.2)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vscs.application.assembly_contracts import (
    AssemblyContractError,
    AssemblyGovernanceValidator,
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyState,
    AssemblyTimelineRevision,
    AssemblyValidation,
    ShotSelection,
)
from vscs.application.generated_media import GeneratedMediaPersistenceService
from vscs.domain.generated_media import GeneratedMediaKind, GeneratedMediaState


class AssemblyEvidenceError(AssemblyContractError):
    """Assembly media, revision, or stored evidence cannot be trusted."""


def _object(raw: Any, name: str, keys: frozenset[str]) -> dict[str, Any]:
    if not isinstance(raw, dict) or frozenset(raw) != keys:
        raise AssemblyEvidenceError(f"{name} has invalid fields")
    return raw


def _fields(model: type[Any]) -> frozenset[str]:
    return frozenset(model.__dataclass_fields__)


def _encode(revision: AssemblyTimelineRevision) -> dict[str, Any]:
    return asdict(revision)


def _decode(raw: Any) -> AssemblyTimelineRevision:
    try:
        data = _object(raw, "timeline", _fields(AssemblyTimelineRevision))
        scope_data = _object(data["scope"], "scope", _fields(AssemblyScope))
        scope = AssemblyScope(
            **{**scope_data, "scope_kind": AssemblyScopeKind(scope_data["scope_kind"])}
        )
        selections_raw = data["selections"]
        if not isinstance(selections_raw, list):
            raise AssemblyEvidenceError("selections must be a list")
        selections = tuple(
            ShotSelection(
                **{
                    **_object(item, "selection", _fields(ShotSelection)),
                    "boundary_evidence_refs": tuple(item["boundary_evidence_refs"]),
                }
            )
            for item in selections_raw
        )
        return AssemblyTimelineRevision(
            assembly_id=data["assembly_id"],
            revision_id=data["revision_id"],
            scope=scope,
            selections=selections,
            frame_rate_num=data["frame_rate_num"],
            frame_rate_den=data["frame_rate_den"],
            state=AssemblyState(data["state"]),
            predecessor_revision=data["predecessor_revision"],
            reviewer_id=data["reviewer_id"],
            schema_version=data["schema_version"],
        )
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        raise AssemblyEvidenceError("Invalid stored assembly timeline") from exc


class JsonAssemblyTimelineRepository:
    """Append-only revision documents; never overwrite or approve media."""

    _safe = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

    def __init__(self, project_directory: Path) -> None:
        self.root = Path(project_directory) / ".vscs" / "episode_assembly" / "revisions"

    def _path(self, assembly_id: str, revision_id: str) -> Path:
        for name, value in (("assembly_id", assembly_id), ("revision_id", revision_id)):
            if not value or any(character not in self._safe for character in value):
                raise AssemblyEvidenceError(f"Unsafe {name}")
        return self.root / assembly_id / f"{revision_id}.json"

    def create(self, revision: AssemblyTimelineRevision) -> Path:
        """Exclusive atomic publication: a revision can never be replaced."""
        path = self._path(revision.assembly_id, revision.revision_id)
        if path.exists():
            raise AssemblyEvidenceError("Assembly revision already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "fingerprint": revision.fingerprint,
            "timeline": _encode(revision),
        }
        staged: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
            ) as stream:
                staged = Path(stream.name)
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            # Linking fails if another writer has already published this revision.
            os.link(staged, path)
        except FileExistsError as exc:
            raise AssemblyEvidenceError("Assembly revision already exists") from exc
        except OSError as exc:
            raise AssemblyEvidenceError("Unable to persist assembly revision") from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        return path

    def get(self, assembly_id: str, revision_id: str) -> AssemblyTimelineRevision | None:
        path = self._path(assembly_id, revision_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            document = _object(
                payload,
                "revision document",
                frozenset({"schema_version", "fingerprint", "timeline"}),
            )
            if document["schema_version"] != "1.0":
                raise AssemblyEvidenceError("Unsupported assembly repository schema")
            revision = _decode(document["timeline"])
            if revision.assembly_id != assembly_id or revision.revision_id != revision_id:
                raise AssemblyEvidenceError("Assembly revision identity mismatch")
            if document["fingerprint"] != revision.fingerprint:
                raise AssemblyEvidenceError("Assembly revision fingerprint mismatch")
            return revision
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AssemblyEvidenceError("Assembly revision evidence unreadable") from exc


class AssemblyMediaEvidenceValidator:
    """Verify actual Generated Media records and bytes; no state transitions."""

    def __init__(self, project_directory: Path, media: GeneratedMediaPersistenceService) -> None:
        self.project_directory = Path(project_directory).resolve()
        self.media = media

    def validate(
        self, revision: AssemblyTimelineRevision, *, final_use: bool
    ) -> AssemblyValidation:
        blockers = list(
            AssemblyGovernanceValidator().validate(revision, final_use=final_use).blockers
        )
        if revision.scope.scope_kind is not AssemblyScopeKind.EPISODE:
            blockers.append("Standalone scope verification not implemented")
            return AssemblyValidation(False, tuple(blockers))
        for selection in revision.selections:
            record = self.media.get(selection.generated_media_id)
            if record is None:
                blockers.append(f"{selection.shot_id}: media record missing")
                continue
            if (
                record.kind is not GeneratedMediaKind.VIDEO
                or record.scope.production_id != revision.scope.production_id
                or record.scope.episode_id != revision.scope.scope_id
                or record.scope.scene_id != selection.scene_id
                or record.scope.shot_id != selection.shot_id
                or str(record.revision) != selection.media_revision
                or record.state.value != selection.media_state
                or record.file.checksum_sha256 != selection.file_checksum
            ):
                blockers.append(
                    f"{selection.shot_id}: media identity, revision, state or checksum mismatch"
                )
                continue
            if final_use and (
                record.state is not GeneratedMediaState.APPROVED
                or not any(
                    event.to_state is GeneratedMediaState.APPROVED
                    for event in record.governance_history
                )
            ):
                blockers.append(f"{selection.shot_id}: authoritative human approval missing")
            if record.file.size_bytes is None:
                blockers.append(f"{selection.shot_id}: media byte size evidence missing")
                continue
            file_path = (self.project_directory / record.file.relative_path).resolve()
            if not file_path.is_relative_to(self.project_directory) or not file_path.is_file():
                blockers.append(f"{selection.shot_id}: media file missing or unsafe")
                continue
            try:
                data = file_path.read_bytes()
            except OSError:
                blockers.append(f"{selection.shot_id}: media file unreadable")
                continue
            if (
                len(data) != record.file.size_bytes
                or hashlib.sha256(data).hexdigest() != selection.file_checksum
            ):
                blockers.append(f"{selection.shot_id}: media bytes do not match evidence")
        return AssemblyValidation(not blockers, tuple(blockers))
