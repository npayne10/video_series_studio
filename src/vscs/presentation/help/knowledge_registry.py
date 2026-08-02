"""Central topic registry for the VSCS Knowledge Framework."""

from __future__ import annotations

from collections.abc import Iterable

from .knowledge_topics import SCENE_TOPICS, KnowledgeTopic


class KnowledgeTopicNotFoundError(LookupError):
    """Raised when a requested VKF topic does not exist."""


class KnowledgeRegistry:
    """Store and retrieve immutable knowledge topics by canonical ID."""

    def __init__(self, topics: Iterable[KnowledgeTopic] = ()) -> None:
        self._topics: dict[str, KnowledgeTopic] = {}
        self.register_many(topics)

    def register(self, topic: KnowledgeTopic) -> None:
        """Register or replace one topic by its canonical ID."""
        topic_id = topic.topic_id.strip()
        if not topic_id:
            raise ValueError("Knowledge topic ID cannot be empty.")
        self._topics[topic_id] = topic

    def register_many(self, topics: Iterable[KnowledgeTopic]) -> None:
        """Register several topics."""
        for topic in topics:
            self.register(topic)

    def topic(self, topic_id: str) -> KnowledgeTopic:
        """Return a required topic or raise a descriptive lookup error."""
        normalized = topic_id.strip()
        try:
            return self._topics[normalized]
        except KeyError as exc:
            raise KnowledgeTopicNotFoundError(
                f"Knowledge topic is not registered: {normalized or '<empty>'}"
            ) from exc

    def get(self, topic_id: str) -> KnowledgeTopic | None:
        """Return a topic when available."""
        return self._topics.get(topic_id.strip())

    def contains(self, topic_id: str) -> bool:
        """Return whether the topic is registered."""
        return topic_id.strip() in self._topics

    def all_topics(self) -> tuple[KnowledgeTopic, ...]:
        """Return topics in stable canonical-ID order."""
        return tuple(self._topics[key] for key in sorted(self._topics))


def build_default_knowledge_registry() -> KnowledgeRegistry:
    """Build the application registry with all currently supported topics."""
    return KnowledgeRegistry(SCENE_TOPICS)
