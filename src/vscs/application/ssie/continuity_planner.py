"""Deterministic continuity planning for SSIE shots."""

from __future__ import annotations

from .models import ContinuityPlan, Scene, ShotPlan


class RuleBasedContinuityPlanner:
    """Create explicit continuity state for downstream production systems."""

    def plan_continuity(
        self,
        scene: Scene,
        shot: ShotPlan,
        previous_shot: ShotPlan | None = None,
    ) -> ContinuityPlan:
        incoming = list(shot.continuity_requirements)
        if previous_shot is not None:
            incoming.append(f"Continue spatial and performance state from {previous_shot.shot_id}.")

        participant_states = tuple(
            f"{asset_id}: preserve approved appearance, wardrobe, position, and condition"
            for asset_id in shot.subject_asset_ids
        )
        prop_ids = tuple(
            asset_id
            for asset_id in shot.required_asset_ids
            if asset_id not in shot.subject_asset_ids and asset_id != scene.location_asset_id
        )
        prop_states = tuple(
            f"{asset_id}: preserve placement, orientation, and interaction state"
            for asset_id in prop_ids
        )
        lighting_state = (
            f"Maintain {scene.time_of_day.strip()} lighting state."
            if scene.time_of_day
            else "Maintain the established scene lighting state."
        )
        outgoing = (
            f"Location remains {scene.location_asset_id}.",
            "Subject positions and object states remain available to the next shot.",
        )
        return ContinuityPlan(
            location_state=(
                f"{scene.location_asset_id}: preserve architecture, dressing, and damage state"
            ),
            participant_states=participant_states,
            prop_states=prop_states,
            lighting_state=lighting_state,
            screen_direction="preserve established left-right and travel direction",
            incoming_requirements=tuple(dict.fromkeys(incoming)),
            outgoing_state=outgoing,
        )
