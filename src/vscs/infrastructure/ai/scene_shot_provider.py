"""Scene/Shot proposal provider for Phase 19.5.4."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.automation.scene_shot import (
    SceneShotProposalDraft,
    ShotProposalDraft,
)
from vscs.domain.story_analysis import AnalysisResult
from vscs.infrastructure.ai.provider import AIProviderError


class _OpenAIShotProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    narrative_purpose: str = Field(min_length=1)
    production_objective: str = Field(min_length=1)
    target_runtime_seconds: int = Field(gt=0)
    required_action: str = Field(min_length=1)
    dialogue_requirement: str
    continuity_in: str
    continuity_out: str
    shot_constraints: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class _OpenAISceneShotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shots: tuple[_OpenAIShotProposal, ...]

    def to_domain(self) -> SceneShotProposalDraft:
        return SceneShotProposalDraft(
            shots=tuple(
                ShotProposalDraft(
                    sequence_number=shot.sequence_number,
                    title=shot.title,
                    narrative_purpose=shot.narrative_purpose,
                    production_objective=shot.production_objective,
                    target_runtime_seconds=shot.target_runtime_seconds,
                    required_action=shot.required_action,
                    dialogue_requirement=shot.dialogue_requirement,
                    continuity_in=shot.continuity_in,
                    continuity_out=shot.continuity_out,
                    shot_constraints=shot.shot_constraints,
                    confidence=shot.confidence,
                )
                for shot in self.shots
            ),
            diagnostics=("OpenAI Scene/Shot proposal provider used",),
        )


class OpenAISceneShotProposalProvider:
    """Use structured OpenAI output to propose renderer-neutral Shot intent."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("An OpenAI API key is required")
        if not model.strip():
            raise ValueError("An OpenAI model is required")
        try:
            module = import_module("openai")
            client_type = module.OpenAI
        except (ImportError, AttributeError) as exc:
            raise AIProviderError(
                'Install the VSCS AI dependency with: python -m pip install "openai>=1.68"'
            ) from exc
        self._client: Any = client_type(api_key=api_key)
        self.model_name = model

    def propose_scene_shots(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        scene_payload: dict[str, object],
    ) -> SceneShotProposalDraft:
        instructions = (
            "You are the VSCS semantic shot-planning layer. Decompose exactly one supplied Scene "
            "proposal into the minimum useful sequence of renderer-neutral cinematic Shot proposals. "
            "Preserve Story order and explicit facts. Do not invent characters, props, locations, "
            "technology, dialogue, actions, or continuity facts unsupported by the Story or Scene. "
            "Do not choose camera lenses, camera movement, lighting design, assets, rendering models, "
            "or provider-specific prompt language; those belong to later specialist planners. Each "
            "Shot must contain narrative purpose, production objective, required action, dialogue "
            "requirement when supported, continuity boundaries, and a plausible positive runtime. "
            "Shot sequence numbers must start at 1 and be contiguous. The total Shot runtime must not "
            "exceed the Scene target runtime. These are proposals only: never claim approval, canon "
            "status, Ready state, or production authorization."
        )
        input_text = (
            f"Story ID: {story_id}\n\n"
            f"Scene proposal:\n{scene_payload}\n\n"
            f"Deterministic Story Analysis:\n{baseline.model_dump_json(indent=2)}\n\n"
            f"Story source:\n{source_text}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=input_text,
                text_format=_OpenAISceneShotResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI Scene/Shot proposal generation failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI Scene/Shot proposal generation returned no result")
        if not isinstance(parsed, _OpenAISceneShotResponse):
            parsed = _OpenAISceneShotResponse.model_validate(parsed)
        return parsed.to_domain()
