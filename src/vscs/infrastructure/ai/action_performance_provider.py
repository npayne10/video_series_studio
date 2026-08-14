"""Structured OpenAI Action, Dialogue & Performance proposals for Phase 19.5.6."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.automation.action_performance import ActionPerformanceProposalDraft
from vscs.infrastructure.ai.provider import AIProviderError


class _OpenAIActionPerformanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temporal_narrative: str = Field(min_length=1)
    spoken_content: str
    performance_direction: str
    opening_state: str
    closing_state: str
    timing_notes: str
    confidence: float = Field(ge=0.0, le=1.0)


class OpenAIActionPerformanceProposalProvider:
    """Propose temporal action, supported dialogue and performance direction per Shot."""

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

    def propose_action_performance(
        self,
        *,
        story_id: str,
        source_text: str,
        shot_payload: dict[str, object],
    ) -> ActionPerformanceProposalDraft:
        instructions = (
            "You are the VSCS Action, Dialogue & Performance proposal layer. Expand exactly one "
            "existing Shot proposal into provider-neutral temporal performance intent. Preserve the "
            "Shot's required action, runtime, continuity and Story facts. Dialogue may only be quoted "
            "or paraphrased when the supplied Story/Shot supports it; never invent new plot facts, "
            "characters, props, locations, technology, outcomes or canonical behaviour. Performance "
            "direction may describe delivery, reaction, blocking emphasis and pacing, but must not "
            "choose camera, lens, lighting, assets, renderer prompts, voices or provider settings. "
            "Return proposals only and never claim Ready, approval or production authority."
        )
        input_text = (
            f"Story ID: {story_id}\n\nShot proposal:\n{shot_payload}\n\nStory source:\n{source_text}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=input_text,
                text_format=_OpenAIActionPerformanceResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI Action/Performance proposal generation failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI Action/Performance proposal generation returned no result")
        if not isinstance(parsed, _OpenAIActionPerformanceResponse):
            parsed = _OpenAIActionPerformanceResponse.model_validate(parsed)
        return ActionPerformanceProposalDraft(
            temporal_narrative=parsed.temporal_narrative,
            spoken_content=parsed.spoken_content,
            performance_direction=parsed.performance_direction,
            opening_state=parsed.opening_state,
            closing_state=parsed.closing_state,
            timing_notes=parsed.timing_notes,
            confidence=parsed.confidence,
        )
