"""Governed Shot-set completion: authoritative preflight and append-only declarations."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from vscs.application.assembly_contracts import AssemblyTimelineRevision
from vscs.application.shot_set_completion import (
    ShotSetCompletionDeclaration,
    ShotSetCompletionService,
    ShotSetDeclarationError,
    ShotSetReadiness,
    ShotSetState,
)
from vscs.infrastructure.assembly_timeline import AssemblyMediaEvidenceValidator


class JsonShotSetCompletionRepository:
    """Publish a declaration once; do not rewrite or mutate prior revisions."""

    _safe = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")

    def __init__(self, project_directory: Path) -> None:
        self.root = Path(project_directory) / ".vscs" / "episode_assembly" / "shot_set_declarations"

    def _path(self, declaration_id: str) -> Path:
        if not declaration_id or any(ch not in self._safe for ch in declaration_id):
            raise ShotSetDeclarationError("Unsafe declaration identity")
        return self.root / f"{declaration_id}.json"

    def save_new(self, declaration: ShotSetCompletionDeclaration) -> Path:
        path = self._path(declaration.declaration_id)
        if path.exists():
            raise ShotSetDeclarationError("Shot-set declaration already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        staged: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
            ) as stream:
                staged = Path(stream.name)
                json.dump(asdict(declaration), stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(staged, path)
        except FileExistsError as exc:
            raise ShotSetDeclarationError("Shot-set declaration already exists") from exc
        except OSError as exc:
            raise ShotSetDeclarationError("Cannot persist Shot-set declaration") from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        return path

    def get(self, declaration_id: str) -> ShotSetCompletionDeclaration | None:
        from vscs.application.assembly_contracts import AssemblyScope, AssemblyScopeKind

        path = self._path(declaration_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Invalid declaration")
            scope = raw["scope"]
            if not isinstance(scope, dict):
                raise ValueError("Invalid declaration scope")
            restored = ShotSetCompletionDeclaration(
                declaration_id=raw["declaration_id"],
                scope=AssemblyScope(
                    production_id=scope["production_id"],
                    scope_kind=AssemblyScopeKind(scope["scope_kind"]),
                    scope_id=scope["scope_id"],
                    declared_shot_set_revision=scope["declared_shot_set_revision"],
                    story_structure_fingerprint=scope["story_structure_fingerprint"],
                ),
                readiness_fingerprint=raw["readiness_fingerprint"],
                expected_shot_ids=tuple(raw["expected_shot_ids"]),
                selected_media_ids=tuple(raw["selected_media_ids"]),
                operator_id=raw["operator_id"],
                predecessor_declaration_id=raw["predecessor_declaration_id"],
                state=ShotSetState(raw["state"]),
                schema_version=raw["schema_version"],
            )
            if restored.declaration_id != declaration_id or restored.schema_version != "1.0":
                raise ValueError("Declaration identity/schema mismatch")
            if json.loads(json.dumps(asdict(restored))) != raw:
                raise ValueError("Declaration contains unsupported data")
            return restored
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ShotSetDeclarationError("Stored Shot-set declaration is invalid") from exc


class GovernedShotSetCompletion:
    """Re-verify current media immediately before a human declaration."""

    def __init__(
        self,
        verifier: AssemblyMediaEvidenceValidator,
        repository: JsonShotSetCompletionRepository,
    ) -> None:
        self.verifier = verifier
        self.repository = repository
        self.service = ShotSetCompletionService()

    def assess(
        self, revision: AssemblyTimelineRevision, expected_shot_ids: tuple[str, ...]
    ) -> ShotSetReadiness:
        evidence = self.verifier.validate(revision, final_use=True)
        return self.service.assess(
            revision.scope, expected_shot_ids, revision.selections, media_validation=evidence
        )

    def declare(
        self,
        revision: AssemblyTimelineRevision,
        expected_shot_ids: tuple[str, ...],
        *,
        declaration_id: str,
        operator_id: str,
        observed_fingerprint: str,
        predecessor_declaration_id: str | None = None,
    ) -> ShotSetCompletionDeclaration:
        readiness = self.assess(revision, expected_shot_ids)
        predecessor = None
        if predecessor_declaration_id is not None:
            predecessor = self.repository.get(predecessor_declaration_id)
            if predecessor is None:
                raise ShotSetDeclarationError("Previous declaration not found")
        declaration = self.service.declare(
            readiness,
            declaration_id=declaration_id,
            operator_id=operator_id,
            observed_fingerprint=observed_fingerprint,
            predecessor=predecessor,
        )
        self.repository.save_new(declaration)
        return declaration
