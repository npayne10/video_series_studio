"""Reusable provider for practical VSCS field examples."""

from __future__ import annotations

from dataclasses import dataclass

from .adaptive_examples import heading_suggestions, scene_name_examples
from .empty_state_examples import empty_state_text
from .scene_examples import SCENE_EXAMPLES, ExampleTopic


@dataclass(frozen=True, slots=True)
class ExampleContext:
    """Optional project names used to personalise suggestions."""

    locations: tuple[str, ...] = ()
    characters: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()


class ExampleProvider:
    """Resolve placeholders, tips, empty states and adaptive suggestions."""

    def __init__(
        self,
        topics: tuple[ExampleTopic, ...] = SCENE_EXAMPLES,
        context: ExampleContext | None = None,
    ) -> None:
        self._topics = {topic.topic_id: topic for topic in topics}
        self.context = context or ExampleContext()

    def topic(self, topic_id: str) -> ExampleTopic | None:
        """Return one registered example topic, if present."""
        return self._topics.get(topic_id)

    def placeholder(self, topic_id: str) -> str:
        """Return a project-aware placeholder for a field."""
        topic = self.topic(topic_id)
        if topic is None:
            return ""
        if topic_id == "scene.name":
            dynamic = scene_name_examples(
                self.context.locations,
                self.context.characters,
            )
            if dynamic:
                return f"Example: {dynamic[0]}"
        return topic.placeholder

    def inline_tip(self, topic_id: str) -> str:
        """Return a concise inline production tip."""
        topic = self.topic(topic_id)
        return topic.inline_tip if topic is not None else ""

    def empty_state(self, topic_id: str) -> str:
        """Return actionable guidance for an empty selector or editor."""
        topic = self.topic(topic_id)
        return empty_state_text(topic.empty_state if topic is not None else None)

    def adaptive(self, topic_id: str, prefix: str) -> tuple[str, ...]:
        """Return optional context-aware completion suggestions."""
        if topic_id == "scene.heading":
            return heading_suggestions(prefix, self.context.locations)
        return ()

    def examples(self, topic_id: str) -> tuple[str, ...]:
        """Return project-aware examples followed by registered fallbacks."""
        topic = self.topic(topic_id)
        if topic is None:
            return ()
        if topic_id == "scene.name":
            dynamic = scene_name_examples(
                self.context.locations,
                self.context.characters,
            )
            return tuple(dict.fromkeys(dynamic + topic.examples))
        return topic.examples
