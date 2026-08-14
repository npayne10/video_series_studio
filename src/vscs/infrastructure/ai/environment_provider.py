"""Structured OpenAI Environment proposals for Phase 19.5.7."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.automation.environment import EnvironmentProposalDraft
from vscs.application.story import (
    AtmosphereState,
    EnvironmentContext,
    TimeContext,
    WeatherState,
)
from vscs.infrastructure.ai.provider import AIProviderError


class _OpenAIEnvironmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_context: EnvironmentContext
    time_context: TimeContext
    atmosphere_state: AtmosphereState
    weather_state: WeatherState
    gravity_m_s2: float | None = Field(default=None, ge=0.0, le=100.0)
    pressure_kpa: float | None = Field(default=None, ge=0.0, le=10000.0)
    temperature_c: float | None = Field(default=None, ge=-273.15, le=5000.0)
    visibility_m: float | None = Field(default=None, ge=0.0, le=1_000_000_000.0)
    surface_state: str = Field(min_length=1)
    environmental_motion: str = Field(min_length=1)
    hazard_notes: str
    continuity_notes: str
    environment_constraints: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class OpenAIEnvironmentProposalProvider:
    """Propose grounded physical-world state without creating environmental canon."""

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

    def propose_environment(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
        performance_payload: dict[str, object],
    ) -> EnvironmentProposalDraft:
        instructions = (
            "You are the VSCS physical Environment proposal layer. Interpret exactly one current "
            "Shot plus its Action/Performance proposal into renderer-neutral physical-world state. "
            "Use only Story-supported facts. Preserve unknown physical values as null: never invent "
            "gravity, pressure, temperature, visibility, atmospheric composition, weather or hazards "
            "when canon does not establish them. Do not create or choose canonical Asset IDs. Do not "
            "decide camera framing, lenses, lighting/exposure, visual style, renderer prompts, model "
            "settings or provider settings. Environment context owns physical setting, atmosphere, "
            "weather, surface state, environmental motion, hazards and environment continuity only. "
            "Return a proposal for human review; never claim Ready state, approval or authority."
        )
        input_text = (
            f"Story ID: {story_id}\n\nShot proposal:\n{shot_payload}\n\n"
            f"Action/Performance proposal:\n{performance_payload}\n\nStory source:\n{source_text}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=input_text,
                text_format=_OpenAIEnvironmentResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI Environment proposal generation failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI Environment proposal generation returned no result")
        if not isinstance(parsed, _OpenAIEnvironmentResponse):
            parsed = _OpenAIEnvironmentResponse.model_validate(parsed)
        return EnvironmentProposalDraft(
            environment_context=parsed.environment_context,
            time_context=parsed.time_context,
            atmosphere_state=parsed.atmosphere_state,
            weather_state=parsed.weather_state,
            gravity_m_s2=parsed.gravity_m_s2,
            pressure_kpa=parsed.pressure_kpa,
            temperature_c=parsed.temperature_c,
            visibility_m=parsed.visibility_m,
            surface_state=parsed.surface_state,
            environmental_motion=parsed.environmental_motion,
            hazard_notes=parsed.hazard_notes,
            continuity_notes=parsed.continuity_notes,
            environment_constraints=parsed.environment_constraints,
            confidence=parsed.confidence,
        )
