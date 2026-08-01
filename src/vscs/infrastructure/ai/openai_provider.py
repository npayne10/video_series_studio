"""OpenAI-backed structured CAP generation."""

from __future__ import annotations

from importlib import import_module
from typing import Any, TypeVar, cast

from pydantic import BaseModel

from vscs.domain.caps.generation import (
    CanonicalFactExtraction,
    CAPCanonAnalysis,
    CAPGenerationRequest,
    GeneratedCAPDraft,
)
from vscs.infrastructure.ai.provider import AIProviderError

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class OpenAICAPGenerationProvider:
    """Generate CAP drafts through a multi-stage OpenAI intelligence pipeline."""

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
        """Run fact extraction, canon analysis, and draft generation in sequence."""
        try:
            extraction = self._extract_facts(request)
            analysis = self._analyse_canon(request, extraction)
            return self._generate_draft(request, analysis)
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(f"OpenAI CAP generation failed: {exc}") from exc

    def _extract_facts(self, request: CAPGenerationRequest) -> CanonicalFactExtraction:
        instructions = (
            "You are stage one of the VSCS CAP intelligence pipeline. Extract only explicit, "
            "asset-relevant facts from the supplied source. Do not infer design details. For each "
            "fact, include concise source evidence and a confidence score. Put ambiguous, implied, "
            "or incomplete claims in candidate_claims instead of facts."
        )
        return self._parse(
            instructions=instructions,
            input_text=self._request_text(request),
            result_type=CanonicalFactExtraction,
            stage="canonical fact extraction",
        )

    def _analyse_canon(
        self,
        request: CAPGenerationRequest,
        extraction: CanonicalFactExtraction,
    ) -> CAPCanonAnalysis:
        instructions = (
            "You are stage two of the VSCS CAP intelligence pipeline. Review the extracted facts "
            "against the original source. Retain only established canon. Move unsupported, "
            "ambiguous, or conflicting material into uncertainties or contradictions. Do not add "
            "new facts. Produce a concise source summary."
        )
        input_text = (
            f"Original request:\n{self._request_text(request)}\n\n"
            f"Stage-one extraction:\n{extraction.model_dump_json(indent=2)}"
        )
        return self._parse(
            instructions=instructions,
            input_text=input_text,
            result_type=CAPCanonAnalysis,
            stage="canon analysis",
        )

    def _generate_draft(
        self,
        request: CAPGenerationRequest,
        analysis: CAPCanonAnalysis,
    ) -> GeneratedCAPDraft:
        instructions = (
            "You are stage three of the VSCS CAP intelligence pipeline. Create a production-ready "
            "CAP Draft Package using only canonical_facts from the supplied analysis. Never promote "
            "an uncertainty, contradiction, or unsupported inference into canon. Preserve all "
            "uncertainties as unresolved_questions. Copy canonical_facts and contradictions into "
            "the result. Score confidence for every draft section and overall. Lower confidence "
            "when facts are sparse, indirect, or visually incomplete."
        )
        input_text = (
            f"Asset ID: {request.asset_id}\n"
            f"Asset name: {request.asset_name}\n"
            f"Category: {request.asset_category}\n\n"
            f"Approved canon analysis:\n{analysis.model_dump_json(indent=2)}"
        )
        draft = self._parse(
            instructions=instructions,
            input_text=input_text,
            result_type=GeneratedCAPDraft,
            stage="CAP Draft Package generation",
        )
        if not draft.canonical_facts:
            draft = draft.model_copy(update={"canonical_facts": analysis.canonical_facts})
        if not draft.unresolved_questions:
            draft = draft.model_copy(update={"unresolved_questions": analysis.uncertainties})
        if not draft.contradictions:
            draft = draft.model_copy(update={"contradictions": analysis.contradictions})
        if not draft.source_summary:
            draft = draft.model_copy(update={"source_summary": analysis.source_summary})
        return draft

    def _parse(
        self,
        *,
        instructions: str,
        input_text: str,
        result_type: type[StructuredResult],
        stage: str,
    ) -> StructuredResult:
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=input_text,
                text_format=result_type,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI {stage} failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError(f"OpenAI returned no structured result during {stage}")
        return cast(StructuredResult, parsed)

    @staticmethod
    def _request_text(request: CAPGenerationRequest) -> str:
        return (
            f"Asset ID: {request.asset_id}\n"
            f"Asset name: {request.asset_name}\n"
            f"Category: {request.asset_category}\n"
            f"Existing description: {request.asset_description or '(none)'}\n\n"
            f"Story context:\n{request.story_context}"
        )
