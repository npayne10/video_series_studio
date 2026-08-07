"""Deterministic source analysis for VSCS story material.

The Phase 18.2.3 engine intentionally uses local, explainable heuristics. It creates
traceable Story Model records without requiring an AI provider. Later extractors may
augment or replace individual heuristics through the existing stage architecture.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha1

from vscs.application.story_analysis.contracts import StoryAnalysisRequest
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
    Technology,
    TimelineEvent,
)

_SENTENCE_PATTERN = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
_QUOTED_PATTERN = re.compile(r'[\"“](.+?)[\"”]', re.DOTALL)
_TITLE_NAME_PATTERN = re.compile(
    r"\b(?P<title>Commander|Captain|Major|Ambassador|Doctor|Dr\.|Admiral|General)\s+"
    r"(?P<name>[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?)"
)
_FULL_NAME_PATTERN = re.compile(r"\b([A-Z][a-z]+\s+[A-Z][A-Za-z'-]+)\b")
_SPEAKER_AFTER_PATTERN = re.compile(
    r"[,\"]\s*(?P<name>[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?)\s+"
    r"(?:said|asked|replied|answered|whispered|called|reported|said softly)\b",
    re.IGNORECASE,
)

_LOCATION_CUES = (
    "planet",
    "city",
    "spaceport",
    "station",
    "bridge",
    "corridor",
    "mountain",
    "world",
    "orbit",
    "surface",
)
_TECHNOLOGY_CUES = (
    "engine",
    "drive",
    "transport",
    "system",
    "conduit",
    "plasma",
    "docking",
    "aircraft",
    "ship",
)
_PROP_CUES = (
    "door",
    "doorway",
    "viewport",
    "platform",
    "console",
    "chair",
    "weapon",
)
_EMOTION_CUES: tuple[tuple[str, str, float], ...] = (
    ("frowned", "concern", 0.65),
    ("afraid", "fear", 0.8),
    ("fear", "fear", 0.75),
    ("smiled", "pleasure", 0.55),
    ("laughed", "amusement", 0.6),
    ("angry", "anger", 0.75),
    ("surprised", "surprise", 0.7),
    ("stared", "awe", 0.55),
    ("awe", "awe", 0.7),
    ("quiet", "unease", 0.35),
)


@dataclass(frozen=True, slots=True)
class TextSpan:
    """Offset-preserving unit of source text."""

    text: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True, slots=True)
class StorySection:
    """Detected story section or scene boundary."""

    title: str
    body: str
    start_offset: int
    end_offset: int
    index: int


class StoryStructureParser:
    """Split story text into deterministic sections while retaining offsets."""

    def parse(self, text: str) -> tuple[StorySection, ...]:
        lines = text.splitlines(keepends=True)
        headings: list[tuple[str, int, int]] = []
        offset = 0
        for index, line in enumerate(lines):
            stripped = line.strip()
            next_blank = index + 1 >= len(lines) or not lines[index + 1].strip()
            if stripped and self._is_heading(stripped, next_blank):
                headings.append((stripped.lstrip("# ").strip(), offset, offset + len(line)))
            offset += len(line)

        if not headings:
            return (
                StorySection(
                    title="Story",
                    body=text,
                    start_offset=0,
                    end_offset=len(text),
                    index=0,
                ),
            )

        sections: list[StorySection] = []
        for section_index, (title, _heading_start, heading_end) in enumerate(headings):
            section_end = (
                headings[section_index + 1][1]
                if section_index + 1 < len(headings)
                else len(text)
            )
            body = text[heading_end:section_end].strip()
            body_start = heading_end
            while body_start < section_end and text[body_start].isspace():
                body_start += 1
            sections.append(
                StorySection(
                    title=title,
                    body=body,
                    start_offset=body_start,
                    end_offset=section_end,
                    index=section_index,
                )
            )
        return tuple(sections)

    @staticmethod
    def _is_heading(value: str, next_blank: bool) -> bool:
        if value.startswith("#"):
            return True
        if not next_blank or len(value) > 80:
            return False
        if value.endswith((".", "?", "!", ":", ";", ",")):
            return False
        words = value.split()
        return 1 <= len(words) <= 8 and all(
            word[:1].isupper() or word.lower() in {"of", "the", "and", "a", "an"}
            for word in words
        )


class StoryTokenizer:
    """Create sentence spans without losing source offsets."""

    def sentences(self, text: str, base_offset: int = 0) -> tuple[TextSpan, ...]:
        spans: list[TextSpan] = []
        for match in _SENTENCE_PATTERN.finditer(text):
            raw = match.group(0)
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw.rstrip())
            cleaned = raw.strip()
            if not cleaned:
                continue
            start = base_offset + match.start() + leading
            end = base_offset + match.start() + trailing
            spans.append(TextSpan(cleaned, start, end))
        return tuple(spans)


class DeterministicStoryAnalyzer:
    """Convert story source into the Phase 18.2.2 structured Story Model."""

    def __init__(
        self,
        parser: StoryStructureParser | None = None,
        tokenizer: StoryTokenizer | None = None,
    ) -> None:
        self._parser = parser or StoryStructureParser()
        self._tokenizer = tokenizer or StoryTokenizer()

    def analyze(self, request: StoryAnalysisRequest) -> AnalysisResult:
        sections = self._parser.parse(request.source_text)
        sentences = tuple(
            span
            for section in sections
            for span in self._tokenizer.sentences(section.body, section.start_offset)
        )
        characters = self._characters(request, sentences)
        entities = self._other_entities(request, sentences, characters)
        all_entities = (*characters, *entities)
        dialogues = self._dialogues(request, sentences, characters)
        actions = self._actions(request, sentences, all_entities)
        emotions = self._emotions(request, sentences, characters)
        relationships = self._relationships(request, sentences, characters)
        timeline = self._timeline(request, sections, all_entities)
        diagnostics = (
            f"Detected {len(sections)} story sections",
            f"Detected {len(sentences)} sentence spans",
            f"Extracted {len(all_entities)} entities and {len(dialogues)} dialogue records",
        )
        return AnalysisResult(
            story_id=request.story_id,
            source_revision=request.source_revision,
            entities=all_entities,
            dialogues=dialogues,
            actions=actions,
            emotions=emotions,
            relationships=relationships,
            timeline_events=timeline,
            diagnostics=diagnostics,
        )

    def _characters(
        self,
        request: StoryAnalysisRequest,
        sentences: tuple[TextSpan, ...],
    ) -> tuple[Character, ...]:
        found: dict[str, tuple[str, SourceSpan]] = {}
        for sentence in sentences:
            for match in _TITLE_NAME_PATTERN.finditer(sentence.text):
                title = match.group("title")
                name = match.group("name")
                source = self._span(
                    request, 
                    sentence.start_offset + match.start(), 
                    sentence.start_offset + match.end()
                )
                found.setdefault(name, (title, source))

            for match in _SPEAKER_AFTER_PATTERN.finditer(sentence.text):
                name = match.group("name")
                if name in found or len(name.split()) < 2:
                    continue
                source = self._span(
                    request, 
                    sentence.start_offset + match.start("name"), 
                    sentence.start_offset + match.end("name")
                )
                found[name] = ("", source)

        return tuple(
            Character(
                entity_id=self._id("character", name),
                name=name,
                narrative_role=title,
                sources=(source,),
                confidence=0.95 if title else 0.8,
            )
            for name, (title, source) in found.items()
        )

    def _other_entities(
        self,
        request: StoryAnalysisRequest,
        sentences: tuple[TextSpan, ...],
        characters: tuple[Character, ...],
    ) -> tuple[Location | Technology | Prop, ...]:
        character_names = {item.name for item in characters}
        candidates: dict[tuple[EntityKind, str], SourceSpan] = {}
        for sentence in sentences:
            lowered = sentence.text.lower()
            for match in _FULL_NAME_PATTERN.finditer(sentence.text):
                name = match.group(1)
                if name in character_names:
                    continue
                kind = self._classify_named_entity(name, lowered)
                if kind is None:
                    continue
                candidates.setdefault(
                    (kind, name),
                    self._span(
                        request,
                        sentence.start_offset + match.start(1),
                        sentence.start_offset + match.end(1),
                    ),
                )

            for cue in (*_LOCATION_CUES, *_TECHNOLOGY_CUES, *_PROP_CUES):
                for match in re.finditer(rf"\b(?:the\s+)?{re.escape(cue)}s?\b", lowered):
                    phrase = sentence.text[match.start():match.end()].strip()
                    name = re.sub(r"^(?:the\s+)", "", phrase, flags=re.IGNORECASE)
                    kind = self._kind_for_cue(cue)
                    candidates.setdefault(
                        (kind, name.title()),
                        self._span(
                            request,
                            sentence.start_offset + match.start(),
                            sentence.start_offset + match.end(),
                        ),
                    )

        models: list[Location | Technology | Prop] = []
        for (kind, name), source in candidates.items():
            if kind is EntityKind.LOCATION:
                models.append(
                    Location(
                        entity_id=self._id("location", name),
                        name=name,
                        sources=(source,),
                        confidence=0.65,
                    )
                )
            elif kind is EntityKind.TECHNOLOGY:
                models.append(
                    Technology(
                        entity_id=self._id("technology", name),
                        name=name,
                        sources=(source,),
                        confidence=0.6,
                    )
                )
            else:
                models.append(
                    Prop(
                        entity_id=self._id("prop", name),
                        name=name,
                        sources=(source,),
                        confidence=0.6,
                    )
                )
        return tuple(models)

    def _dialogues(
        self,
        request: StoryAnalysisRequest,
        sentences: tuple[TextSpan, ...],
        characters: tuple[Character, ...],
    ) -> tuple[Dialogue, ...]:
        by_name = {item.name: item.entity_id for item in characters}
        results: list[Dialogue] = []
        index = 0
        for sentence in sentences:
            for match in _QUOTED_PATTERN.finditer(sentence.text):
                speaker_match = _SPEAKER_AFTER_PATTERN.search(sentence.text[match.end():])
                speaker_id: str | None = None
                if speaker_match is not None:
                    speaker_id = by_name.get(speaker_match.group("name"))
                results.append(
                    Dialogue(
                        dialogue_id=f"dialogue-{index:04d}",
                        text=match.group(1).strip(),
                        speaker_entity_id=speaker_id,
                        source=self._span(
                            request,
                            sentence.start_offset + match.start(),
                            sentence.start_offset + match.end(),
                        ),
                        confidence=0.9 if speaker_id else 0.75,
                    )
                )
                index += 1
        return tuple(results)

    def _actions(
        self,
        request: StoryAnalysisRequest,
        sentences: tuple[TextSpan, ...],
        entities: tuple[Character | Location | Technology | Prop, ...],
    ) -> tuple[Action, ...]:
        results: list[Action] = []
        for index, sentence in enumerate(sentences):
            narrative = _QUOTED_PATTERN.sub("", sentence.text).strip(" ,")
            if len(narrative.split()) < 3:
                continue
            actor_ids = tuple(
                entity.entity_id
                for entity in entities
                if isinstance(entity, Character) and entity.name in narrative
            )
            location_id = next(
                (
                    entity.entity_id
                    for entity in entities
                    if isinstance(entity, Location) and entity.name.lower() in narrative.lower()
                ),
                None,
            )
            results.append(
                Action(
                    action_id=f"action-{index:04d}",
                    summary=narrative,
                    actor_entity_ids=actor_ids,
                    location_entity_id=location_id,
                    source=self._span(request, sentence.start_offset, sentence.end_offset),
                    confidence=0.7,
                )
            )
        return tuple(results)

    def _emotions(
        self,
        request: StoryAnalysisRequest,
        sentences: tuple[TextSpan, ...],
        characters: tuple[Character, ...],
    ) -> tuple[Emotion, ...]:
        results: list[Emotion] = []
        index = 0
        for sentence in sentences:
            lowered = sentence.text.lower()
            subject = next((item for item in characters if item.name in sentence.text), None)
            if subject is None:
                continue
            for cue, emotion, intensity in _EMOTION_CUES:
                if cue not in lowered:
                    continue
                results.append(
                    Emotion(
                        emotion_id=f"emotion-{index:04d}",
                        subject_entity_id=subject.entity_id,
                        emotion=emotion,
                        intensity=intensity,
                        source=self._span(request, sentence.start_offset, sentence.end_offset),
                        confidence=0.65,
                    )
                )
                index += 1
        return tuple(results)

    def _relationships(
        self,
        request: StoryAnalysisRequest,
        sentences: tuple[TextSpan, ...],
        characters: tuple[Character, ...],
    ) -> tuple[Relationship, ...]:
        pairs: dict[tuple[str, str], SourceSpan] = {}
        for sentence in sentences:
            present = [item for item in characters if item.name in sentence.text]
            if len(present) < 2:
                continue
            for left_index, left in enumerate(present):
                for right in present[left_index + 1:]:
                    key = tuple(sorted((left.entity_id, right.entity_id)))
                    pairs.setdefault(
                        key,
                        self._span(request, sentence.start_offset, sentence.end_offset),
                    )
        return tuple(
            Relationship(
                relationship_id=f"relationship-{index:04d}",
                source_entity_id=left,
                target_entity_id=right,
                relationship_type="co-occurrence",
                description="Characters appear together in the same narrative sentence.",
                sources=(source,),
                confidence=0.45,
            )
            for index, ((left, right), source) in enumerate(pairs.items())
        )

    def _timeline(
        self,
        request: StoryAnalysisRequest,
        sections: tuple[StorySection, ...],
        entities: tuple[Character | Location | Technology | Prop, ...],
    ) -> tuple[TimelineEvent, ...]:
        events: list[TimelineEvent] = []
        for section in sections:
            sentences = self._tokenizer.sentences(section.body, section.start_offset)
            if not sentences:
                continue
            first = sentences[0]
            participants = tuple(
                entity.entity_id
                for entity in entities
                if isinstance(entity, Character) and entity.name in section.body
            )
            location_id = next(
                (
                    entity.entity_id
                    for entity in entities
                    if isinstance(entity, Location)
                    and entity.name.lower() in section.body.lower()
                ),
                None,
            )
            events.append(
                TimelineEvent(
                    event_id=f"timeline-{section.index:04d}",
                    sequence_index=section.index,
                    summary=f"{section.title}: {first.text}",
                    participant_entity_ids=participants,
                    location_entity_id=location_id,
                    sources=(
                        self._span(
                            request, 
                            section.start_offset, 
                            max(section.start_offset + 1, section.end_offset),
                        ),
                    ),
                    confidence=0.8,
                )
            )
        return tuple(events)

    @staticmethod
    def _kind_for_cue(cue: str) -> EntityKind:
        if cue in _LOCATION_CUES:
            return EntityKind.LOCATION
        if cue in _TECHNOLOGY_CUES:
            return EntityKind.TECHNOLOGY
        return EntityKind.PROP

    @staticmethod
    def _classify_named_entity(name: str, sentence: str) -> EntityKind | None:
        lowered = name.lower()
        if any(cue in sentence for cue in _LOCATION_CUES) and lowered in sentence:
            return EntityKind.LOCATION
        if any(cue in sentence for cue in _TECHNOLOGY_CUES) and lowered in sentence:
            return EntityKind.TECHNOLOGY
        if any(cue in sentence for cue in _PROP_CUES) and lowered in sentence:
            return EntityKind.PROP
        return None

    def _span(self, request: StoryAnalysisRequest, start: int, end: int) -> SourceSpan:
        text = request.source_text
        bounded_start = max(0, min(start, len(text) - 1))
        bounded_end = max(bounded_start + 1, min(end, len(text)))
        start_line = text.count("\n", 0, bounded_start) + 1
        end_line = text.count("\n", 0, bounded_end) + 1
        return SourceSpan(
            story_id=request.story_id,
            source_revision=request.source_revision,
            start_offset=bounded_start,
            end_offset=bounded_end,
            start_line=start_line,
            end_line=end_line,
            excerpt=text[bounded_start:bounded_end],
        )

    @staticmethod
    def _id(kind: str, name: str) -> str:
        digest = sha1(name.casefold().encode("utf-8"), usedforsecurity=False).hexdigest()[:10]
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:48]
        return f"{kind}-{slug}-{digest}"
