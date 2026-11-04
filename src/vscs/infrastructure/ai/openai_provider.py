"""OpenAI-backed structured CAP generation."""

from __future__ import annotations

import re
from importlib import import_module
from typing import Any, TypeVar, cast

from pydantic import BaseModel, Field

from vscs.application.caps.provider_design_expansion import DesignExpansionResponse
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.caps.generation import (
    CanonicalFactExtraction,
    CAPCanonAnalysis,
    CAPGenerationRequest,
    ExtractedCanonicalFact,
    GeneratedCAPDraft,
)
from vscs.infrastructure.ai.provider import AIProviderError

StructuredResult = TypeVar("StructuredResult", bound=BaseModel)


class _StrictCAPConfidence(BaseModel):
    """OpenAI wire schema: all confidence fields are explicitly required."""

    canonical_description: float = Field(ge=0.0, le=1.0)
    visual_identity: float = Field(ge=0.0, le=1.0)
    production_notes: float = Field(ge=0.0, le=1.0)
    continuity_rules: float = Field(ge=0.0, le=1.0)
    prohibited_variations: float = Field(ge=0.0, le=1.0)
    functional_capabilities: float = Field(ge=0.0, le=1.0)
    classifications: float = Field(ge=0.0, le=1.0)
    overall: float = Field(ge=0.0, le=1.0)


class _MetadataEntry(BaseModel):
    """Explicit metadata pair, avoiding dynamic JSON object keys in strict schemas."""

    key: str
    value: str


class _StrictGeneratedCAPDraft(BaseModel):
    """Strict API response model; legacy domain defaults remain unchanged."""

    title: str
    canonical_description: str
    visual_identity: str
    production_notes: str
    continuity_rules: tuple[str, ...]
    prohibited_variations: tuple[str, ...]
    functional_capabilities: tuple[str, ...]
    semantic_tags: tuple[str, ...]
    production_classifications: tuple[str, ...]
    behaviour_references: tuple[str, ...]
    production_metadata: tuple[_MetadataEntry, ...]
    unresolved_questions: tuple[str, ...]
    source_summary: str
    canonical_facts: tuple[ExtractedCanonicalFact, ...]
    contradictions: tuple[str, ...]
    confidence: _StrictCAPConfidence


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

    @classmethod
    def list_available_models(cls, *, api_key: str) -> tuple[str, ...]:
        """Return API-visible model IDs; visibility does not guarantee CAP compatibility."""
        provider = cls(api_key=api_key, model="model-discovery")
        try:
            response = provider._client.models.list()
            identifiers = {
                model.id.strip()
                for model in response.data
                if isinstance(getattr(model, "id", None), str) and model.id.strip()
            }
        except Exception as exc:
            raise AIProviderError(f"OpenAI model discovery failed: {exc}") from exc
        return tuple(sorted(identifiers, key=str.casefold))

    def generate_cap(self, request: CAPGenerationRequest) -> GeneratedCAPDraft:
        """Run fact extraction, canon analysis, and draft generation in sequence."""
        try:
            extraction = self._extract_facts(request)
            analysis = self._analyse_canon(request, extraction)
            draft = self._generate_draft(request, analysis)
            issues = (
                *self._identity_quality_issues(draft),
                *self._source_relationship_issues(request, draft),
            )
            if issues:
                # One bounded corrective draft call, reusing the same verified facts.
                # Never silently accept a recurring Shot-event leak into asset identity.
                draft = self._generate_draft(request, analysis, corrections=issues)
                remaining = (
                    *self._identity_quality_issues(draft),
                    *self._source_relationship_issues(request, draft),
                )
                if remaining:
                    raise AIProviderError(
                        "CAP identity quality gate failed after one corrective generation: "
                        + "; ".join(remaining)
                    )
            return draft
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError(f"OpenAI CAP generation failed: {exc}") from exc

    def expand_cap_design(
        self, spec: CAPStructuredSpecification, story_context: str
    ) -> DesignExpansionResponse:
        """One read-only structured call for creative suggestions, never canon."""
        from vscs.application.caps.completeness import REQUIRED_FIELDS

        missing = [
            key
            for key in REQUIRED_FIELDS.get(spec.category, ("identity",))
            if not spec.canonical_attributes.get(key, "").strip()
        ]
        if not missing:
            return DesignExpansionResponse(fields=())
        instructions = (
            "Act as a production designer, NOT a canon extraction agent. "
            "Suggest a DISTINCTIVE, repeatable, camera-independent physical asset. "
            "For locations establish a coordinate-independent fixed layout, key equipment relationships, "
            "doorways or access points when appropriate, consistent surfaces and practical lighting fixtures. "
            "For scale or dimensions give plausible numeric measurements and units explicitly as PROPOSED "
            "design choices, never as source facts. Treat separate props, ships and characters as "
            "independent assets: specify attachment zones or spatial relationships without inventing "
            "their intrinsic dimensions, identity or appearance. Do not use foreground, midground, "
            "background, framing, camera placement or shot composition as canonical geometry. "
            "Never present invented dimensions, materials, or spatial relationships as Story facts. "
            "Return exactly one proposal and rationale per requested field; leave a field out "
            "if a responsible design cannot be proposed. Never change fixed attributes. "
            "Do not generate images or execute media providers."
        )
        source = (
            f"Category: {spec.category.value}\\nDesign intent: {spec.design_intent}\\n"
            f"Fixed details: {spec.canonical_attributes}\\n"
            f"Fields to propose: {missing}\\n"
            f"Story context (source, not permission to invent canon): {story_context}"
        )
        return self._parse(
            instructions=instructions,
            input_text=source,
            result_type=DesignExpansionResponse,
            stage="CAP design detail proposals",
        )

    def _extract_facts(self, request: CAPGenerationRequest) -> CanonicalFactExtraction:
        instructions = (
            "You are stage one of the VSCS CAP intelligence pipeline. Extract only explicit, "
            "asset-relevant facts from the supplied source. Do not infer design details. For each "
            "fact, include concise source evidence and a confidence score. Preserve clear "
            "object ownership and spatial relationships: if the grammar identifies a display "
            "as belonging to the console, do not treat that ownership as ambiguous. "
            "Label one-time Shot events as temporal source facts, never fixed physical "
            "characteristics. Put ambiguous, implied, or incomplete claims in "
            "candidate_claims instead of facts."
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
            "ambiguous, or conflicting material into uncertainties or contradictions. Preserve "
            "explicit ownership and fixed spatial relationships without inventing missing "
            "geometry. Distinguish facts describing fixed asset identity from temporal "
            "events that belong to a Shot; retain event facts as evidence, not permanent "
            "identity constraints. Do not add new facts. Produce a concise source summary."
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

    @staticmethod
    def _identity_quality_issues(draft: GeneratedCAPDraft) -> tuple[str, ...]:
        """Detect clear transient Shot events leaking into persistent CAP identity.

        This is deliberately conservative: unresolved ambiguity is left for review,
        not rewritten as canon. The full source facts remain available as evidence.
        """
        identity_text = " ".join(
            (
                draft.canonical_description,
                draft.visual_identity,
                *draft.continuity_rules,
            )
        ).lower()
        transient_patterns = (
            r"\bpuls(?:es|e|ed|ing)\s+(?:exactly\s+)?once\b",
            r"\bindicator\s+(?:then\s+)?returns?\s+to\s+(?:a\s+)?steady\s+glow\b",
            r"\bafter\s+the\s+indicator\s+pulse\b",
            r"\bbefore\s+the\s+indicator\s+pulse\b",
        )
        if any(re.search(pattern, identity_text) for pattern in transient_patterns):
            return (
                "Shot-specific indicator pulse or sequence appears in persistent CAP identity "
                "or continuity rules. Move it to narrative evidence only.",
            )
        return ()

    @staticmethod
    def _source_relationship_issues(
        request: CAPGenerationRequest, draft: GeneratedCAPDraft
    ) -> tuple[str, ...]:
        """Flag an avoidable loss of a source-linked relationship for review.

        A possible grammatical attachment is *not* itself promoted to canon.
        The corrective model must inspect the original sentence and leave
        genuinely ambiguous relationships unresolved.
        """
        source = request.story_context.lower()
        identity = " ".join(
            (draft.canonical_description, draft.visual_identity, *draft.continuity_rules)
        ).lower()
        source_links_display = bool(
            re.search(
                r"\b(?:diagnostic\s+)?console\b.{0,160}\bits\s+blue\s+display\b",
                source,
                flags=re.DOTALL,
            )
            or re.search(r"\bconsole['’]s\s+blue\s+display\b", source)
        )
        if source_links_display and re.search(
            r"\b(?:display['’]s\s+)?ownership\s+(?:is\s+)?unspecified\b"
            r"|\btheir\s+ownership\b",
            identity,
        ):
            return (
                "The source links the blue display to a console by possessive "
                "wording, but the Draft discards that link. Re-read the original "
                "source grammar; preserve a supported ownership relationship, "
                "but do not invent the small indicator's precise attachment.",
            )
        return ()

    def _generate_draft(
        self,
        request: CAPGenerationRequest,
        analysis: CAPCanonAnalysis,
        *,
        corrections: tuple[str, ...] = (),
    ) -> GeneratedCAPDraft:
        instructions = (
            "You are stage three of the VSCS CAP intelligence pipeline. Create a production-ready "
            "CAP Draft Package using only canonical_facts from the supplied analysis. Never promote "
            "an uncertainty, contradiction, or unsupported inference into canon. Preserve all "
            "uncertainties as unresolved_questions. Copy canonical_facts and contradictions into "
            "the result. Also emit structured functional_capabilities, semantic_tags, "
            "production_classifications, behaviour_references, and production_metadata key/value entries only when "
            "they are directly supported by the approved canonical facts. Functional capabilities "
            "must describe what the asset can actually do in production, not visual adjectives. "
            "Asset identity and continuity rules describe PERSISTENT, CAMERA-INDEPENDENT "
            "physical characteristics, fixed relationships and constraints across shots. "
            "Single-occurrence actions, transitions, timing, lighting changes, dialogue and "
            "other Shot events remain in source evidence/production notes, NEVER in "
            "canonical_description, visual_identity, or continuity_rules. For example, "
            "'an indicator pulses once then returns to steady' is a Shot action; the "
            "CAP may describe only the presence and fixed placement of that indicator. "
            "Continuity rules and prohibited variations must govern stable identity, "
            "not dictate which Shot contains an action. Preserve unambiguous ownership "
            "and pronoun references in the source (e.g. a console's blue display belongs "
            "to the console), never invent a new ambiguity. "
            "Do not invent dimensions, materials or geometry. Leave unresolved facts "
            "unresolved; proposed design details require separate human review. "
            "Leave a structured collection empty rather than inventing unsupported information. "
            "Score confidence for every draft section and overall, lowering confidence when facts "
            "are sparse, indirect, or incomplete."
        )
        input_text = (
            f"Asset ID: {request.asset_id}\n"
            f"Asset name: {request.asset_name}\n"
            f"Category: {request.asset_category}\n\n"
            f"Approved canon analysis:\n{analysis.model_dump_json(indent=2)}\n\n"
            f"Original approved Story text for source-grounding cross-check:\n"
            f"{request.story_context}\n\n"
            "Use the source only to verify an extracted relationship or resolve an "
            "apparent loss of relationship; never infer new physical design facts. "
            "The analysis includes source facts and may include transient narrative events; "
            "do not promote those events into permanent asset identity or CAP continuity rules.\n"
        )
        if corrections:
            input_text += "CORRECT THE PREVIOUS DRAFT QUALITY ISSUES:\n" + "\n".join(
                f"- {issue}" for issue in corrections
            )
        wire_draft = self._parse(
            instructions=instructions,
            input_text=input_text,
            result_type=_StrictGeneratedCAPDraft,
            stage="CAP Draft Package generation",
        )
        wire_data = wire_draft.model_dump()
        wire_data["production_metadata"] = {
            entry.key: entry.value for entry in wire_draft.production_metadata
        }
        draft = GeneratedCAPDraft.model_validate(wire_data)
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
