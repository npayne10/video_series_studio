"""Scene → Shot proposal automation above governed Shot Planning authority."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Protocol

from vscs.domain.story_analysis import AnalysisResult

from .contracts import (
    AutomationProposal,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class ShotProposalDraft:
    """Provider-neutral narrative Shot proposal, never governed Shot authority."""

    sequence_number: int
    title: str
    narrative_purpose: str
    production_objective: str
    target_runtime_seconds: int
    required_action: str
    dialogue_requirement: str = ""
    continuity_in: str = ""
    continuity_out: str = ""
    shot_constraints: tuple[str, ...] = ()
    confidence: float = 0.5


@dataclass(frozen=True, slots=True)
class SceneShotProposalDraft:
    """Complete provider response for one proposed Scene."""

    shots: tuple[ShotProposalDraft, ...]
    diagnostics: tuple[str, ...] = ()


class SceneShotProposalProvider(Protocol):
    """Semantic boundary for Scene proposal → Shot proposal decomposition."""

    provider_name: str
    model_name: str

    def propose_scene_shots(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        scene_payload: dict[str, object],
    ) -> SceneShotProposalDraft:
        """Return reviewable Shot proposals only."""


class TemplateSceneShotProposalProvider:
    """Deterministic offline Scene decomposition for tests and development."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose_scene_shots(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        scene_payload: dict[str, object],
    ) -> SceneShotProposalDraft:
        del story_id, source_text, baseline
        scene_runtime = max(1, self._integer(scene_payload.get("target_runtime_seconds"), 60))
        events = self._strings(scene_payload.get("required_events"))
        if not events:
            fallback = (
                str(scene_payload.get("story_scope", "")).strip() or "Present the Scene intent"
            )
            events = (fallback,)
        if scene_runtime < len(events):
            events = events[:scene_runtime]

        constraints = self._strings(scene_payload.get("scene_constraints"))
        count = len(events)
        base_runtime = max(1, scene_runtime // count)
        remaining = scene_runtime
        shots: list[ShotProposalDraft] = []
        for index, event in enumerate(events, start=1):
            runtime = (
                remaining if index == count else min(base_runtime, remaining - (count - index))
            )
            remaining -= runtime
            shots.append(
                ShotProposalDraft(
                    sequence_number=index,
                    title=f"Shot {index}",
                    narrative_purpose=event,
                    production_objective=f"Present the required Scene event: {event}",
                    target_runtime_seconds=max(1, runtime),
                    required_action=event,
                    continuity_in=(
                        "Continue from the preceding Shot state"
                        if index > 1
                        else str(scene_payload.get("continuity_in", "")).strip()
                    ),
                    continuity_out=(
                        str(scene_payload.get("continuity_out", "")).strip()
                        if index == count
                        else "Carry visual and narrative state into the next Shot"
                    ),
                    shot_constraints=constraints,
                    confidence=0.6,
                )
            )
        return SceneShotProposalDraft(
            shots=tuple(shots),
            diagnostics=("Deterministic Scene/Shot proposal provider used",),
        )

    @staticmethod
    def _integer(value: object, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    @staticmethod
    def _strings(value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            normalized = value.strip()
            return (normalized,) if normalized else ()
        if not isinstance(value, Iterable):
            return ()
        return tuple(normalized for item in value if (normalized := str(item).strip()))


class SceneShotProposalAutomationService:
    """Generate policy-compliant Shot proposals without creating governed Shot Plans."""

    MIN_SHOT_SECONDS = 15
    MAX_SHOT_SECONDS = 20

    def __init__(
        self,
        provider: SceneShotProposalProvider,
        proposals: AutomationProposalService,
    ) -> None:
        self._provider = provider
        self._proposals = proposals

    def generate(
        self,
        *,
        story_id: str,
        source_text: str,
        source_revision: str,
        baseline: AnalysisResult,
    ) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision or not source_text.strip():
            raise ValueError("Story ID, source revision and source text are required")
        if baseline.story_id.strip().upper() != normalized_story:
            raise ValueError("Scene/Shot baseline belongs to another Story")
        if baseline.source_revision and baseline.source_revision != revision:
            raise ValueError("Scene/Shot baseline is stale for this Story revision")

        scene_proposals = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.proposal_type is AutomationProposalType.SCENE
            and proposal.provenance.source_story_id == normalized_story
            and proposal.provenance.source_revision == revision
        )
        if not scene_proposals:
            raise ValueError(
                "Generate current Episode/Scene proposals before generating Shot proposals"
            )

        existing_shots = tuple(
            proposal
            for proposal in self._proposals.list_proposals()
            if proposal.proposal_type is AutomationProposalType.SHOT
            and proposal.provenance.source_story_id == normalized_story
            and proposal.provenance.source_revision == revision
        )
        if any(
            proposal.status is not AutomationProposalStatus.PROPOSED
            for proposal in existing_shots
        ):
            raise ValueError(
                "Cannot regenerate Shot proposals after human review, acceptance or "
                "rejection. Preserve the proposal history and use a governed "
                "revision/recovery workflow."
            )

        # Reject impossible Scene budgets before an optional paid AI provider call.
        for scene in scene_proposals:
            runtime = self._scene_runtime(scene)
            minimum_shots = (runtime + self.MAX_SHOT_SECONDS - 1) // self.MAX_SHOT_SECONDS
            maximum_shots = runtime // self.MIN_SHOT_SECONDS
            if runtime <= 0 or minimum_shots > maximum_shots:
                raise ValueError(
                    f"Scene {scene.target_id} has an unpartitionable {runtime}s runtime "
                    f"under the {self.MIN_SHOT_SECONDS}–{self.MAX_SHOT_SECONDS}s Shot policy. "
                    "Review the Scene budget before invoking a provider."
                )

        generated: list[AutomationProposal] = []
        for scene in sorted(scene_proposals, key=lambda item: item.target_id):
            draft = self._provider.propose_scene_shots(
                story_id=normalized_story,
                source_text=source_text,
                baseline=baseline,
                scene_payload=scene.payload,
            )
            if not draft.shots:
                raise ValueError(f"Scene/Shot provider returned no Shots for {scene.target_id}")
            draft = self._fit_runtime_budget(scene, draft)
            draft = self._rebalance_provider_runtimes(scene, draft)
            draft = self._enforce_shot_duration_policy(scene, draft)
            self._validate_runtime_budget(scene, draft)
            previous = tuple(
                proposal
                for proposal in existing_shots
                if proposal.target_id.startswith(f"{scene.target_id}-SHT-")
            )
            if len(previous) > len(draft.shots):
                raise ValueError(
                    f"Scene {scene.target_id} already has {len(previous)} proposed Shots; "
                    "the corrected generation would leave stale orphan proposals. "
                    "Use a governed proposal-set replacement before regenerating."
                )
            for shot in draft.shots:
                generated.append(
                    self._proposals.save(
                        self._shot_proposal(
                            story_id=normalized_story,
                            revision=revision,
                            source_text=source_text,
                            scene=scene,
                            shot=shot,
                            diagnostics=draft.diagnostics,
                        )
                    )
                )
        return tuple(generated)

    def _shot_proposal(
        self,
        *,
        story_id: str,
        revision: str,
        source_text: str,
        scene: AutomationProposal,
        shot: ShotProposalDraft,
        diagnostics: tuple[str, ...],
    ) -> AutomationProposal:
        target_id = f"{scene.target_id}-SHT-{shot.sequence_number:03d}"
        proposal_id = self._proposal_id(story_id, revision, scene.target_id, target_id)
        return AutomationProposal(
            proposal_id=proposal_id,
            proposal_type=AutomationProposalType.SHOT,
            target_id=target_id,
            payload={
                "scene_id": scene.target_id,
                "sequence_number": shot.sequence_number,
                "title": shot.title,
                "narrative_purpose": shot.narrative_purpose,
                "production_objective": shot.production_objective,
                "target_runtime_seconds": shot.target_runtime_seconds,
                "required_action": shot.required_action,
                "dialogue_requirement": shot.dialogue_requirement,
                "continuity_in": shot.continuity_in,
                "continuity_out": shot.continuity_out,
                "shot_constraints": list(shot.shot_constraints),
                "diagnostics": list(diagnostics),
            },
            provenance=self._provenance(
                story_id=story_id,
                revision=revision,
                confidence=shot.confidence,
            ),
            metadata={
                "phase": "19.5.4",
                "parent_scene_proposal_id": scene.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )

    def _provenance(
        self,
        *,
        story_id: str,
        revision: str,
        confidence: float,
    ) -> AutomationProvenance:
        source_kind = (
            AutomationSourceKind.AI_INFERENCE
            if self._provider.provider_name != "vscs-template"
            else AutomationSourceKind.DETERMINISTIC_RESOLUTION
        )
        return AutomationProvenance(
            source_kind=source_kind,
            source_story_id=story_id,
            source_revision=revision,
            source_scope="current Phase 19.5.3 Scene proposal plus Story Analysis context",
            provider=self._provider.provider_name,
            model=self._provider.model_name,
            confidence=max(0.0, min(1.0, confidence)),
            inference_note=(
                "Shot structure is proposed for human review. It does not create, mark Ready, "
                "or approve governed Shot Planning authority."
            ),
            resolution_method="semantic Scene decomposition using existing Story Analysis context",
        )

    @classmethod
    def _fit_runtime_budget(
        cls,
        scene: AutomationProposal,
        draft: SceneShotProposalDraft,
    ) -> SceneShotProposalDraft:
        """Scale positive provider runtimes into the Scene budget without changing Shot intent."""
        scene_runtime = cls._scene_runtime(scene)
        if scene_runtime <= 0:
            raise ValueError(f"Scene proposal {scene.target_id} has no valid runtime budget")
        if scene_runtime < len(draft.shots):
            raise ValueError(
                f"Scene proposal {scene.target_id} runtime is too short for "
                f"{len(draft.shots)} positive-runtime Shot proposals"
            )

        runtimes = tuple(shot.target_runtime_seconds for shot in draft.shots)
        if any(runtime <= 0 for runtime in runtimes):
            raise ValueError(f"Shot proposals for {scene.target_id} require positive runtimes")
        total = sum(runtimes)
        if total <= scene_runtime:
            return draft

        # Runtime is an estimate at proposal stage. Preserve the provider's relative pacing while
        # fitting it to the authoritative parent proposal budget. Largest-remainder allocation gives
        # every Shot at least one second and produces a deterministic exact Scene total.
        distributable = scene_runtime - len(runtimes)
        weights = tuple(runtime / total for runtime in runtimes)
        raw_extra = tuple(weight * distributable for weight in weights)
        extras = [int(value) for value in raw_extra]
        remainder = distributable - sum(extras)
        order = sorted(
            range(len(extras)),
            key=lambda index: (raw_extra[index] - extras[index], -index),
            reverse=True,
        )
        for index in order[:remainder]:
            extras[index] += 1

        fitted = tuple(
            replace(shot, target_runtime_seconds=1 + extras[index])
            for index, shot in enumerate(draft.shots)
        )
        diagnostic = (
            f"Provider Shot runtimes totalled {total}s and were proportionally fitted to the "
            f"{scene_runtime}s Scene proposal budget."
        )
        return SceneShotProposalDraft(
            shots=fitted,
            diagnostics=(*draft.diagnostics, diagnostic),
        )

    @classmethod
    def _feasible_shot_duration(cls, seconds: int) -> bool:
        """A duration can be divided exactly into compliant generation segments."""
        if seconds < cls.MIN_SHOT_SECONDS:
            return False
        min_count = (seconds + cls.MAX_SHOT_SECONDS - 1) // cls.MAX_SHOT_SECONDS
        max_count = seconds // cls.MIN_SHOT_SECONDS
        return min_count <= max_count

    @classmethod
    def _rebalance_provider_runtimes(
        cls,
        scene: AutomationProposal,
        draft: SceneShotProposalDraft,
    ) -> SceneShotProposalDraft:
        """Adjust neighboring narrative durations only when required for Shot policy.

        Preserve the total Scene runtime and the existing order of distinct actions.
        If no safe pairwise adjustment exists, fail before persisting proposals.
        """
        durations = [shot.target_runtime_seconds for shot in draft.shots]
        if sum(durations) != cls._scene_runtime(scene):
            return draft
        original = tuple(durations)
        for index, seconds in enumerate(durations):
            if cls._feasible_shot_duration(seconds):
                continue
            adjustments: list[tuple[int, int, int]] = []
            for neighbor, available in enumerate(durations):
                if neighbor == index:
                    continue
                for delta in range(-cls.MAX_SHOT_SECONDS, cls.MAX_SHOT_SECONDS + 1):
                    if not delta:
                        continue
                    if (
                        cls._feasible_shot_duration(seconds + delta)
                        and cls._feasible_shot_duration(available - delta)
                    ):
                        adjustments.append((abs(delta), neighbor, delta))
            if not adjustments:
                raise ValueError(
                    f"Scene {scene.target_id} contains a {seconds}s provider Shot that "
                    "cannot be rebalanced into the 15–20s policy without changing "
                    "narrative ownership. Review the Scene pacing."
                )
            _size, neighbor, delta = min(adjustments)
            durations[index] += delta
            durations[neighbor] -= delta
        if all(cls._feasible_shot_duration(value) for value in durations):
            if tuple(durations) == original:
                return draft
            detail = ", ".join(
                f"{before}s→{after}s"
                for before, after in zip(original, durations, strict=True)
            )
            return SceneShotProposalDraft(
                shots=tuple(
                    replace(shot, target_runtime_seconds=duration)
                    for shot, duration in zip(draft.shots, durations, strict=True)
                ),
                diagnostics=(
                    *draft.diagnostics,
                    f"VSCS rebalanced provider narrative runtimes ({detail}) to meet "
                    "15–20s clip constraints without changing Scene duration; "
                    "human review is required.",
                ),
            )
        raise ValueError(
            f"Scene {scene.target_id} contains noncompliant provider Shot runtimes "
            "after attempted rebalancing."
        )

    @classmethod
    def _enforce_shot_duration_policy(
        cls,
        scene: AutomationProposal,
        draft: SceneShotProposalDraft,
    ) -> SceneShotProposalDraft:
        """Split oversized Shots while assigning narrative actions to one segment only.

        Never duplicate a one-time event across the continuation segments. Reject
        under-budget and mathematically impossible durations, instead of approving
        an unrenderable Shot or silently altering the approved Scene duration.
        """
        expected = cls._scene_runtime(scene)
        total = sum(shot.target_runtime_seconds for shot in draft.shots)
        if total != expected:
            raise ValueError(
                f"Scene {scene.target_id} requires {expected}s of Shot proposals; "
                f"the provider supplied {total}s. No Shot authority was created."
            )

        result: list[ShotProposalDraft] = []
        split_count = 0
        for shot in draft.shots:
            runtime = shot.target_runtime_seconds
            if runtime < cls.MIN_SHOT_SECONDS:
                raise ValueError(
                    f"Scene {scene.target_id} has a {runtime}s Shot below the "
                    f"{cls.MIN_SHOT_SECONDS}s minimum; review the Scene pacing."
                )
            if runtime <= cls.MAX_SHOT_SECONDS:
                result.append(replace(shot, sequence_number=len(result) + 1))
                continue
            count = (runtime + cls.MAX_SHOT_SECONDS - 1) // cls.MAX_SHOT_SECONDS
            if count * cls.MIN_SHOT_SECONDS > runtime:
                raise ValueError(
                    f"Cannot split {runtime}s Shot in Scene {scene.target_id} into "
                    f"{cls.MIN_SHOT_SECONDS}–{cls.MAX_SHOT_SECONDS}s segments. "
                    "Revisit the Scene duration or Shot pacing."
                )
            base, extra = divmod(runtime, count)
            durations = tuple(base + (1 if index < extra else 0) for index in range(count))
            split_count += 1
            for index, duration in enumerate(durations):
                first = index == 0
                last = index == count - 1
                result.append(
                    replace(
                        shot,
                        sequence_number=len(result) + 1,
                        title=(
                            shot.title if first else f"{shot.title} — continuation {index + 1}"
                        ),
                        target_runtime_seconds=duration,
                        required_action=(
                            shot.required_action
                            if first
                            else (
                                "Hold the established state from the preceding Shot; "
                                "do not repeat any event, pulse, movement or dialogue."
                            )
                        ),
                        narrative_purpose=(
                            shot.narrative_purpose
                            if first
                            else "Continue observing the established state without a new event."
                        ),
                        production_objective=(
                            shot.production_objective
                            if first
                            else "Preserve visual and asset continuity; do not replay actions."
                        ),
                        dialogue_requirement=shot.dialogue_requirement if first else "",
                        shot_constraints=(
                            shot.shot_constraints
                            if first
                            else tuple(
                                constraint
                                for constraint in shot.shot_constraints
                                if not any(
                                    event_word in constraint.casefold()
                                    for event_word in ("pulse", "once", "repeat")
                                )
                            )
                            + ("Do not replay the preceding Shot's one-time events.",)
                        ),
                        continuity_in=(
                            shot.continuity_in
                            if first
                            else "Maintain precisely the preceding Shot end state."
                        ),
                        continuity_out=(
                            shot.continuity_out
                            if last
                            else "Continue the same scene and asset state without resetting."
                        ),
                    )
                )
        if any(
            not cls.MIN_SHOT_SECONDS <= shot.target_runtime_seconds <= cls.MAX_SHOT_SECONDS
            for shot in result
        ):
            raise ValueError(f"Shot duration policy violation in Scene {scene.target_id}")
        if not split_count:
            return SceneShotProposalDraft(
                shots=tuple(result),
                diagnostics=draft.diagnostics,
            )
        diagnostic = (
            f"VSCS split {split_count} oversized Shot(s) to the "
            f"{cls.MIN_SHOT_SECONDS}–{cls.MAX_SHOT_SECONDS}s generation policy. "
            "Original actions are assigned to the first segment; continuations "
            "hold state without repeating events. Human review is required."
        )
        return SceneShotProposalDraft(
            shots=tuple(result),
            diagnostics=(*draft.diagnostics, diagnostic),
        )

    @classmethod
    def _validate_runtime_budget(
        cls,
        scene: AutomationProposal,
        draft: SceneShotProposalDraft,
    ) -> None:
        scene_runtime = cls._scene_runtime(scene)
        if scene_runtime <= 0:
            raise ValueError(f"Scene proposal {scene.target_id} has no valid runtime budget")
        total = sum(shot.target_runtime_seconds for shot in draft.shots)
        if total > scene_runtime:
            raise ValueError(
                f"Shot proposals for {scene.target_id} exceed the Scene runtime budget "
                f"({total}s proposed for {scene_runtime}s)"
            )
        sequence = tuple(shot.sequence_number for shot in draft.shots)
        if sequence != tuple(range(1, len(draft.shots) + 1)):
            raise ValueError(
                f"Shot proposals for {scene.target_id} must use contiguous sequence numbers"
            )

    @staticmethod
    def _scene_runtime(scene: AutomationProposal) -> int:
        raw_runtime = scene.payload.get("target_runtime_seconds")
        return (
            raw_runtime if isinstance(raw_runtime, int) and not isinstance(raw_runtime, bool) else 0
        )

    @staticmethod
    def _proposal_id(story_id: str, revision: str, scene_id: str, target_id: str) -> str:
        digest = sha256(f"{story_id}|{revision}|shot|{scene_id}|{target_id}".encode()).hexdigest()
        return f"AUT-SHOT-{digest[:12].upper()}"
