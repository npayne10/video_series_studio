"""Episode/Video Shot-set completion governance, without provider or media mutations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from vscs.application.assembly_contracts import AssemblyScope, AssemblyValidation, ShotSelection


class ShotSetDeclarationError(ValueError):
    """The requested Shot-set declaration violates governance."""


class ShotSetState(StrEnum):
    DECLARED_COMPLETE = "declared_complete"


@dataclass(frozen=True, slots=True)
class ShotSetReadiness:
    scope: AssemblyScope
    expected_shot_ids: tuple[str, ...]
    selections: tuple[ShotSelection, ...]
    blockers: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not self.blockers

    @property
    def fingerprint(self) -> str:
        payload = {
            "scope": {
                "production_id": self.scope.production_id,
                "scope_kind": self.scope.scope_kind.value,
                "scope_id": self.scope.scope_id,
                "declared_shot_set_revision": self.scope.declared_shot_set_revision,
                "story_structure_fingerprint": self.scope.story_structure_fingerprint,
            },
            "expected_shot_ids": list(self.expected_shot_ids),
            "selections": [
                {
                    "shot_id": item.shot_id,
                    "media_id": item.generated_media_id,
                    "media_revision": item.media_revision,
                    "checksum": item.file_checksum,
                    "approval_evidence_ref": item.approval_evidence_ref,
                    "state": item.media_state,
                }
                for item in self.selections
            ],
            "blockers": list(self.blockers),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class ShotSetCompletionDeclaration:
    declaration_id: str
    scope: AssemblyScope
    readiness_fingerprint: str
    expected_shot_ids: tuple[str, ...]
    selected_media_ids: tuple[str, ...]
    operator_id: str
    predecessor_declaration_id: str | None = None
    state: ShotSetState = ShotSetState.DECLARED_COMPLETE
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.declaration_id.strip() or not self.operator_id.strip():
            raise ShotSetDeclarationError("Declaration requires identity and operator")
        if len(self.readiness_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in self.readiness_fingerprint
        ):
            raise ShotSetDeclarationError("Invalid readiness fingerprint")
        if self.predecessor_declaration_id == self.declaration_id:
            raise ShotSetDeclarationError("Declaration cannot supersede itself")
        if not self.expected_shot_ids or len(self.expected_shot_ids) != len(self.selected_media_ids):
            raise ShotSetDeclarationError("Declaration must pin complete Shot/media coverage")


class ShotSetCompletionService:
    """Pure readiness and human declaration logic; authoritative verification is injected."""

    def assess(
        self,
        scope: AssemblyScope,
        expected_shot_ids: tuple[str, ...],
        selections: tuple[ShotSelection, ...],
        *,
        media_validation: AssemblyValidation,
    ) -> ShotSetReadiness:
        blockers = list(media_validation.blockers)
        if not expected_shot_ids:
            blockers.append("No expected Shots are defined")
        if len(set(expected_shot_ids)) != len(expected_shot_ids):
            blockers.append("Duplicate expected Shot IDs")
        actual = tuple(item.shot_id for item in selections)
        if len(set(actual)) != len(actual):
            blockers.append("Duplicate selected Shot IDs")
        if set(actual) != set(expected_shot_ids):
            blockers.append("Shot coverage differs from the declared plan")
        if actual != expected_shot_ids:
            blockers.append("Selected Shot order differs from the declared plan")
        for item in selections:
            if item.media_state != "approved" or not item.approval_evidence_ref:
                blockers.append(f"{item.shot_id}: selected media is not approved")
        return ShotSetReadiness(scope, expected_shot_ids, selections, tuple(blockers))

    def declare(
        self,
        readiness: ShotSetReadiness,
        *,
        declaration_id: str,
        operator_id: str,
        observed_fingerprint: str,
        predecessor: ShotSetCompletionDeclaration | None = None,
    ) -> ShotSetCompletionDeclaration:
        if not readiness.ready:
            raise ShotSetDeclarationError("Shot-set declaration blocked: " + "; ".join(readiness.blockers))
        if observed_fingerprint != readiness.fingerprint:
            raise ShotSetDeclarationError("Shot-set evidence changed since review")
        if predecessor is not None:
            if predecessor.scope.production_id != readiness.scope.production_id or predecessor.scope.scope_id != readiness.scope.scope_id:
                raise ShotSetDeclarationError("Predecessor belongs to another production scope")
            if predecessor.scope.declared_shot_set_revision == readiness.scope.declared_shot_set_revision:
                raise ShotSetDeclarationError("Reopening requires a new Shot-set revision")
        return ShotSetCompletionDeclaration(
            declaration_id=declaration_id,
            scope=readiness.scope,
            readiness_fingerprint=readiness.fingerprint,
            expected_shot_ids=readiness.expected_shot_ids,
            selected_media_ids=tuple(item.generated_media_id for item in readiness.selections),
            operator_id=operator_id,
            predecessor_declaration_id=predecessor.declaration_id if predecessor else None,
        )
