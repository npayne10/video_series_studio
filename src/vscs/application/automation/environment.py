"""Environment production proposal automation for Phase 19.5.7."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from vscs.application.story import (
    AtmosphereState,
    EnvironmentContext,
    TimeContext,
    WeatherState,
)

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


@dataclass(frozen=True, slots=True)
class EnvironmentProposalDraft:
    """Provider-neutral physical-world proposal mirroring governed Environment authority."""

    environment_context: EnvironmentContext
    time_context: TimeContext
    atmosphere_state: AtmosphereState
    weather_state: WeatherState
    gravity_m_s2: float | None
    pressure_kpa: float | None
    temperature_c: float | None
    visibility_m: float | None
    surface_state: str
    environmental_motion: str
    hazard_notes: str = ""
    continuity_notes: str = ""
    environment_constraints: tuple[str, ...] = ()
    confidence: float = 0.5


class EnvironmentProposalProvider(Protocol):
    provider_name: str
    model_name: str

    def propose_environment(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
        performance_payload: dict[str, object],
    ) -> EnvironmentProposalDraft: ...


class TemplateEnvironmentProposalProvider:
    """Conservative offline provider that preserves unknown physical properties."""

    provider_name = "vscs-template"
    model_name = "deterministic"

    def propose_environment(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
        performance_payload: dict[str, object],
    ) -> EnvironmentProposalDraft:
        del story_id, source_text
        continuity = " ".join(
            value
            for value in (
                str(shot_payload.get("continuity_in", "")).strip(),
                str(shot_payload.get("continuity_out", "")).strip(),
                str(performance_payload.get("opening_state", "")).strip(),
                str(performance_payload.get("closing_state", "")).strip(),
            )
            if value
        )
        return EnvironmentProposalDraft(
            environment_context=EnvironmentContext.INTERIOR,
            time_context=TimeContext.ARTIFICIAL_CYCLE,
            atmosphere_state=AtmosphereState.UNKNOWN,
            weather_state=WeatherState.NONE,
            gravity_m_s2=None,
            pressure_kpa=None,
            temperature_c=None,
            visibility_m=None,
            surface_state="Preserve the established Story location and canonical environment state.",
            environmental_motion=(
                "No environmental motion beyond explicitly established Story or Shot requirements."
            ),
            continuity_notes=continuity,
            environment_constraints=(
                "Do not invent environmental physics or conditions not established by canon.",
            ),
            confidence=0.5,
        )


class EnvironmentProposalAutomationService:
    """Generate Environment proposals without mutating governed Environment Planning."""

    def __init__(
        self,
        provider: EnvironmentProposalProvider,
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
        shots = tuple(
            item for item in current if item.proposal_type is AutomationProposalType.SHOT
        )
        performances = {
            item.target_id: item
            for item in current
            if item.proposal_type is AutomationProposalType.ACTION_PERFORMANCE
        }
        if not shots:
            raise ValueError("Generate current Shot proposals before Environment proposals")
        missing = tuple(shot.target_id for shot in shots if shot.target_id not in performances)
        if missing:
            raise ValueError(
                "Generate current Action/Performance proposals before Environment proposals; "
                f"missing {len(missing)} Shot(s)"
            )

        generated: list[AutomationProposal] = []
        for shot in sorted(shots, key=lambda item: item.target_id):
            performance = performances[shot.target_id]
            draft = self._provider.propose_environment(
                story_id=normalized_story,
                source_text=source_text,
                shot_payload=shot.payload,
                performance_payload=performance.payload,
            )
            self._validate(draft, shot.target_id)
            generated.append(
                self._proposals.save(
                    self._proposal(
                        story_id=normalized_story,
                        revision=revision,
                        source_text=source_text,
                        shot=shot,
                        performance=performance,
                        draft=draft,
                    )
                )
            )
        return tuple(generated)

    @staticmethod
    def _validate(draft: EnvironmentProposalDraft, shot_id: str) -> None:
        if not draft.surface_state.strip():
            raise ValueError(f"Environment proposal for {shot_id} requires surface state")
        if not draft.environmental_motion.strip():
            raise ValueError(f"Environment proposal for {shot_id} requires environmental motion")
        ranges = (
            (draft.gravity_m_s2, 0.0, 100.0, "gravity"),
            (draft.pressure_kpa, 0.0, 10000.0, "pressure"),
            (draft.temperature_c, -273.15, 5000.0, "temperature"),
            (draft.visibility_m, 0.0, 1_000_000_000.0, "visibility"),
        )
        for value, minimum, maximum, name in ranges:
            if value is not None and not minimum <= value <= maximum:
                raise ValueError(f"Environment proposal for {shot_id} has invalid {name}")
        if draft.atmosphere_state is AtmosphereState.VACUUM and draft.pressure_kpa not in (
            None,
            0.0,
        ):
            raise ValueError(f"Environment proposal for {shot_id} assigns pressure to vacuum")

    def _proposal(
        self,
        *,
        story_id: str,
        revision: str,
        source_text: str,
        shot: AutomationProposal,
        performance: AutomationProposal,
        draft: EnvironmentProposalDraft,
    ) -> AutomationProposal:
        digest = sha256(
            f"{story_id}|{revision}|environment|{shot.proposal_id}|{performance.proposal_id}".encode()
        ).hexdigest()
        source_kind = (
            AutomationSourceKind.AI_INFERENCE
            if self._provider.provider_name != "vscs-template"
            else AutomationSourceKind.DETERMINISTIC_RESOLUTION
        )
        return AutomationProposal(
            proposal_id=f"AUT-ENVIRONMENT-{digest[:12].upper()}",
            proposal_type=AutomationProposalType.ENVIRONMENT,
            target_id=shot.target_id,
            payload={
                "shot_id": shot.target_id,
                "environment_context": draft.environment_context.value,
                "time_context": draft.time_context.value,
                "atmosphere_state": draft.atmosphere_state.value,
                "weather_state": draft.weather_state.value,
                "gravity_m_s2": draft.gravity_m_s2,
                "pressure_kpa": draft.pressure_kpa,
                "temperature_c": draft.temperature_c,
                "visibility_m": draft.visibility_m,
                "surface_state": draft.surface_state,
                "environmental_motion": draft.environmental_motion,
                "hazard_notes": draft.hazard_notes,
                "continuity_notes": draft.continuity_notes,
                "environment_constraints": list(draft.environment_constraints),
            },
            provenance=AutomationProvenance(
                source_kind=source_kind,
                source_story_id=story_id,
                source_revision=revision,
                source_scope="current Shot and Action/Performance proposals plus Story source",
                provider=self._provider.provider_name,
                model=self._provider.model_name,
                confidence=max(0.0, min(1.0, draft.confidence)),
                inference_note=(
                    "Physical environment is proposed for human review only. Unknown physics "
                    "remain unknown and no governed Environment Plan is created or marked Ready."
                ),
                resolution_method="provider-neutral physical environment interpretation",
            ),
            metadata={
                "phase": "19.5.7",
                "parent_shot_proposal_id": shot.proposal_id,
                "parent_action_performance_proposal_id": performance.proposal_id,
                "source_sha256": sha256(source_text.encode("utf-8")).hexdigest(),
            },
        )
