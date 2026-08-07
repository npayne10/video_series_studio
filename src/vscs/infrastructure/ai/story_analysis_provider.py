"""Story Analysis AI providers for deterministic development and OpenAI enrichment."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


class _OpenAIAttribute(BaseModel):
    """Strict key/value attribute representation accepted by Structured Outputs."""

    model_config = ConfigDict(extra="forbid")

    key: str
    value: str


class _OpenAIEntityDraft(BaseModel):
    """Strict OpenAI wire model; every property is required by Structured Outputs."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    category: EntityResolutionCategory
    description: str
    aliases: tuple[str, ...]
    evidence_text: tuple[str, ...]
    attributes: tuple[_OpenAIAttribute, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class _OpenAINarrativeMetadata(BaseModel):
    """Strict OpenAI wire model for narrative metadata."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    themes: tuple[str, ...]
    tone: tuple[str, ...]
    setting: tuple[str, ...]
    production_notes: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class _OpenAIStoryAnalysisResponse(BaseModel):
    """Strict response envelope supplied to the OpenAI Responses API."""

    model_config = ConfigDict(extra="forbid")

    entities: tuple[_OpenAIEntityDraft, ...]
    metadata: _OpenAINarrativeMetadata

    def to_domain(self) -> AIStoryAnalysisDraft:
        """Convert the strict provider response into the provider-neutral VSCS model."""
        entities = tuple(
            AIEntityDraft(
                name=entity.name,
                category=entity.category,
                description=entity.description,
                aliases=entity.aliases,
                evidence_text=entity.evidence_text,
                attributes={item.key: item.value for item in entity.attributes},
                confidence=entity.confidence,
            )
            for entity in self.entities
        )
        metadata = AINarrativeMetadata(
            summary=self.metadata.summary,
            themes=self.metadata.themes,
            tone=self.metadata.tone,
            setting=self.metadata.setting,
            production_notes=self.metadata.production_notes,
            confidence=self.metadata.confidence,
        )
        return AIStoryAnalysisDraft(
            entities=entities,
            metadata=metadata,
            diagnostics=("OpenAI Story Analysis provider used",),
        )


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
            "Every response field is required: use an empty string or empty array when no value is "
            "supported by the story. Represent entity attributes as key/value records. Also extract "
            "useful narrative metadata such as themes, tone, setting and production notes. Do not "
            "promote uncertainty into canon; all entities are proposals awaiting human approval."
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
                text_format=_OpenAIStoryAnalysisResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI Story Analysis failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI Story Analysis returned no structured result")
        if not isinstance(parsed, _OpenAIStoryAnalysisResponse):
            try:
                parsed = _OpenAIStoryAnalysisResponse.model_validate(parsed)
            except (TypeError, ValueError) as exc:
                raise AIProviderError(
                    f"OpenAI Story Analysis returned an invalid structured result: {exc}"
                ) from exc
        return parsed.to_domain()
