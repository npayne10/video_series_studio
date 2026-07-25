"""OpenAI-backed structured CAP generation."""

from __future__ import annotations

from importlib import import_module
from typing import Any, cast

from vscs.domain.caps.generation import CAPGenerationRequest, GeneratedCAPDraft
from vscs.infrastructure.ai.provider import AIProviderError


class OpenAICAPGenerationProvider:
    """Generate CAP drafts through the OpenAI Responses API."""

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("An OpenAI API key is required")
        if not model.strip():
            raise ValueError("An OpenAI model is required")
        try:
            openai_module = import_module("openai")
            client_type = openai_module.OpenAI
        except (ImportError, AttributeError) as exc:
            raise AIProviderError(
                'Install the VSCS AI dependency with: python -m pip install "openai>=1.68"'
            ) from exc
        self._client: Any = client_type(api_key=api_key)
        self._model = model

    @classmethod
    def test_connection(cls, *, api_key: str, model: str) -> None:
        """Validate the configured credentials and model with a lightweight API call."""
        provider = cls(api_key=api_key, model=model)
        try:
            provider._client.models.retrieve(model)
        except Exception as exc:
            raise AIProviderError(f"OpenAI connection test failed: {exc}") from exc

    def generate_cap(self, request: CAPGenerationRequest) -> GeneratedCAPDraft:
        instructions = (
            "You are the VSCS Canonical Asset Profile generator. Create a production-ready draft "
            "grounded in the supplied story. Separate explicit canon from provisional inference. "
            "Never present an unsupported invention as established fact. Return only the requested "
            "structured result."
        )
        input_text = (
            f"Asset ID: {request.asset_id}\n"
            f"Asset name: {request.asset_name}\n"
            f"Category: {request.asset_category}\n"
            f"Existing description: {request.asset_description or '(none)'}\n\n"
            f"Story context:\n{request.story_context}"
        )
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=input_text,
                text_format=GeneratedCAPDraft,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI CAP generation failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI returned no structured CAP draft")
        return cast(GeneratedCAPDraft, parsed)
