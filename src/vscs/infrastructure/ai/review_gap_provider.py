"""Optional AI wording for Phase 19.5.11 repair suggestions."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.automation.review_gaps import ReviewGap
from vscs.infrastructure.ai.provider import AIProviderError


class _RepairSuggestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggestion: str = Field(min_length=1, max_length=1200)


class OpenAIReviewGapSuggestionProvider:
    """Suggest a repair action; never mutate proposals or governed authority."""

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

    def suggest(self, gap: ReviewGap) -> str:
        instructions = (
            "You are the VSCS production review assistant. Provide one concise repair suggestion for "
            "the supplied detected gap. You are advisory only. Never approve, accept, mark Ready, "
            "create canonical identity, overwrite human authority, or claim that a repair was applied. "
            "Prefer reuse of existing governed VSCS functions and upstream regeneration over rewriting. "
            "For canonical asset gaps, require human canonical governance. For continuity conflicts, "
            "require human choice of canonical state."
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=(
                    f"Severity: {gap.severity.value}\nCategory: {gap.category}\n"
                    f"Target: {gap.target_id}\nSummary: {gap.summary}\nEvidence: {gap.evidence}\n"
                    f"Deterministic suggestion: {gap.repair_suggestion}"
                ),
                text_format=_RepairSuggestionResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI review suggestion failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI review suggestion returned no result")
        if not isinstance(parsed, _RepairSuggestionResponse):
            parsed = _RepairSuggestionResponse.model_validate(parsed)
        return parsed.suggestion.strip()
