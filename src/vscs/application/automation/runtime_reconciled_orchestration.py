"""Runtime-reconciled Phase 19.5.10 auto-compilation orchestration."""

from __future__ import annotations

from dataclasses import replace

from vscs.application.projects import ProjectService
from vscs.application.story import (
    EpisodePlanningService,
    GovernedShotPlanningService,
    ScenePlanningService,
    ShotPlan,
    ShotPlanStatus,
)

from .contracts import AutomationProposal, AutomationProposalType
from .orchestration import (
    AutoCompilationReport,
    AutomationCompilationError,
)
from .orchestration import (
    ProposalAutoCompilationOrchestrator as BaseProposalAutoCompilationOrchestrator,
)
from .runtime_budget import fit_positive_runtimes_to_budget
from .service import AutomationProposalService


class ProposalAutoCompilationOrchestrator(BaseProposalAutoCompilationOrchestrator):
    """Compile accepted structure after deterministic Scene-budget reconciliation.

    Phase 19.5.4 defines Shot runtimes as proposal-stage estimates and proportionally
    fits them into the parent Scene budget. Repeated proposal generation in early
    Phase 19.5 builds could leave a coherent accepted Shot identity set whose stored
    estimates no longer sum to the current Scene budget. This wrapper applies the
    same deterministic fitting policy to the complete accepted set before governed
    materialisation. It never relaxes the governed Shot Planner budget.

    If a previous Phase 19.5.10 run already created some of those governed Shots,
    only authority recorded in that run's authority map may be reconciled. Any
    differing/unowned governed authority remains protected as human authority.
    """

    def __init__(
        self,
        projects: ProjectService,
        proposals: AutomationProposalService,
        episodes: EpisodePlanningService,
        scenes: ScenePlanningService,
        shots: GovernedShotPlanningService,
    ) -> None:
        super().__init__(projects, proposals, episodes, scenes, shots)
        self._runtime_overrides: dict[str, int] = {}

    def compile_current(
        self,
        *,
        story_id: str,
        source_revision: str,
        compiled_by: str,
    ) -> AutoCompilationReport:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        accepted = tuple(
            proposal
            for proposal in self.proposals.list_proposals()
            if proposal.provenance.source_story_id == story
            and proposal.provenance.source_revision == revision
            and proposal.consumable
        )
        self._runtime_overrides = self._build_runtime_overrides(accepted)
        try:
            self._reconcile_previous_automation_shots(
                story_id=story,
                source_revision=revision,
                accepted=accepted,
            )
            return super().compile_current(
                story_id=story,
                source_revision=revision,
                compiled_by=compiled_by,
            )
        finally:
            self._runtime_overrides = {}

    def _compile_shot(
        self,
        proposal: AutomationProposal,
        authority_map: dict[str, str],
    ) -> tuple[bool, bool, str]:
        runtime = self._runtime_overrides.get(proposal.proposal_id)
        if runtime is None:
            raise AutomationCompilationError(
                f"No reconciled runtime exists for accepted Shot {proposal.proposal_id}"
            )
        normalized = replace(
            proposal,
            payload={**proposal.payload, "target_runtime_seconds": runtime},
        )
        return super()._compile_shot(normalized, authority_map)

    def _build_runtime_overrides(
        self,
        accepted: tuple[AutomationProposal, ...],
    ) -> dict[str, int]:
        scenes = {
            proposal.target_id: proposal
            for proposal in accepted
            if proposal.proposal_type is AutomationProposalType.SCENE
        }
        shots = tuple(
            proposal
            for proposal in accepted
            if proposal.proposal_type is AutomationProposalType.SHOT
        )
        overrides: dict[str, int] = {}
        by_scene: dict[str, list[AutomationProposal]] = {}
        for shot in shots:
            scene_id = str(shot.payload.get("scene_id", "")).strip().upper()
            by_scene.setdefault(scene_id, []).append(shot)

        for scene_id, scene_shots in by_scene.items():
            scene = scenes.get(scene_id)
            if scene is None:
                raise AutomationCompilationError(
                    f"Accepted Shot set references Scene proposal {scene_id} which is not accepted"
                )
            budget = self._integer(scene.payload, "target_runtime_seconds")
            ordered = sorted(scene_shots, key=self._sequence_sort)
            sequence = tuple(self._integer(shot.payload, "sequence_number") for shot in ordered)
            if sequence != tuple(range(1, len(ordered) + 1)):
                raise AutomationCompilationError(
                    f"Accepted Shots for {scene_id} must use contiguous sequence numbers"
                )
            estimates = tuple(
                self._integer(shot.payload, "target_runtime_seconds") for shot in ordered
            )
            try:
                fitted = fit_positive_runtimes_to_budget(estimates, budget)
            except ValueError as exc:
                raise AutomationCompilationError(
                    f"Accepted Shots for {scene_id} cannot fit the Scene runtime budget: {exc}"
                ) from exc
            overrides.update(
                {shot.proposal_id: runtime for shot, runtime in zip(ordered, fitted, strict=True)}
            )
        return overrides

    def _reconcile_previous_automation_shots(
        self,
        *,
        story_id: str,
        source_revision: str,
        accepted: tuple[AutomationProposal, ...],
    ) -> None:
        try:
            previous = self.last_report()
        except AutomationCompilationError:
            previous = None
        if (
            previous is None
            or previous.story_id != story_id
            or previous.source_revision != source_revision
        ):
            return

        accepted_shots = tuple(
            proposal
            for proposal in accepted
            if proposal.proposal_type is AutomationProposalType.SHOT
        )
        changes: list[tuple[AutomationProposal, ShotPlan, int]] = []
        for proposal in accepted_shots:
            governed_id = previous.authority_map.get(proposal.target_id)
            if not governed_id:
                continue
            plan = self.shots.plan(governed_id)
            if plan is None:
                continue
            desired_runtime = self._runtime_overrides[proposal.proposal_id]
            if plan.target_runtime_seconds == desired_runtime:
                continue
            self._require_automation_owned_shot(plan, proposal)
            changes.append((proposal, plan, desired_runtime))

        if not changes:
            return

        for _proposal, plan, _runtime in changes:
            if plan.status is ShotPlanStatus.READY:
                self.shots.return_to_draft(plan.shot_id)

        for proposal, plan, desired_runtime in sorted(
            changes,
            key=lambda item: (item[2] - item[1].target_runtime_seconds, item[1].shot_id),
        ):
            payload = proposal.payload
            self.shots.update(
                plan.shot_id,
                title=self._string(payload, "title"),
                narrative_purpose=self._string(payload, "narrative_purpose"),
                production_objective=self._string(payload, "production_objective"),
                target_runtime_seconds=desired_runtime,
                required_action=self._string(payload, "required_action"),
                dialogue_requirement=str(payload.get("dialogue_requirement", "")),
                continuity_in=str(payload.get("continuity_in", "")),
                continuity_out=str(payload.get("continuity_out", "")),
                shot_constraints=self._strings(payload.get("shot_constraints")),
            )

        for _proposal, plan, _runtime in changes:
            self.shots.mark_ready(plan.shot_id)

    def _require_automation_owned_shot(
        self,
        plan: ShotPlan,
        proposal: AutomationProposal,
    ) -> None:
        payload = proposal.payload
        original_runtime = self._integer(payload, "target_runtime_seconds")
        expected_without_runtime = (
            self._integer(payload, "sequence_number"),
            self._string(payload, "title"),
            self._string(payload, "narrative_purpose"),
            self._string(payload, "production_objective"),
            self._string(payload, "required_action"),
            str(payload.get("dialogue_requirement", "")).strip(),
            str(payload.get("continuity_in", "")).strip(),
            str(payload.get("continuity_out", "")).strip(),
            self._strings(payload.get("shot_constraints")),
        )
        actual_without_runtime = (
            plan.sequence_number,
            plan.title,
            plan.narrative_purpose,
            plan.production_objective,
            plan.required_action,
            plan.dialogue_requirement,
            plan.continuity_in,
            plan.continuity_out,
            plan.shot_constraints,
        )
        if actual_without_runtime != expected_without_runtime:
            raise AutomationCompilationError(
                f"Existing Shot authority {plan.shot_id} differs from its previously compiled "
                "automation proposal; runtime reconciliation will not overwrite human edits"
            )
        desired_runtime = self._runtime_overrides[proposal.proposal_id]
        if plan.target_runtime_seconds not in {original_runtime, desired_runtime}:
            raise AutomationCompilationError(
                f"Existing Shot authority {plan.shot_id} has a runtime not owned by this accepted "
                "proposal; runtime reconciliation will not overwrite human authority"
            )
