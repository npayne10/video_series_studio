"""Story Analysis AI providers for deterministic development and OpenAI enrichment."""

from __future__ import annotations

from importlib import import_module
from typing import Any, cast

from vscs.domain.story_analysis import (
    AIEntityDraft,
    AINarrativeMetadata,
    AIStoryAnalysisDraft,
    AnalysisResult,
    EntityResolutionCategory,
)
from vscs.infrastructure.ai.provider import AIProviderError


class TemplateStoryAIAnalysisProvider:
    """Offline provider that mirrors baseline entities for tests and development."""

    def analyze_story(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
    ) -> AIStoryAnalysisDraft:
        del story_id
        entities = tuple(
            AIEntityDraft(
                name=entity.name,
                category=self._category(entity.kind.value),
                description="Deterministic baseline entity proposed for review.",
                evidence_text=tuple(source.excerpt for source in entity.sources if source.excerpt),
                confidence=entity.confidence,
            )
            for entity in baseline.entities
        )
        metadata = AINarrativeMetadata(
            summary=source_text.strip()[:800],
            production_notes=(
                "Offline template enrichment is active; configure an AI provider for semantic "
                "entity discovery beyond deterministic baseline extraction.",
            ),
            confidence=0.5,
        )
        return AIStoryAnalysisDraft(
            entities=entities,
            metadata=metadata,
            diagnostics=("Template AI Story Analysis provider used",),
        )

    @staticmethod
    def _category(value: str) -> EntityResolutionCategory:
        try:
            return EntityResolutionCategory(value)
        except ValueError:
            return EntityResolutionCategory.OTHER


class OpenAIStoryAIAnalysisProvider:
    """Use OpenAI structured output to identify production entities and story metadata."""

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
        self._model = model

    def analyze_story(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
    ) -> AIStoryAnalysisDraft:
        instructions = (
            "You are the VSCS Story Analysis intelligence layer. Identify production-relevant "
            "entities explicitly supported by the supplied story: characters, ships, planets, "
            "locations, vehicles, props, technology, organisations, species and environments. "
            "Do not invent visual facts. Use evidence_text copied exactly from the source whenever "
            "possible. Supply concise descriptions, aliases, explicit attributes and confidence. "
            "Also extract useful narrative metadata such as themes, tone, setting and production "
            "notes. Do not promote uncertainty into canon; all entities are proposals awaiting "
            "human approval."
        )
        input_text = (
            f"Story ID: {story_id}\n\n"
            f"Deterministic baseline:\n{baseline.model_dump_json(indent=2)}\n\n"
            f"Story source:\n{source_text}"
        )
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=input_text,
                text_format=AIStoryAnalysisDraft,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI Story Analysis failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI Story Analysis returned no structured result")
        return cast(AIStoryAnalysisDraft, parsed)
