"""Unit tests for the Phase 18.2.3 deterministic Story Analysis Engine."""

from vscs.application.story_analysis import (
    DeterministicStoryAnalyzer,
    StoryAnalysisRequest,
    StoryStructureParser,
    StoryTokenizer,
)
from vscs.domain.story_analysis import Character, Location, Prop, Technology

TRAILER_STORY = """# Arrival

Commander James Spence stood beside the viewport on the Iron Horizon.
Captain Cheryl Draker watched the planet below.
\"Confirmed visual,\" Cheryl Draker said.
Commander James Spence frowned as the ship entered the atmosphere.

# Discovery

The transport stopped beside the circular doorway.
Commander James Spence stared into the darkness beyond the mountain.
"""


def test_structure_parser_preserves_two_scene_boundaries() -> None:
    sections = StoryStructureParser().parse(TRAILER_STORY)

    assert [section.title for section in sections] == ["Arrival", "Discovery"]
    assert sections[0].start_offset < sections[0].end_offset <= sections[1].start_offset
    assert "Commander James Spence" in sections[0].body


def test_tokenizer_preserves_source_offsets() -> None:
    text = "James arrived. Cheryl waited."

    spans = StoryTokenizer().sentences(text)

    assert [span.text for span in spans] == ["James arrived.", "Cheryl waited."]
    assert text[spans[0].start_offset : spans[0].end_offset] == "James arrived."
    assert text[spans[1].start_offset : spans[1].end_offset] == "Cheryl waited."


def test_analyzer_builds_traceable_story_model() -> None:
    result = DeterministicStoryAnalyzer().analyze(
        StoryAnalysisRequest(
            story_id="xorix-trailer",
            source_text=TRAILER_STORY,
            source_revision="test-1",
        )
    )

    characters = [item for item in result.entities if isinstance(item, Character)]
    locations = [item for item in result.entities if isinstance(item, Location)]
    technologies = [item for item in result.entities if isinstance(item, Technology)]
    props = [item for item in result.entities if isinstance(item, Prop)]

    assert {item.name for item in characters} >= {"James Spence", "Cheryl Draker"}
    assert locations
    assert technologies
    assert props
    assert result.dialogues[0].text == "Confirmed visual,"
    assert result.actions
    assert result.emotions
    assert [event.sequence_index for event in result.ordered_timeline] == [0, 1]
    assert all(item.sources for item in characters)
    assert all(source.excerpt for item in characters for source in item.sources)


def test_analysis_is_deterministic_for_identical_source() -> None:
    analyzer = DeterministicStoryAnalyzer()
    request = StoryAnalysisRequest(story_id="story-1", source_text=TRAILER_STORY)

    first = analyzer.analyze(request)
    second = analyzer.analyze(request)

    assert first == second
    assert [item.entity_id for item in first.entities] == [
        item.entity_id for item in second.entities
    ]


def test_plain_text_without_headings_becomes_single_story_section() -> None:
    sections = StoryStructureParser().parse("Commander James Spence entered the bridge.")

    assert len(sections) == 1
    assert sections[0].title == "Story"
