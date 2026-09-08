"""OpenAI semantic inference for unresolved governed Shot asset requirements."""

from __future__ import annotations

from hashlib import sha256
from importlib import import_module
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.story import (
    ShotAssetInferenceSource,
    ShotAssetRequirementProposal,
    ShotAssetSemanticInferenceProvider,
    ShotPlan,
)
from vscs.domain.assets import AssetCategory
from vscs.infrastructure.ai.provider import AIProviderError


class _AIShotAssetRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(min_length=1)
    requirement: str = Field(min_length=1)
    expected_category: AssetCategory
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)


class _AIShotAssetRequirementResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirements: tuple[_AIShotAssetRequirement, ...]


class OpenAIShotAssetRequirementProvider(ShotAssetSemanticInferenceProvider):
    """Infer only missing Shot asset requirements; never create or approve canon."""

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

    def infer_requirements(
        self,
        *,
        shot: ShotPlan,
        scene_text: str,
        deterministic: tuple[ShotAssetRequirementProposal, ...],
    ) -> tuple[ShotAssetRequirementProposal, ...]:
        deterministic_summary = (
            "\n".join(
                (
                    f"- {proposal.expected_category.value}: {proposal.matched_asset_name or proposal.requirement} "
                    f"({proposal.canonical_status})"
                )
                for proposal in deterministic
            )
            or "(none)"
        )

        instructions = (
            "You are the VSCS Shot Asset Requirement inference layer. Propose only production "
            "assets that are necessary to realize the supplied governed Shot and are missing from "
            "the deterministic requirement list. Do not invent canon, asset IDs, character names, "
            "locations, props, technology, ships, or environments unsupported by the supplied "
            "Shot/Scene authority. Do not propose Camera, Lighting, or Reference assets; those are "
            "owned by specialist planners. Use only these categories when justified: character, "
            "ship, planet, location, vehicle, prop, technology, environment, effect, audio, other. "
            "If the Shot can be produced using the deterministic requirements already listed, "
            "return an empty requirements tuple. Each result is a proposal for human review only."
        )
        input_text = (
            f"Shot ID: {shot.shot_id}\n"
            f"Shot title: {shot.title}\n"
            f"Coverage role: {shot.coverage_role.value}\n"
            f"Narrative purpose: {shot.narrative_purpose}\n"
            f"Production objective: {shot.production_objective}\n"
            f"Required action: {shot.required_action}\n"
            f"Dialogue requirement: {shot.dialogue_requirement or '(none)'}\n\n"
            f"Governed Shot/Scene authority:\n{scene_text}\n\n"
            f"Deterministic requirements already found:\n{deterministic_summary}"
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=input_text,
                text_format=_AIShotAssetRequirementResponse,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI Shot asset requirement inference failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI Shot asset requirement inference returned no result")
        if not isinstance(parsed, _AIShotAssetRequirementResponse):
            parsed = _AIShotAssetRequirementResponse.model_validate(parsed)

        return tuple(
            ShotAssetRequirementProposal(
                proposal_id=self._proposal_id(shot.shot_id, index, requirement),
                shot_id=shot.shot_id,
                role=requirement.role,
                requirement=requirement.requirement,
                expected_category=requirement.expected_category,
                confidence=requirement.confidence,
                source=ShotAssetInferenceSource.AI_SEMANTIC,
                rationale=requirement.rationale,
                canonical_status="unresolved",
            )
            for index, requirement in enumerate(parsed.requirements, start=1)
        )

    @staticmethod
    def _proposal_id(
        shot_id: str,
        index: int,
        requirement: _AIShotAssetRequirement,
    ) -> str:
        digest = sha256(
            (
                f"{shot_id}|{index}|{requirement.role}|"
                f"{requirement.expected_category.value}|{requirement.requirement}"
            ).encode()
        ).hexdigest()
        return f"{shot_id}-AI-AST-{digest[:10].upper()}"
