"""AI-assisted story entity recognition and resolution domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vscs.domain.story_analysis.models import SourceSpan


class EntityResolutionCategory(StrEnum):
    CHARACTER = "character"
    SHIP = "ship"
    PLANET = "planet"
    LOCATION = "location"
    VEHICLE = "vehicle"
    PROP = "prop"
    TECHNOLOGY = "technology"
    ORGANIZATION = "organization"
    SPECIES = "species"
    ENVIRONMENT = "environment"
    OTHER = "other"


class CandidateReviewStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class ResolutionMatchKind(StrEnum):
    NEW = "new"
    EXISTING = "existing"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    UNCERTAIN = "uncertain"


class AIEntityDraft(BaseModel):
    """Provider-neutral entity proposal returned by an AI analysis provider."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    category: EntityResolutionCategory
    description: str = ""
    aliases: tuple[str, ...] = ()
    evidence_text: tuple[str, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("aliases", "evidence_text")
    @classmethod
    def _deduplicate(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))


class AINarrativeMetadata(BaseModel):
    """AI-derived narrative metadata that does not itself require canon approval."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    summary: str = ""
    themes: tuple[str, ...] = ()
    tone: tuple[str, ...] = ()
    setting: tuple[str, ...] = ()
    production_notes: tuple[str, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class AIStoryAnalysisDraft(BaseModel):
    """Complete structured AI response before deterministic entity resolution."""

    model_config = ConfigDict(frozen=True)

    entities: tuple[AIEntityDraft, ...] = ()
    metadata: AINarrativeMetadata = Field(default_factory=AINarrativeMetadata)
    diagnostics: tuple[str, ...] = ()


class EntityCandidate(BaseModel):
    """One proposed production entity awaiting human review."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    candidate_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=200)
    category: EntityResolutionCategory
    description: str = ""
    aliases: tuple[str, ...] = ()
    evidence: tuple[SourceSpan, ...] = ()
    attributes: dict[str, str] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    review_status: CandidateReviewStatus = CandidateReviewStatus.PROPOSED
    match_kind: ResolutionMatchKind = ResolutionMatchKind.NEW
    matched_asset_id: str | None = None
    matched_asset_name: str | None = None

    @model_validator(mode="after")
    def _validate_match(self) -> "EntityCandidate":
        if self.match_kind is ResolutionMatchKind.EXISTING and not self.matched_asset_id:
            raise ValueError("Existing entity matches require matched_asset_id")
        return self

    def approve(self) -> "EntityCandidate":
        return self.model_copy(update={"review_status": CandidateReviewStatus.APPROVED})

    def reject(self) -> "EntityCandidate":
        return self.model_copy(update={"review_status": CandidateReviewStatus.REJECTED})


class EntityResolutionResult(BaseModel):
    """AI-enriched story analysis with reviewable production-entity candidates."""

    model_config = ConfigDict(frozen=True)

    story_id: str = Field(min_length=1)
    source_revision: str | None = None
    candidates: tuple[EntityCandidate, ...] = ()
    metadata: AINarrativeMetadata = Field(default_factory=AINarrativeMetadata)
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _unique_candidates(self) -> "EntityResolutionResult":
        ids = [candidate.candidate_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("Entity candidate IDs must be unique")
        return self

    @property
    def pending_candidates(self) -> tuple[EntityCandidate, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.review_status is CandidateReviewStatus.PROPOSED
        )
