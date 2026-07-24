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


class GeneratedCAPDraft(BaseModel):
    """Validated CAP draft returned by an automation provider."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    canonical_description: str = Field(min_length=1)
    visual_identity: str = ""
    production_notes: str = ""
    continuity_rules: tuple[str, ...] = ()
    prohibited_variations: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    source_summary: str = ""
