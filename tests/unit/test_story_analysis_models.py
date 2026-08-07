"""Tests for Phase 18.2.2 story-analysis domain models."""

import pytest
from pydantic import ValidationError

from vscs.domain.story_analysis import (
    Action,
    AnalysisResult,
    Character,
    Dialogue,
    Emotion,
    EntityKind,
    Location,
    Prop,
    Relationship,
    SourceSpan,
    StoryAttribute,
    Technology,
    TimelineEvent,
)


def source_span() -> SourceSpan:
    """Return a representative traceable manuscript span."""
    return SourceSpan(
        story_id="story-1",
        source_revision="rev-4",
        start_offset=10,
        end_offset=42,
        start_line=2,
        end_line=3,
        excerpt="James entered the bridge.",
    )


def test_source_span_validates_offsets_and_lines() -> None:
    """Source provenance cannot point backwards or to an empty range."""
    with pytest.raises(ValidationError, match="end_offset"):
        SourceSpan(story_id="story-1", start_offset=10, end_offset=10)

    with pytest.raises(ValidationError, match="end_line"):
        SourceSpan(
            story_id="story-1",
            start_offset=0,
            end_offset=5,
            start_line=4,
            end_line=3,
        )


def test_source_span_is_immutable() -> None:
    """Traceability coordinates remain stable after construction."""
    span = source_span()

    with pytest.raises(ValidationError):
        span.start_offset = 20


def test_character_normalizes_aliases_and_attributes() -> None:
    """Entity aliases are normalized without losing their declared order."""
    character = Character(
        entity_id="char-james",
        name="Commander James Spence",
        aliases=("James", " James ", "", "Commander Spence"),
        attributes=(StoryAttribute(name="rank", value="Commander"),),
        sources=(source_span(),),
        narrative_role="protagonist",
        traits=("disciplined", "observant"),
    )

    assert character.kind is EntityKind.CHARACTER
    assert character.aliases == ("James", "Commander Spence")
    assert character.attributes[0].value == "Commander"


def test_entity_subtypes_enforce_their_kind() -> None:
    """A concrete entity cannot be mislabeled as another entity category."""
    with pytest.raises(ValidationError):
        Character(entity_id="char-1", name="James", kind=EntityKind.LOCATION)


def test_all_supported_entity_types_can_be_constructed() -> None:
    """The Phase 18.2.2 model covers the production-relevant entity classes."""
    entities = (
        Character(entity_id="char-1", name="James"),
        Location(entity_id="loc-1", name="Mauritania Bridge"),
        Technology(entity_id="tech-1", name="Jump Drive"),
        Prop(entity_id="prop-1", name="Command Tablet"),
    )

    assert tuple(entity.kind for entity in entities) == (
        EntityKind.CHARACTER,
        EntityKind.LOCATION,
        EntityKind.TECHNOLOGY,
        EntityKind.PROP,
    )


def test_confidence_and_emotion_intensity_are_bounded() -> None:
    """Probabilistic analysis values stay within the normalized 0..1 range."""
    with pytest.raises(ValidationError):
        Character(entity_id="char-1", name="James", confidence=1.1)

    with pytest.raises(ValidationError):
        Emotion(
            emotion_id="emotion-1",
            subject_entity_id="char-1",
            emotion="concern",
            intensity=-0.1,
            source=source_span(),
        )


def test_narrative_records_preserve_source_traceability() -> None:
    """Dialogue, actions, and emotions retain the exact source span."""
    span = source_span()
    dialogue = Dialogue(
        dialogue_id="dialogue-1",
        text="Take us in.",
        speaker_entity_id="char-1",
        source=span,
    )
    action = Action(
        action_id="action-1",
        summary="James enters the bridge.",
        actor_entity_ids=("char-1",),
        location_entity_id="loc-1",
        source=span,
    )
    emotion = Emotion(
        emotion_id="emotion-1",
        subject_entity_id="char-1",
        emotion="focus",
        intensity=0.8,
        source=span,
    )

    assert dialogue.source is span
    assert action.source is span
    assert emotion.source is span


def test_relationship_rejects_self_reference() -> None:
    """Relationship edges require two distinct endpoints."""
    with pytest.raises(ValidationError, match="different entities"):
        Relationship(
            relationship_id="rel-1",
            source_entity_id="char-1",
            target_entity_id="char-1",
            relationship_type="trusts",
        )


def test_analysis_result_rejects_duplicate_identifiers() -> None:
    """Each structured result collection has stable unique identities."""
    james = Character(entity_id="char-1", name="James")
    duplicate = Character(entity_id="char-1", name="Commander Spence")

    with pytest.raises(ValidationError, match="duplicate entity"):
        AnalysisResult(story_id="story-1", entities=(james, duplicate))


def test_analysis_result_supports_lookup_and_deterministic_timeline() -> None:
    """Consumers can resolve entities and obtain chronology without mutation."""
    james = Character(entity_id="char-1", name="James")
    later = TimelineEvent(
        event_id="event-2",
        sequence_index=20,
        summary="The ship enters orbit.",
        participant_entity_ids=("char-1",),
        sources=(source_span(),),
    )
    earlier = TimelineEvent(
        event_id="event-1",
        sequence_index=10,
        summary="James reaches the bridge.",
        participant_entity_ids=("char-1",),
        sources=(source_span(),),
    )
    result = AnalysisResult(
        story_id="story-1",
        source_revision="rev-4",
        entities=(james,),
        timeline_events=(later, earlier),
    )

    assert result.entity("char-1") is james
    assert result.entity("missing") is None
    assert result.timeline_events == (later, earlier)
    assert result.ordered_timeline == (earlier, later)


def test_complete_analysis_result_holds_all_phase_18_2_2_records() -> None:
    """The aggregate can carry all structured narrative concepts together."""
    span = source_span()
    character = Character(entity_id="char-1", name="James", sources=(span,))
    location = Location(entity_id="loc-1", name="Bridge", sources=(span,))
    dialogue = Dialogue(dialogue_id="dialogue-1", text="Ready.", source=span)
    action = Action(action_id="action-1", summary="James nods.", source=span)
    emotion = Emotion(
        emotion_id="emotion-1",
        subject_entity_id="char-1",
        emotion="resolve",
        source=span,
    )
    relationship = Relationship(
        relationship_id="rel-1",
        source_entity_id="char-1",
        target_entity_id="loc-1",
        relationship_type="present_at",
        sources=(span,),
    )
    event = TimelineEvent(
        event_id="event-1",
        sequence_index=0,
        summary="James arrives.",
        sources=(span,),
    )

    result = AnalysisResult(
        story_id="story-1",
        entities=(character, location),
        dialogues=(dialogue,),
        actions=(action,),
        emotions=(emotion,),
        relationships=(relationship,),
        timeline_events=(event,),
        diagnostics=("analysis complete",),
    )

    assert len(result.entities) == 2
    assert result.dialogues == (dialogue,)
    assert result.actions == (action,)
    assert result.emotions == (emotion,)
    assert result.relationships == (relationship,)
    assert result.timeline_events == (event,)
