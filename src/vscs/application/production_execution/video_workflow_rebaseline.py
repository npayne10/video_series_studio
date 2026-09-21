"""Provider video workflow rebaseline candidates through Phase 20.18.2.2g."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderVideoCandidateId(StrEnum):
    """Stable identities for the governed A/B/C provider evaluation."""

    A_LTX23_INGREDIENTS = "A"
    B_LTX23_I2V_KEYFRAME = "B"
    C_LTX25_I2V_KEYFRAME = "C"


@dataclass(frozen=True, slots=True)
class ProviderVideoCandidate:
    """One provider architecture candidate and its current executable readiness."""

    candidate_id: ProviderVideoCandidateId
    label: str
    model_family: str
    workflow_id: str
    composition_authority: str
    prompt_mode: str
    execution_ready: bool
    preferred: bool = False
    readiness_note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id.value,
            "label": self.label,
            "model_family": self.model_family,
            "workflow_id": self.workflow_id,
            "composition_authority": self.composition_authority,
            "prompt_mode": self.prompt_mode,
            "execution_ready": self.execution_ready,
            "preferred": self.preferred,
            "readiness_note": self.readiness_note,
        }


VISUAL_ACCEPTANCE_CRITERIA = (
    "exactly_two_visible_people_for_all_frames",
    "james_identity_stable",
    "sandra_identity_stable",
    "no_extra_crew",
    "correct_iron_horizon_bridge",
    "xorix_visible_in_correct_place",
    "sandra_begins_at_control_station",
    "sandra_notices_reading",
    "sandra_turns_toward_james",
    "james_remains_focused_forward",
    "no_dialogue",
    "no_scene_cut",
    "no_reference_sheet_collapse",
    "no_location_transformation",
    "six_second_governed_duration",
)


def provider_video_candidates(*, governed_keyframe_ready: bool = False) -> tuple[ProviderVideoCandidate, ...]:
    """Return the provider candidates, activating C only from approved keyframe authority."""
    return (
        ProviderVideoCandidate(
            candidate_id=ProviderVideoCandidateId.A_LTX23_INGREDIENTS,
            label="LTX-2.3 Ingredients / cinematic prompt control",
            model_family="LTX-2.3",
            workflow_id="ltx23_production_v1",
            composition_authority="governed_multi_reference",
            prompt_mode="cinematic_scene_v2",
            execution_ready=not governed_keyframe_ready,
            readiness_note=(
                "Candidate A failed visual acceptance in Phase 20.18.2.2f and remains available "
                "only as the historical control."
            ),
        ),
        ProviderVideoCandidate(
            candidate_id=ProviderVideoCandidateId.B_LTX23_I2V_KEYFRAME,
            label="LTX-2.3 governed keyframe image-to-video",
            model_family="LTX-2.3",
            workflow_id="ltx23_i2v_keyframe_v1",
            composition_authority="governed_start_keyframe",
            prompt_mode="motion_only_v2",
            execution_ready=False,
            readiness_note=(
                "Blocked until a governed Shot Composition Keyframe and dedicated I2V workflow "
                "are installed and acceptance-tested."
            ),
        ),
        ProviderVideoCandidate(
            candidate_id=ProviderVideoCandidateId.C_LTX25_I2V_KEYFRAME,
            label="LTX-2.5 governed keyframe image-to-video",
            model_family="LTX-2.5",
            workflow_id="ltx25_i2v_keyframe_v1",
            composition_authority="governed_start_keyframe",
            prompt_mode="motion_only_v2",
            execution_ready=governed_keyframe_ready,
            preferred=True,
            readiness_note=(
                "Preferred Phase 20.18.2.2g target. Requires an approved governed Shot Composition "
                "Keyframe and successful local LTX-2.5 deployment assurance."
            ),
        ),
    )


def provider_video_rebaseline_contract(
    *, governed_keyframe_ready: bool = False
) -> dict[str, object]:
    """Return package metadata for the current governed provider baseline."""
    candidates = provider_video_candidates(governed_keyframe_ready=governed_keyframe_ready)
    active = next(item for item in candidates if item.execution_ready)
    preferred = next(item for item in candidates if item.preferred)
    return {
        "schema_version": "1.0",
        "phase": "20.18.2.2g" if governed_keyframe_ready else "20.18.2.2f",
        "active_candidate": active.candidate_id.value,
        "preferred_candidate": preferred.candidate_id.value,
        "execution_policy": (
            "candidate_c_requires_approved_governed_keyframe"
            if governed_keyframe_ready
            else "candidate_a_control_only_until_governed_keyframe"
        ),
        "candidates": [item.to_dict() for item in candidates],
        "visual_acceptance_criteria": list(VISUAL_ACCEPTANCE_CRITERIA),
    }
