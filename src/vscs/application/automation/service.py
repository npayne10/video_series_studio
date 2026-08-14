"""Project-backed persistence and human governance for automation proposals."""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .contracts import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)


class AutomationProposalError(RuntimeError):
    """Raised when an automation proposal cannot be processed safely."""


class AutomationProposalService:
    """Persist reviewable proposals without mutating governed production authority."""

    FILE_NAME = "automation_proposals.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService) -> None:
        self.projects = projects

    @property
    def proposal_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "automation" / self.FILE_NAME

    def list_proposals(self) -> tuple[AutomationProposal, ...]:
        path = self.proposal_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            proposals = tuple(self._from_dict(item) for item in raw.get("proposals", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AutomationProposalError(f"Unable to load automation proposals: {exc}") from exc
        return tuple(sorted(proposals, key=lambda item: item.proposal_id))

    def proposal(self, proposal_id: str) -> AutomationProposal | None:
        normalized = proposal_id.strip().upper()
        return next(
            (item for item in self.list_proposals() if item.proposal_id == normalized),
            None,
        )

    def save(self, proposal: AutomationProposal) -> AutomationProposal:
        """Persist a proposal. Production approval is intentionally outside this service."""
        normalized = proposal.proposal_id.strip().upper()
        if not normalized:
            raise ValueError("Automation proposal ID is required")
        if not proposal.target_id.strip():
            raise ValueError("Automation proposal target ID is required")
        proposals = {item.proposal_id: item for item in self.list_proposals()}
        stored = replace(
            proposal, proposal_id=normalized, target_id=proposal.target_id.strip().upper()
        )
        proposals[stored.proposal_id] = stored
        self._write(tuple(proposals.values()))
        return stored

    def mark_reviewed(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        notes: str = "",
    ) -> AutomationProposal:
        current = self._require(proposal_id)
        reviewer = reviewed_by.strip()
        if not reviewer:
            raise ValueError("Human reviewer identity is required")
        if current.status is not AutomationProposalStatus.PROPOSED:
            raise AutomationProposalError("Only Proposed automation can enter human review")
        updated = replace(
            current,
            status=AutomationProposalStatus.REVIEWED,
            reviewed_by=reviewer,
            review_notes=notes.strip(),
        )
        return self.save(updated)

    def accept(self, proposal_id: str, *, accepted_by: str) -> AutomationProposal:
        """Accept for governed planner consumption; never approve production authority."""
        current = self._require(proposal_id)
        reviewer = accepted_by.strip()
        if not reviewer:
            raise ValueError("Human identity is required to accept automation")
        if current.status is not AutomationProposalStatus.REVIEWED or not current.human_reviewed:
            raise AutomationProposalError("Automation must be human-reviewed before acceptance")
        updated = replace(
            current,
            status=AutomationProposalStatus.ACCEPTED,
            accepted_by=reviewer,
        )
        return self.save(updated)

    def reject(
        self,
        proposal_id: str,
        *,
        rejected_by: str,
        notes: str,
    ) -> AutomationProposal:
        current = self._require(proposal_id)
        reviewer = rejected_by.strip()
        reason = notes.strip()
        if not reviewer or not reason:
            raise ValueError("Human identity and rejection notes are required")
        if current.status not in {
            AutomationProposalStatus.PROPOSED,
            AutomationProposalStatus.REVIEWED,
        }:
            raise AutomationProposalError("Only unconsumed automation may be rejected")
        updated = replace(
            current,
            status=AutomationProposalStatus.REJECTED,
            rejected_by=reviewer,
            review_notes=reason,
            reviewed_by=current.reviewed_by or reviewer,
        )
        return self.save(updated)

    def _require(self, proposal_id: str) -> AutomationProposal:
        proposal = self.proposal(proposal_id)
        if proposal is None:
            raise AutomationProposalError(
                f"Automation proposal {proposal_id.strip().upper()} does not exist"
            )
        return proposal

    def _write(self, proposals: tuple[AutomationProposal, ...]) -> None:
        path = self.proposal_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "written_at": datetime.now(UTC).isoformat(),
            "proposals": [
                self._to_dict(item) for item in sorted(proposals, key=lambda p: p.proposal_id)
            ],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str)
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise AutomationProposalError(f"Unable to save automation proposals: {exc}") from exc

    @staticmethod
    def _to_dict(proposal: AutomationProposal) -> dict[str, Any]:
        raw = asdict(proposal)
        raw["proposal_type"] = proposal.proposal_type.value
        raw["status"] = proposal.status.value
        raw["provenance"]["source_kind"] = proposal.provenance.source_kind.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> AutomationProposal:
        provenance_raw = dict(raw["provenance"])
        provenance_raw["source_kind"] = AutomationSourceKind(str(provenance_raw["source_kind"]))
        return AutomationProposal(
            proposal_id=str(raw["proposal_id"]),
            proposal_type=AutomationProposalType(str(raw["proposal_type"])),
            target_id=str(raw["target_id"]),
            payload=dict(raw.get("payload", {})),
            provenance=AutomationProvenance(**provenance_raw),
            status=AutomationProposalStatus(str(raw.get("status", "proposed"))),
            review_notes=str(raw.get("review_notes", "")),
            reviewed_by=str(raw.get("reviewed_by", "")),
            accepted_by=str(raw.get("accepted_by", "")),
            rejected_by=str(raw.get("rejected_by", "")),
            metadata={str(key): str(value) for key, value in dict(raw.get("metadata", {})).items()},
        )
