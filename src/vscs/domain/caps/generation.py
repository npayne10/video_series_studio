"""Structured inputs and outputs for automated CAP generation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CAPGenerationRequest(BaseModel):
    """Story-grounded request for a generated Canonical Asset Profile."""

    model_config = ConfigDict(str_strip_whitespace=True)

    asset_id: str = Field(min_length=1, max_length=64)
    asset_name: str = Field(min_length=1, max_length=200)
    asset_category: str = Field(min_length=1, max_length=64)
    asset_description: str = ""
    story_context: str = Field(min_length=1)


class ExtractedCanonicalFact(BaseModel):
    """One explicit story fact with evidence and a confidence score."""

    model_config = ConfigDict(str_strip_whitespace=True)

    fact: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class CanonicalFactExtraction(BaseModel):
    """Stage-one extraction of explicit facts and candidate claims."""

    model_config = ConfigDict(str_strip_whitespace=True)

    facts: tuple[ExtractedCanonicalFact, ...] = ()
    candidate_claims: tuple[str, ...] = ()


class CAPCanonAnalysis(BaseModel):
    """Stage-two separation of established canon from uncertainty."""

    model_config = ConfigDict(str_strip_whitespace=True)

    canonical_facts: tuple[ExtractedCanonicalFact, ...] = ()
    uncertainties: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    source_summary: str = ""


class CAPSectionConfidence(BaseModel):
    """Confidence scores for each generated CAP Draft Package section."""

    canonical_description: float = Field(default=0.0, ge=0.0, le=1.0)
    visual_identity: float = Field(default=0.0, ge=0.0, le=1.0)
    production_notes: float = Field(default=0.0, ge=0.0, le=1.0)
    continuity_rules: float = Field(default=0.0, ge=0.0, le=1.0)
    prohibited_variations: float = Field(default=0.0, ge=0.0, le=1.0)
    functional_capabilities: float = Field(default=0.0, ge=0.0, le=1.0)
    classifications: float = Field(default=0.0, ge=0.0, le=1.0)
    overall: float = Field(default=0.0, ge=0.0, le=1.0)


class GeneratedCAPDraft(BaseModel):
    """Validated CAP draft returned by an automation provider."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    canonical_description: str = Field(min_length=1)
    visual_identity: str = ""
    production_notes: str = ""
    continuity_rules: tuple[str, ...] = ()
    prohibited_variations: tuple[str, ...] = ()
    functional_capabilities: tuple[str, ...] = ()
    semantic_tags: tuple[str, ...] = ()
    production_classifications: tuple[str, ...] = ()
    behaviour_references: tuple[str, ...] = ()
    production_metadata: dict[str, str] = Field(default_factory=dict)
    unresolved_questions: tuple[str, ...] = ()
    source_summary: str = ""
    canonical_facts: tuple[ExtractedCanonicalFact, ...] = ()
    contradictions: tuple[str, ...] = ()
    confidence: CAPSectionConfidence = Field(default_factory=CAPSectionConfidence)
