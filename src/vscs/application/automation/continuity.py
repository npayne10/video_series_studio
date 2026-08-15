"""Deterministic continuity-aware proposal automation for Phase 19.5.9."""

from __future__ import annotations

import re
from hashlib import sha256

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


class ContinuityProposalAutomationService:
    """Resolve cross-Shot continuity proposals without mutating Continuity authority."""

    _PRESERVATION_PHRASES = (
        "same as previous shot",
        "same as the previous shot",
        "same as in previous shot",
        "same as in the previous shot",
        "continues from previous shot",
        "continues from the previous shot",
        "continue from previous shot",
        "continue from the previous shot",
        "unchanged from previous shot",
        "unchanged from the previous shot",
        "preserve previous",
        "preserve the previous",
        "as previous shot",
        "as the previous shot",
    )

    def __init__(self, proposals: AutomationProposalService) -> None:
        self._proposals = proposals

    def generate(
        self,
        *,
        story_id: str,
        source_text: str,
        source_revision: str,
    ) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision or not source_text.strip():
            raise ValueError("Story ID, source revision and source text are required")
        current = tuple(
            item
            for item in self._proposals.list_proposals()
            if item.provenance.source_story_id == normalized_story
            and item.provenance.source_revision == revision
        )
        shots = sorted(
            (item for item in current if item.proposal_type is AutomationProposalType.SHOT),
            key=lambda item: item.target_id,
        )
        if not shots:
            raise ValueError("Generate current Shot proposals before Continuity proposals")
        by_type = {
            proposal_type: {
                item.target_id: item
                for item in current
                if item.proposal_type is proposal_type
            }
            for proposal_type in (
                AutomationProposalType.ACTION_PERFORMANCE,
                AutomationProposalType.ENVIRONMENT,
                AutomationProposalType.CAMERA,
                AutomationProposalType.LIGHTING,
            )
        }
        labels = {
            AutomationProposalType.ACTION_PERFORMANCE: "Action/Performance",
            AutomationProposalType.ENVIRONMENT: "Environment",
            AutomationProposalType.CAMERA: "Camera",
            AutomationProposalType.LIGHTING: "Lighting",
        }
        for proposal_type, lookup in by_type.items():
            missing = [shot.target_id for shot in shots if shot.target_id not in lookup]
            if missing:
                raise ValueError(
                    f"Generate current {labels[proposal_type]} proposals before Continuity proposals; "
                    f"missing {len(missing)} Shot(s)"
                )

        generated: list[AutomationProposal] = []
        previous: AutomationProposal | None = None
        for shot in shots:
            performance = by_type[AutomationProposalType.ACTION_PERFORMANCE][shot.target_id]
            environment = by_type[AutomationProposalType.ENVIRONMENT][shot.target_id]
            camera = by_type[AutomationProposalType.CAMERA][shot.target_id]
            lighting = by_type[AutomationProposalType.LIGHTING][shot.target_id]
            previous_performance = (
                by_type[AutomationProposalType.ACTION_PERFORMANCE].get(previous.target_id)
                if previous is not None
                else None
            )
            previous_camera = (
                by_type[AutomationProposalType.CAMERA].get(previous.target_id)
                if previous is not None
                else None
            )
            previous_lighting = (
                by_type[AutomationProposalType.LIGHTING].get(previous.target_id)
                if previous is not None
                else None
            )
            proposal = self._proposal(
                story_id=normalized_story,
                revision=revision,
                source_text=source_text,
                shot=shot,
                performance=performance,
                environment=environment,
                camera=camera,
                lighting=lighting,
                previous=previous,
                previous_performance=previous_performance,
                previous_camera=previous_camera,
                previous_lighting=previous_lighting,
            )
            generated.append(self._proposals.save(proposal))
            previous = shot
        return tuple(generated)

    def _proposal(
        self,
        *,
        story_id: str,
        revision: str,
        source_text: str,
        shot: AutomationProposal,
        performance: AutomationProposal,
        environment: AutomationProposal,
        camera: AutomationProposal,
        lighting: AutomationProposal,
        previous: AutomationProposal | None,
        previous_performance: AutomationProposal | None,
        previous_camera: AutomationProposal | None,
        previous_lighting: AutomationProposal | None,
    ) -> AutomationProposal:
        opening = str(performance.payload.get("opening_state", "")).strip() or str(
            shot.payload.get("continuity_in", "")
        ).strip()
        closing = str(performance.payload.get("closing_state", "")).strip() or str(
            shot.payload.get("continuity_out", "")
        ).strip()
        previous_closing = (
            str(previous_performance.payload.get("closing_state", "")).strip()
            if previous_performance is not None
            else ""
        )
        preservation = self._is_preservation_directive(opening)
        if preservation and previous_closing:
            effective_opening = previous_closing
            opening_resolution = "preserve-previous-directive"
        elif opening:
            effective_opening = opening
            opening_resolution = "explicit-opening-state"
        elif previous_closing:
            effective_opening = previous_closing
            opening_resolution = "inherited-previous-closing-state"
        else:
            effective_opening = ""
            opening_resolution = "series-entry"

        conflicts: list[str] = []
        if opening and previous_closing and not preservation and opening != previous_closing:
            conflicts.append(
                "Current opening state differs from the previous Shot closing state; human review required."
            )
        previous_screen = (
            str(previous_camera.payload.get("screen_direction", "")).strip()
            if previous_camera is not None
            else ""
        )
        current_screen = str(camera.payload.get("screen_direction", "")).strip()
        if (
            previous_screen
            and current_screen
            and current_screen != "preserve_previous"
            and previous_screen not in {"preserve_previous", "neutral"}
            and current_screen not in {previous_screen, "neutral"}
        ):
            conflicts.append("Screen direction reverses relative to the previous Shot; human review required.")

        previous_lighting_notes = (
            str(previous_lighting.payload.get("continuity_notes", "")).strip()
            if previous_lighting is not None
            else ""
        )
        current_lighting_notes = str(lighting.payload.get("continuity_notes", "")).strip()
        digest = sha256(
            f"{story_id}|{revision}|continuity|{shot.proposal_id}|{previous.proposal_id if previous else ''}|"
            f"{performance.proposal_id}|{environment.proposal_id}|{camera.proposal_id}|{lighting.proposal_id}".encode()
        ).hexdigest()
        return AutomationProposal(
            proposal_id=f"AUT-CONTINUITY-{digest[:12].upper()}",
            proposal_type=AutomationProposalType.CONTINUITY,
            target_id=shot.target_id,
            payload={
                "current_shot_id": shot.target_id,
                "previous_shot_id": previous.target_id if previous else "",
                "previous_closing_state": previous_closing,
                "current_opening_state": opening,
                "effective_opening_state": effective_opening,
                "opening_resolution": opening_resolution,
                "current_closing_state": closing,
                "previous_screen_direction": previous_screen,
                "current_screen_direction": current_screen,
                "previous_lighting_continuity": previous_lighting_notes,
                "current_lighting_continuity": current_lighting_notes,
                "environment": dict(environment.payload),
                "continuity_conflicts": conflicts,
                "inheritance_mode": "previous-shot-closing-state" if previous else "series-entry",
                "continuity_notes": self._continuity_notes(
                    previous_closing=previous_closing,
                    effective_opening=effective_opening,
                    conflicts=conflicts,
                ),
                "continuity_constraints": [
                    "Preserve established character, prop, location and environmental state across adjacent Shots.",
                    "Do not resolve a detected continuity conflict automatically; require human review.",
                ],
            },
            provenance=AutomationProvenance(
                source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
                source_story_id=story_id,
                source_revision=revision,
                source_scope=(
                    "current and previous Shot proposals plus current Action/Performance, Environment, Camera and Lighting proposals"
                ),
                provider="vscs",
                model="deterministic-continuity-resolution",
                confidence=1.0 if not conflicts else 0.75,
                inference_note=(
                    "Continuity is resolved deterministically for human review only. Conflicts remain explicit and no governed Continuity compilation is created or marked Ready."
                ),
                resolution_method="Phase 19.4.6-compatible previous-Shot state inheritance",
            ),
            metadata={
                "phase": "19.5.9",
                "parent_shot_proposal_id": shot.proposal_id,
                "previous_shot_proposal_id": previous.proposal_id if previous else "",
                "parent_action_performance_proposal_id": performance.proposal_id,
                "parent_environment_proposal_id": environment.proposal_id,
                "parent_camera_proposal_id": camera.proposal_id,
                "parent_lighting_proposal_id": lighting.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )

    @classmethod
    def _is_preservation_directive(cls, value: str) -> bool:
        normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
        if not normalized:
            return False
        if normalized in {"unchanged", "same", "preserve previous"}:
            return True
        return any(phrase in normalized for phrase in cls._PRESERVATION_PHRASES)

    @staticmethod
    def _continuity_notes(
        *, previous_closing: str, effective_opening: str, conflicts: list[str]
    ) -> str:
        if conflicts:
            return "Human continuity review required: " + " ".join(conflicts)
        if previous_closing and effective_opening == previous_closing:
            return "Opening state inherits the previous Shot closing state without conflict."
        if not previous_closing:
            return "Series/sequence entry; no previous Shot state is available to inherit."
        return "No deterministic cross-Shot continuity conflict detected."
