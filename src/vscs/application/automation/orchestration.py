"""Human acceptance and deterministic auto-compilation orchestration for Phase 19.5.10."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.story import (
    EpisodePlan,
    EpisodePlanningError,
    EpisodePlanningService,
    EpisodePlanStatus,
    GovernedShotPlanningError,
    GovernedShotPlanningService,
    ScenePlan,
    ScenePlanningError,
    ScenePlanningService,
    ScenePlanStatus,
    ShotPlan,
    ShotPlanStatus,
    build_scene_id,
)

from .contracts import AutomationProposal, AutomationProposalStatus, AutomationProposalType
from .service import AutomationProposalError, AutomationProposalService


class ProposalAcceptanceError(RuntimeError):
    """Raised when human proposal acceptance cannot be completed safely."""


class AutomationCompilationError(RuntimeError):
    """Raised when accepted proposals cannot be compiled safely."""


@dataclass(frozen=True, slots=True)
class ProposalAcceptanceSummary:
    """Result of one explicit human bulk-review/acceptance action."""

    story_id: str
    source_revision: str
    reviewed_by: str
    accepted_now: int
    already_accepted: int
    blocked: int
    rejected: int
    accepted_proposal_ids: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AutoCompilationReport:
    """Persistent report for accepted proposal → governed authority orchestration."""

    story_id: str
    source_revision: str
    compiled_by: str
    compiled_at: str
    accepted_proposals: int
    episodes_created: int
    episodes_reused: int
    scenes_created: int
    scenes_reused: int
    shots_created: int
    shots_reused: int
    ready_promotions: int
    deferred_proposals: int
    blocked_proposals: int
    authority_map: dict[str, str]
    deferred: tuple[str, ...]
    blockers: tuple[str, ...]


class ProposalAcceptanceService:
    """Apply explicit human review/acceptance without creating production authority."""

    def __init__(self, proposals: AutomationProposalService) -> None:
        self.proposals = proposals

    def accept_eligible_current(
        self,
        *,
        story_id: str,
        source_revision: str,
        reviewed_by: str,
        notes: str = "",
    ) -> ProposalAcceptanceSummary:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        reviewer = reviewed_by.strip()
        if not story or not revision:
            raise ValueError("Story ID and source revision are required")
        if not reviewer:
            raise ValueError("Human reviewer identity is required")

        current = tuple(
            item
            for item in self.proposals.list_proposals()
            if item.provenance.source_story_id == story
            and item.provenance.source_revision == revision
        )
        if not current:
            raise ProposalAcceptanceError("No current automation proposals exist to review")

        accepted_now = 0
        already_accepted = 0
        rejected = 0
        accepted_ids: list[str] = []
        blockers: list[str] = []
        review_notes = notes.strip()

        for proposal in sorted(current, key=self._acceptance_order):
            if proposal.status is AutomationProposalStatus.REJECTED:
                rejected += 1
                blockers.append(
                    f"{proposal.proposal_id}: rejected proposal remains excluded from compilation"
                )
                continue
            blocker = self._eligibility_blocker(proposal)
            if blocker:
                blockers.append(f"{proposal.proposal_id}: {blocker}")
                continue
            if proposal.status is AutomationProposalStatus.ACCEPTED:
                already_accepted += 1
                accepted_ids.append(proposal.proposal_id)
                continue
            try:
                current_proposal = proposal
                if proposal.status is AutomationProposalStatus.PROPOSED:
                    current_proposal = self.proposals.mark_reviewed(
                        proposal.proposal_id,
                        reviewed_by=reviewer,
                        notes=review_notes,
                    )
                if current_proposal.status is AutomationProposalStatus.REVIEWED:
                    current_proposal = self.proposals.accept(
                        current_proposal.proposal_id,
                        accepted_by=reviewer,
                    )
                if current_proposal.status is not AutomationProposalStatus.ACCEPTED:
                    raise ProposalAcceptanceError(
                        f"Proposal {proposal.proposal_id} did not reach Accepted state"
                    )
            except (AutomationProposalError, ValueError) as exc:
                blockers.append(f"{proposal.proposal_id}: {exc}")
                continue
            accepted_now += 1
            accepted_ids.append(current_proposal.proposal_id)

        return ProposalAcceptanceSummary(
            story_id=story,
            source_revision=revision,
            reviewed_by=reviewer,
            accepted_now=accepted_now,
            already_accepted=already_accepted,
            blocked=len(blockers),
            rejected=rejected,
            accepted_proposal_ids=tuple(accepted_ids),
            blockers=tuple(blockers),
        )

    @staticmethod
    def _eligibility_blocker(proposal: AutomationProposal) -> str:
        if proposal.proposal_type is AutomationProposalType.ASSET:
            canonical_status = str(proposal.payload.get("canonical_status", "")).strip()
            human_resolution = bool(proposal.payload.get("human_resolution_required"))
            if canonical_status != "resolved" or human_resolution:
                return (
                    "canonical asset is not fully resolved; asset identity must remain under human "
                    "canonical governance"
                )
        if proposal.proposal_type is AutomationProposalType.CONTINUITY:
            conflicts = proposal.payload.get("continuity_conflicts")
            if isinstance(conflicts, list) and conflicts:
                return "continuity conflicts require explicit human resolution before acceptance"
        return ""

    @staticmethod
    def _acceptance_order(proposal: AutomationProposal) -> tuple[int, str, str]:
        order = {
            AutomationProposalType.STORY_INTERPRETATION: 0,
            AutomationProposalType.EPISODE: 1,
            AutomationProposalType.SCENE: 2,
            AutomationProposalType.SHOT: 3,
            AutomationProposalType.ASSET: 4,
            AutomationProposalType.ACTION_PERFORMANCE: 5,
            AutomationProposalType.ENVIRONMENT: 6,
            AutomationProposalType.CAMERA: 7,
            AutomationProposalType.LIGHTING: 8,
            AutomationProposalType.CONTINUITY: 9,
            AutomationProposalType.STYLE: 10,
        }
        return order.get(proposal.proposal_type, 99), proposal.target_id, proposal.proposal_id


class ProposalAutoCompilationOrchestrator:
    """Compile accepted structural proposals through existing governed public services.

    Human acceptance is the authorization event. The orchestrator may create and
    promote Episode, Scene and Shot authority to Ready so the accepted hierarchy can
    become usable by existing downstream planners. It never creates canonical assets,
    never bypasses Shot-to-Asset governance, and never performs final Production
    Review/Approval or provider submission.
    """

    FILE_NAME = "automation_compilation.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        proposals: AutomationProposalService,
        episodes: EpisodePlanningService,
        scenes: ScenePlanningService,
        shots: GovernedShotPlanningService,
    ) -> None:
        self.projects = projects
        self.proposals = proposals
        self.episodes = episodes
        self.scenes = scenes
        self.shots = shots

    @property
    def report_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "automation" / self.FILE_NAME

    def compile_current(
        self,
        *,
        story_id: str,
        source_revision: str,
        compiled_by: str,
    ) -> AutoCompilationReport:
        story = story_id.strip().upper()
        revision = source_revision.strip()
        compiler = compiled_by.strip()
        if not story or not revision:
            raise ValueError("Story ID and source revision are required")
        if not compiler:
            raise ValueError("Human compiler identity is required")

        current = tuple(
            item
            for item in self.proposals.list_proposals()
            if item.provenance.source_story_id == story
            and item.provenance.source_revision == revision
        )
        accepted = tuple(item for item in current if item.consumable)
        if not accepted:
            raise AutomationCompilationError(
                "No human-accepted automation proposals exist for the current Story revision"
            )

        accepted_by_type = {
            proposal_type: tuple(
                item for item in accepted if item.proposal_type is proposal_type
            )
            for proposal_type in AutomationProposalType
        }
        authority_map: dict[str, str] = {}
        blockers: list[str] = []
        deferred: list[str] = []
        episodes_created = 0
        episodes_reused = 0
        scenes_created = 0
        scenes_reused = 0
        shots_created = 0
        shots_reused = 0
        ready_promotions = 0

        for proposal in sorted(
            accepted_by_type[AutomationProposalType.EPISODE],
            key=self._sequence_sort,
        ):
            try:
                created, promoted, governed_id = self._compile_episode(story, proposal)
                episodes_created += int(created)
                episodes_reused += int(not created)
                ready_promotions += int(promoted)
                authority_map[proposal.target_id] = governed_id
            except (AutomationCompilationError, EpisodePlanningError, ValueError, TypeError) as exc:
                blockers.append(f"{proposal.proposal_id}: {exc}")

        for proposal in sorted(
            accepted_by_type[AutomationProposalType.SCENE],
            key=self._scene_sort,
        ):
            try:
                created, promoted, governed_id = self._compile_scene(proposal, authority_map)
                scenes_created += int(created)
                scenes_reused += int(not created)
                ready_promotions += int(promoted)
                authority_map[proposal.target_id] = governed_id
            except (AutomationCompilationError, ScenePlanningError, ValueError, TypeError) as exc:
                blockers.append(f"{proposal.proposal_id}: {exc}")

        for proposal in sorted(
            accepted_by_type[AutomationProposalType.SHOT],
            key=self._shot_sort,
        ):
            try:
                created, promoted, governed_id = self._compile_shot(proposal, authority_map)
                shots_created += int(created)
                shots_reused += int(not created)
                ready_promotions += int(promoted)
                authority_map[proposal.target_id] = governed_id
            except (
                AutomationCompilationError,
                GovernedShotPlanningError,
                ValueError,
                TypeError,
            ) as exc:
                blockers.append(f"{proposal.proposal_id}: {exc}")

        for proposal in accepted:
            if proposal.proposal_type in {
                AutomationProposalType.STORY_INTERPRETATION,
                AutomationProposalType.EPISODE,
                AutomationProposalType.SCENE,
                AutomationProposalType.SHOT,
            }:
                continue
            mapped_target = authority_map.get(proposal.target_id, proposal.target_id)
            if proposal.proposal_type is AutomationProposalType.ASSET:
                reason = (
                    "canonical entity resolution is accepted, but Shot-scoped asset binding remains "
                    "deferred because Phase 19.5.5 does not establish per-Shot asset usage"
                )
            else:
                reason = (
                    "accepted specialist proposal is deferred until governed Shot asset-resolution "
                    "prerequisites are satisfied; orchestration will not bypass existing planner gates"
                )
            deferred.append(
                f"{proposal.proposal_type.value}:{proposal.proposal_id}:{mapped_target}: {reason}"
            )

        unresolved_current = tuple(
            item
            for item in current
            if item.status is not AutomationProposalStatus.ACCEPTED
            and item.proposal_type
            in {
                AutomationProposalType.ASSET,
                AutomationProposalType.CONTINUITY,
            }
        )
        for proposal in unresolved_current:
            reason = ProposalAcceptanceService._eligibility_blocker(proposal)
            if reason:
                blockers.append(f"{proposal.proposal_id}: {reason}")

        report = AutoCompilationReport(
            story_id=story,
            source_revision=revision,
            compiled_by=compiler,
            compiled_at=datetime.now(UTC).isoformat(),
            accepted_proposals=len(accepted),
            episodes_created=episodes_created,
            episodes_reused=episodes_reused,
            scenes_created=scenes_created,
            scenes_reused=scenes_reused,
            shots_created=shots_created,
            shots_reused=shots_reused,
            ready_promotions=ready_promotions,
            deferred_proposals=len(deferred),
            blocked_proposals=len(blockers),
            authority_map=dict(sorted(authority_map.items())),
            deferred=tuple(deferred),
            blockers=tuple(blockers),
        )
        self._write_report(report)
        return report

    def last_report(self) -> AutoCompilationReport | None:
        path = self.report_file
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            report = dict(raw["report"])
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AutomationCompilationError(f"Unable to load automation compilation report: {exc}") from exc
        report["authority_map"] = {
            str(key): str(value) for key, value in dict(report.get("authority_map", {})).items()
        }
        report["deferred"] = tuple(str(value) for value in report.get("deferred", []))
        report["blockers"] = tuple(str(value) for value in report.get("blockers", []))
        return AutoCompilationReport(**report)

    def _compile_episode(
        self,
        story_id: str,
        proposal: AutomationProposal,
    ) -> tuple[bool, bool, str]:
        payload = proposal.payload
        sequence = self._integer(payload, "sequence_number")
        expected_id = f"EP-{sequence:03d}"
        if proposal.target_id != expected_id:
            raise AutomationCompilationError(
                f"Episode proposal target {proposal.target_id} does not match canonical {expected_id}"
            )
        existing = self.episodes.plan(expected_id)
        if existing is None:
            existing = self.episodes.create(
                story_id=story_id,
                sequence_number=sequence,
                title=self._string(payload, "title"),
                story_scope=self._string(payload, "story_scope"),
                production_objective=self._string(payload, "production_objective"),
                target_runtime_seconds=self._integer(payload, "target_runtime_seconds"),
                continuity_in=str(payload.get("continuity_in", "")),
                continuity_out=str(payload.get("continuity_out", "")),
                production_constraints=self._strings(payload.get("production_constraints")),
            )
            ready = self.episodes.mark_ready(existing.episode_id)
            return True, ready.status is EpisodePlanStatus.READY, ready.episode_id
        self._require_episode_match(existing, proposal)
        if existing.status is EpisodePlanStatus.READY:
            return False, False, existing.episode_id
        ready = self.episodes.mark_ready(existing.episode_id)
        return False, ready.status is EpisodePlanStatus.READY, ready.episode_id

    def _compile_scene(
        self,
        proposal: AutomationProposal,
        authority_map: dict[str, str],
    ) -> tuple[bool, bool, str]:
        payload = proposal.payload
        parent_proposal_id = self._string(payload, "episode_id")
        governed_episode_id = authority_map.get(parent_proposal_id)
        if not governed_episode_id:
            raise AutomationCompilationError(
                f"Parent Episode proposal {parent_proposal_id} has not compiled to governed authority"
            )
        sequence = self._integer(payload, "sequence_number")
        governed_scene_id = build_scene_id(governed_episode_id, sequence)
        existing = self.scenes.plan(governed_scene_id)
        if existing is None:
            existing = self.scenes.create(
                episode_id=governed_episode_id,
                sequence_number=sequence,
                title=self._string(payload, "title"),
                story_scope=self._string(payload, "story_scope"),
                production_objective=self._string(payload, "production_objective"),
                target_runtime_seconds=self._integer(payload, "target_runtime_seconds"),
                setting_requirement=self._string(payload, "setting_requirement"),
                required_events=self._strings(payload.get("required_events")),
                continuity_in=str(payload.get("continuity_in", "")),
                continuity_out=str(payload.get("continuity_out", "")),
                scene_constraints=self._strings(payload.get("scene_constraints")),
            )
            ready = self.scenes.mark_ready(existing.scene_id)
            return True, ready.status is ScenePlanStatus.READY, ready.scene_id
        self._require_scene_match(existing, proposal, governed_episode_id)
        if existing.status is ScenePlanStatus.READY:
            return False, False, existing.scene_id
        ready = self.scenes.mark_ready(existing.scene_id)
        return False, ready.status is ScenePlanStatus.READY, ready.scene_id

    def _compile_shot(
        self,
        proposal: AutomationProposal,
        authority_map: dict[str, str],
    ) -> tuple[bool, bool, str]:
        payload = proposal.payload
        parent_proposal_id = self._string(payload, "scene_id")
        governed_scene_id = authority_map.get(parent_proposal_id)
        if not governed_scene_id:
            raise AutomationCompilationError(
                f"Parent Scene proposal {parent_proposal_id} has not compiled to governed authority"
            )
        sequence = self._integer(payload, "sequence_number")
        expected_id = f"{governed_scene_id}-SHT-{sequence:03d}"
        existing = self.shots.plan(expected_id)
        if existing is None:
            existing = self.shots.create(
                scene_id=governed_scene_id,
                sequence_number=sequence,
                title=self._string(payload, "title"),
                narrative_purpose=self._string(payload, "narrative_purpose"),
                production_objective=self._string(payload, "production_objective"),
                target_runtime_seconds=self._integer(payload, "target_runtime_seconds"),
                required_action=self._string(payload, "required_action"),
                dialogue_requirement=str(payload.get("dialogue_requirement", "")),
                continuity_in=str(payload.get("continuity_in", "")),
                continuity_out=str(payload.get("continuity_out", "")),
                shot_constraints=self._strings(payload.get("shot_constraints")),
            )
            ready = self.shots.mark_ready(existing.shot_id)
            return True, ready.status is ShotPlanStatus.READY, ready.shot_id
        self._require_shot_match(existing, proposal, governed_scene_id)
        if existing.status is ShotPlanStatus.READY:
            return False, False, existing.shot_id
        ready = self.shots.mark_ready(existing.shot_id)
        return False, ready.status is ShotPlanStatus.READY, ready.shot_id

    def _require_episode_match(self, plan: EpisodePlan, proposal: AutomationProposal) -> None:
        payload = proposal.payload
        expected = (
            self._integer(payload, "sequence_number"),
            self._string(payload, "title"),
            self._string(payload, "story_scope"),
            self._string(payload, "production_objective"),
            self._integer(payload, "target_runtime_seconds"),
            str(payload.get("continuity_in", "")).strip(),
            str(payload.get("continuity_out", "")).strip(),
            self._strings(payload.get("production_constraints")),
        )
        actual = (
            plan.sequence_number,
            plan.title,
            plan.story_scope,
            plan.production_objective,
            plan.target_runtime_seconds,
            plan.continuity_in,
            plan.continuity_out,
            plan.production_constraints,
        )
        if actual != expected:
            raise AutomationCompilationError(
                f"Existing Episode authority {plan.episode_id} differs from the accepted proposal; "
                "orchestration will not overwrite human-governed authority"
            )

    def _require_scene_match(
        self,
        plan: ScenePlan,
        proposal: AutomationProposal,
        governed_episode_id: str,
    ) -> None:
        payload = proposal.payload
        expected = (
            governed_episode_id,
            self._integer(payload, "sequence_number"),
            self._string(payload, "title"),
            self._string(payload, "story_scope"),
            self._string(payload, "production_objective"),
            self._integer(payload, "target_runtime_seconds"),
            self._string(payload, "setting_requirement"),
            self._strings(payload.get("required_events")),
            str(payload.get("continuity_in", "")).strip(),
            str(payload.get("continuity_out", "")).strip(),
            self._strings(payload.get("scene_constraints")),
        )
        actual = (
            plan.episode_id,
            plan.sequence_number,
            plan.title,
            plan.story_scope,
            plan.production_objective,
            plan.target_runtime_seconds,
            plan.setting_requirement,
            plan.required_events,
            plan.continuity_in,
            plan.continuity_out,
            plan.scene_constraints,
        )
        if actual != expected:
            raise AutomationCompilationError(
                f"Existing Scene authority {plan.scene_id} differs from the accepted proposal; "
                "orchestration will not overwrite human-governed authority"
            )

    def _require_shot_match(
        self,
        plan: ShotPlan,
        proposal: AutomationProposal,
        governed_scene_id: str,
    ) -> None:
        payload = proposal.payload
        expected = (
            governed_scene_id,
            self._integer(payload, "sequence_number"),
            self._string(payload, "title"),
            self._string(payload, "narrative_purpose"),
            self._string(payload, "production_objective"),
            self._integer(payload, "target_runtime_seconds"),
            self._string(payload, "required_action"),
            str(payload.get("dialogue_requirement", "")).strip(),
            str(payload.get("continuity_in", "")).strip(),
            str(payload.get("continuity_out", "")).strip(),
            self._strings(payload.get("shot_constraints")),
        )
        actual = (
            plan.scene_id,
            plan.sequence_number,
            plan.title,
            plan.narrative_purpose,
            plan.production_objective,
            plan.target_runtime_seconds,
            plan.required_action,
            plan.dialogue_requirement,
            plan.continuity_in,
            plan.continuity_out,
            plan.shot_constraints,
        )
        if actual != expected:
            raise AutomationCompilationError(
                f"Existing Shot authority {plan.shot_id} differs from the accepted proposal; "
                "orchestration will not overwrite human-governed authority"
            )

    def _write_report(self, report: AutoCompilationReport) -> None:
        path = self.report_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "report": asdict(report),
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise AutomationCompilationError(
                f"Unable to save automation compilation report: {exc}"
            ) from exc

    @staticmethod
    def _integer(payload: dict[str, object], key: str) -> int:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise AutomationCompilationError(f"Proposal field {key} must be an integer")
        return value

    @staticmethod
    def _string(payload: dict[str, object], key: str) -> str:
        value = str(payload.get(key, "")).strip()
        if not value:
            raise AutomationCompilationError(f"Proposal field {key} is required")
        return value

    @staticmethod
    def _strings(value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            normalized = value.strip()
            return (normalized,) if normalized else ()
        if not isinstance(value, (list, tuple)):
            return ()
        return tuple(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))

    @staticmethod
    def _sequence_sort(proposal: AutomationProposal) -> tuple[int, str]:
        value = proposal.payload.get("sequence_number")
        sequence = value if isinstance(value, int) and not isinstance(value, bool) else 0
        return sequence, proposal.target_id

    @staticmethod
    def _scene_sort(proposal: AutomationProposal) -> tuple[str, int, str]:
        episode_id = str(proposal.payload.get("episode_id", ""))
        sequence, target_id = ProposalAutoCompilationOrchestrator._sequence_sort(proposal)
        return episode_id, sequence, target_id

    @staticmethod
    def _shot_sort(proposal: AutomationProposal) -> tuple[str, int, str]:
        scene_id = str(proposal.payload.get("scene_id", ""))
        sequence, target_id = ProposalAutoCompilationOrchestrator._sequence_sort(proposal)
        return scene_id, sequence, target_id
