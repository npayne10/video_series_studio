"""Domain models for structured VSCS story analysis results.

Phase 18.2.2 defines the stable narrative data model consumed by later
analysis, knowledge-graph, persistence, and production-planning phases.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EntityKind(StrEnum):
    """Narrative entity categories extracted from story source material."""

    CHARACTER = "character"
    LOCATION = "location"
    TECHNOLOGY = "technology"
    PROP = "prop"


class SourceSpan(BaseModel):
    """Traceable location of an extracted fact in the source manuscript."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    story_id: str = Field(min_length=1)
    source_revision: str | None = None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(gt=0)
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    excerpt: str = ""

    @model_validator(mode="after")
    def validate_range(self) -> SourceSpan:
        """Require offsets and optional line ranges to progress forward."""
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset must be greater than start_offset")
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.end_line < self.start_line
        ):
            raise ValueError("end_line must be greater than or equal to start_line")
        return self


class StoryAttribute(BaseModel):
    """Small typed key/value fact attached to an extracted entity."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1)


class StoryEntity(BaseModel):
    """Base model shared by all durable narrative entities."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    entity_id: str = Field(min_length=1, max_length=128)
    kind: EntityKind
    name: str = Field(min_length=1, max_length=240)
    aliases: tuple[str, ...] = ()
    description: str = ""
    attributes: tuple[StoryAttribute, ...] = ()
    sources: tuple[SourceSpan, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Remove empty and duplicate aliases while preserving order."""
        return tuple(dict.fromkeys(alias.strip() for alias in value if alias.strip()))


class Character(StoryEntity):
    """Person, creature, or sentient narrative participant."""

    kind: Literal[EntityKind.CHARACTER] = EntityKind.CHARACTER
    narrative_role: str = ""
    traits: tuple[str, ...] = ()


class Location(StoryEntity):
    """Narrative place or spatial setting."""

    kind: Literal[EntityKind.LOCATION] = EntityKind.LOCATION
    environment_notes: str = ""


class Technology(StoryEntity):
    """Narrative technology, system, device class, or engineered capability."""

    kind: Literal[EntityKind.TECHNOLOGY] = EntityKind.TECHNOLOGY
    purpose: str = ""


class Prop(StoryEntity):
    """Narratively significant physical object or production prop."""

    kind: Literal[EntityKind.PROP] = EntityKind.PROP
    usage: str = ""


NarrativeEntity = Character | Location | Technology | Prop


class Dialogue(BaseModel):
    """A traceable spoken or quoted utterance."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    dialogue_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1)
    speaker_entity_id: str | None = None
    addressee_entity_ids: tuple[str, ...] = ()
    source: SourceSpan
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Action(BaseModel):
    """A traceable narrative action or observable event fragment."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    action_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(min_length=1)
    actor_entity_ids: tuple[str, ...] = ()
    target_entity_ids: tuple[str, ...] = ()
    location_entity_id: str | None = None
    source: SourceSpan
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Emotion(BaseModel):
    """An inferred or explicit emotional state tied to a narrative subject."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    emotion_id: str = Field(min_length=1, max_length=128)
    subject_entity_id: str = Field(min_length=1)
    emotion: str = Field(min_length=1, max_length=120)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    source: SourceSpan
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Relationship(BaseModel):
    """Directional relationship between two narrative entities."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    relationship_id: str = Field(min_length=1, max_length=128)
    source_entity_id: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1, max_length=120)
    description: str = ""
    sources: tuple[SourceSpan, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_endpoints(self) -> Relationship:
        """Reject accidental self-relationships at the domain boundary."""
        if self.source_entity_id == self.target_entity_id:
            raise ValueError("relationship endpoints must be different entities")
        return self


class TimelineEvent(BaseModel):
    """Ordered story event used to reconstruct narrative chronology."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    event_id: str = Field(min_length=1, max_length=128)
    sequence_index: int = Field(ge=0)
    summary: str = Field(min_length=1)
    participant_entity_ids: tuple[str, ...] = ()
    location_entity_id: str | None = None
    temporal_marker: str = ""
    sources: tuple[SourceSpan, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AnalysisResult(BaseModel):
    """Complete structured narrative result for one story source revision."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    story_id: str = Field(min_length=1)
    source_revision: str | None = None
    entities: tuple[NarrativeEntity, ...] = ()
    dialogues: tuple[Dialogue, ...] = ()
    actions: tuple[Action, ...] = ()
    emotions: tuple[Emotion, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    timeline_events: tuple[TimelineEvent, ...] = ()
    diagnostics: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_identifiers(self) -> AnalysisResult:
        """Require unique identifiers within every result collection."""
        groups = (
            ("entity", (item.entity_id for item in self.entities)),
            ("dialogue", (item.dialogue_id for item in self.dialogues)),
            ("action", (item.action_id for item in self.actions)),
            ("emotion", (item.emotion_id for item in self.emotions)),
            ("relationship", (item.relationship_id for item in self.relationships)),
            ("timeline event", (item.event_id for item in self.timeline_events)),
        )
        for label, identifiers in groups:
            values = tuple(identifiers)
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifiers are not allowed")
        return self

    def entity(self, entity_id: str) -> NarrativeEntity | None:
        """Resolve an entity by identifier without exposing mutable indexes."""
        return next((entity for entity in self.entities if entity.entity_id == entity_id), None)

    @property
    def ordered_timeline(self) -> tuple[TimelineEvent, ...]:
        """Return timeline events in deterministic chronology order."""
        return tuple(sorted(self.timeline_events, key=lambda event: event.sequence_index))
