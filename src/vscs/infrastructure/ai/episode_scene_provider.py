"""Episode/Scene proposal providers for Phase 19.5.3."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.automation.episode_scene import (
    EpisodeProposalDraft,
    EpisodeSceneProposalDraft,
    SceneProposalDraft,
)
from vscs.domain.story_analysis import AnalysisResult
from vscs.infrastructure.ai.provider import AIProviderError


class _OpenAISceneProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    story_scope: str = Field(min_length=1)
    production_objective: str = Field(min_length=1)
    target_runtime_seconds: int = Field(gt=0)
    setting_requirement: str = Field(min_length=1)
    required_events: tuple[str, ...]
    continuity_in: str
    continuity_out: str
    scene_constraints: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class _OpenAIEpisodeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    story_scope: str = Field(min_length=1)
    production_objective: str = Field(min_length=1)
    target_runtime_seconds: int = Field(gt=0)
    continuity_in: str
    continuity_out: str
    production_constraints: tuple[str, ...]
    scenes: tuple[_OpenAISceneProposal, ...]
    confidence: float = Field(ge=0.0, le=1.0)


class _OpenAIEpisodeSceneResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    episodes: tuple[_OpenAIEpisodeProposal, ...]

    def to_domain(self) -> EpisodeSceneProposalDraft:
        episodes = tuple(
            EpisodeProposalDraft(
                sequence_number=episode.sequence_number,
                title=episode.title,
                story_scope=episode.story_scope,
                production_objective=episode.production_objective,
                target_runtime_seconds=episode.target_runtime_seconds,
                continuity_in=episode.continuity_in,
                continuity_out=episode.continuity_out,
                production_constraints=episode.production_constraints,
                scenes=tuple(
                    SceneProposalDraft(
                        sequence_number=scene.sequence_number,
                        title=scene.title,
                        story_scope=scene.story_scope,
                        production_objective=scene.production_objective,
                        target_runtime_seconds=scene.target_runtime_seconds,
                        setting_requirement=scene.setting_requirement,
                        required_events=scene.required_events,
                        continuity_in=scene.continuity_in,
                        continuity_out=scene.continuity_out,
                        scene_constraints=scene.scene_constraints,
                        confidence=scene.confidence,
                    )
                    for scene in episode.scenes
                ),
                confidence=episode.confidence,
            )
            for episode in self.episodes
        )
        return EpisodeSceneProposalDraft(
            episodes=episodes,
            diagnostics=("OpenAI Episode/Scene proposal provider used",),
        )


class OpenAIEpisodeSceneProposalProvider:
    """Use structured OpenAI output to propose Episode and Scene decomposition."""

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

    def propose_episode_scenes(
        self,
        *,
        story_id: str,
        source_text: str,
        baseline: AnalysisResult,
        semantic_payload: dict[str, object],
    ) -> EpisodeSceneProposalDraft:
        instructions = (
            "You are the VSCS semantic production-planning layer. Decompose the supplied Story "
            "into the minimum useful Episode and Scene structure for cinematic production. "
            "Preserve story order and explicit facts. Do not invent characters, locations, props, "
            "technology, events, or continuity facts that are not supported by the Story. Use the "
            "existing semantic interpretation and deterministic Story Analysis as context. Each "
            "scene must have a clear production objective, setting requirement, required events, "
            "continuity boundaries, and a plausible runtime. Keep one episode for a short, "
            "self-contained story unless the source clearly requires multiple episodes. These are "
            "proposals only: never claim approval, canon status, or production readiness."
        )
        input_text = (
            f"Story ID: {story_id}\n\n"
            f"Semantic interpretation:\n{semantic_payload}\n\n"
            f"Deterministic Story Analysis:\n{baseline.model_dump_json(indent=2)}\n\n"
            f"Story source:\n{source_text}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=input_text,
                text_format=_OpenAIEpisodeSceneResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(
                f"OpenAI Episode/Scene proposal generation failed: {exc}"
            ) from exc
        if parsed is None:
            raise AIProviderError("OpenAI Episode/Scene proposal generation returned no result")
        if not isinstance(parsed, _OpenAIEpisodeSceneResponse):
            parsed = _OpenAIEpisodeSceneResponse.model_validate(parsed)
        return parsed.to_domain()
