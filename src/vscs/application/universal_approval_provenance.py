"""Governed approval provenance for READY Universal Production Descriptions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionDraft,
    UniversalProductionDescriptionStatus,
)


@dataclass(frozen=True, slots=True)
class UniversalProductionDescriptionApproval:
    """One explicit human approval of reviewed UPD authority."""

    shot_id: str
    reviewed_authority_fingerprint: str
    approved_by: str
    approved_at: str


class UniversalProductionDescriptionApprovalStore:
    """Persist approval separately from mutable reference dependency data."""

    FILE_NAME = "universal_production_description_approvals.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService) -> None:
        self.projects = projects

    @property
    def approval_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list(self) -> tuple[UniversalProductionDescriptionApproval, ...]:
        path = self.approval_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            approvals = tuple(
                UniversalProductionDescriptionApproval(
                    shot_id=str(item["shot_id"]).strip().upper(),
                    reviewed_authority_fingerprint=str(
                        item["reviewed_authority_fingerprint"]
                    ).strip(),
                    approved_by=str(item["approved_by"]).strip(),
                    approved_at=str(item["approved_at"]).strip(),
                )
                for item in raw.get("approvals", [])
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise UniversalProductionDescriptionCompilerError(
                f"Unable to load Universal Production Description approval provenance: {exc}"
            ) from exc
        return tuple(sorted(approvals, key=lambda item: item.shot_id))

    def current_for(
        self, draft: UniversalProductionDescriptionDraft
    ) -> UniversalProductionDescriptionApproval | None:
        fingerprint = self.reviewed_authority_fingerprint(draft)
        return next(
            (
                item
                for item in self.list()
                if item.shot_id == draft.shot_id.strip().upper()
                and item.reviewed_authority_fingerprint == fingerprint
            ),
            None,
        )

    def establish(
        self,
        draft: UniversalProductionDescriptionDraft,
        approved_by: str,
    ) -> UniversalProductionDescriptionApproval:
        reviewer = approved_by.strip()
        if not reviewer:
            raise UniversalProductionDescriptionCompilerError(
                "UPD approver identity cannot be blank"
            )
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "UPD approval provenance can only be established for READY authority"
            )
        approval = UniversalProductionDescriptionApproval(
            shot_id=draft.shot_id.strip().upper(),
            reviewed_authority_fingerprint=self.reviewed_authority_fingerprint(draft),
            approved_by=reviewer,
            approved_at=datetime.now(UTC).isoformat(),
        )
        retained = tuple(item for item in self.list() if item.shot_id != approval.shot_id)
        self._write((*retained, approval))
        return approval

    def clear(self, shot_id: str) -> None:
        normalized = shot_id.strip().upper()
        retained = tuple(item for item in self.list() if item.shot_id != normalized)
        self._write(retained)

    @classmethod
    def reviewed_authority_fingerprint(
        cls, draft: UniversalProductionDescriptionDraft
    ) -> str:
        description = json.loads(
            json.dumps(draft.description_value(), sort_keys=True, default=str)
        )
        if not isinstance(description, dict):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description value is not a JSON object"
            )
        description.pop("reference_plan", None)
        canonical = json.dumps(
            description,
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _write(self, approvals: tuple[UniversalProductionDescriptionApproval, ...]) -> None:
        path = self.approval_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "approvals": [asdict(item) for item in approvals],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


def install_universal_approval_provenance() -> None:
    """Extend the existing UPD compiler with explicit approval authority."""
    service_type: Any = UniversalProductionDescriptionCompilerService
    if getattr(service_type, "_approval_provenance_installed", False):
        return

    original_return_to_draft = service_type.return_to_draft

    def approval_provenance(
        self: UniversalProductionDescriptionCompilerService,
        shot_id: str,
    ) -> UniversalProductionDescriptionApproval | None:
        draft = self.draft(shot_id)
        if draft is None or draft.status is not UniversalProductionDescriptionStatus.READY:
            return None
        return UniversalProductionDescriptionApprovalStore(self.projects).current_for(draft)

    def mark_ready_with_approval(
        self: UniversalProductionDescriptionCompilerService,
        shot_id: str,
        approved_by: str,
    ) -> UniversalProductionDescriptionDraft:
        reviewer = approved_by.strip()
        if not reviewer:
            raise UniversalProductionDescriptionCompilerError(
                "Enter the UPD approver identity before marking the Universal Production Description Ready"
            )
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is already Ready"
            )
        if not self.is_current(current):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale against current production authority"
            )
        self._require_upstream_ready(current.shot_id)
        self._require_consistent(current.description_value())
        self._validate(current.description_value())
        ready = replace(current, status=UniversalProductionDescriptionStatus.READY)
        self._replace(ready)
        UniversalProductionDescriptionApprovalStore(self.projects).establish(ready, reviewer)
        self.compile(ready.shot_id)
        return ready

    def establish_approval_provenance(
        self: UniversalProductionDescriptionCompilerService,
        shot_id: str,
        approved_by: str,
    ) -> UniversalProductionDescriptionApproval:
        draft = self._require_draft(shot_id)
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Approval provenance can only be established for a READY Universal Production Description"
            )
        if not self.is_current(draft):
            draft = self._refresh_ready_reference_dependency(draft)
        if not self.is_current(draft):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale and cannot receive approval provenance"
            )
        approval = UniversalProductionDescriptionApprovalStore(self.projects).establish(
            draft, approved_by
        )
        self.compile(draft.shot_id)
        return approval

    def compile_with_approval(
        self: UniversalProductionDescriptionCompilerService,
        shot_id: str,
    ) -> Any:
        draft = self._require_draft(shot_id)
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Only Ready Universal Production Description may be compiled"
            )
        if not self.is_current(draft):
            draft = self._refresh_ready_reference_dependency(draft)
        if not self.is_current(draft):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale and cannot be compiled"
            )
        self._require_upstream_ready(draft.shot_id)
        description = draft.description_value()
        self._require_consistent(description)
        self._validate(description)
        compiled = self._compile_description(description)
        approval = UniversalProductionDescriptionApprovalStore(self.projects).current_for(draft)
        if approval is not None:
            approval_payload = {
                "approved_by": approval.approved_by,
                "approved_at": approval.approved_at,
                "reviewed_authority_fingerprint": approval.reviewed_authority_fingerprint,
            }
            compiled["approval"] = approval_payload
            compiled["approved_by"] = approval.approved_by
            compiled["approved_at"] = approval.approved_at
        return self._derive(
            draft.shot_id,
            compiled,
            production_notes=draft.production_notes,
        )

    def return_to_draft_with_approval_clear(
        self: UniversalProductionDescriptionCompilerService,
        shot_id: str,
    ) -> UniversalProductionDescriptionDraft:
        draft = original_return_to_draft(self, shot_id)
        UniversalProductionDescriptionApprovalStore(self.projects).clear(draft.shot_id)
        return draft

    service_type.approval_provenance = approval_provenance
    service_type.mark_ready_with_approval = mark_ready_with_approval
    service_type.establish_approval_provenance = establish_approval_provenance
    service_type.compile = compile_with_approval
    service_type.return_to_draft = return_to_draft_with_approval_clear
    service_type._approval_provenance_installed = True
