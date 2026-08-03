"""VKF topics for production-container scene identity."""

from .knowledge_topics import KnowledgeTopic

CONTAINER_TOPICS = (
    KnowledgeTopic(
        topic_id="scene.production_type",
        title="Production Type",
        purpose="Defines the kind of production that owns the scene.",
        description=(
            "Choose Episode for normal series scenes, or Trailer, Teaser, Promo, Test "
            "or Special for non-episode content. The choice supplies a suitable default "
            "container ID while keeping the Scene ID stable and generated."
        ),
        examples=("Episode", "Trailer", "Teaser", "Promo", "Test", "Special"),
        common_mistakes=(
            "Creating trailer scenes inside an episode merely to obtain a Scene ID.",
        ),
        related_topics=("scene.container_id", "scene.sequence"),
        documentation_page="docs/story/scene_editor.md#production-container",
    ),
    KnowledgeTopic(
        topic_id="scene.container_id",
        title="Container ID",
        purpose="Identifies the episode, trailer or other production that owns the scene.",
        description=(
            "Use a short canonical identity such as EP-001 or T01. VSCS combines it with "
            "the scene sequence to generate the immutable Scene ID."
        ),
        examples=("EP-001", "T01", "TEASER-01", "PROMO-01", "TEST-01"),
        common_mistakes=(
            "Using a descriptive title instead of a stable canonical identity.",
            "Changing the container identity after production records already exist.",
        ),
        related_topics=("scene.production_type", "scene.sequence"),
        documentation_page="docs/story/scene_editor.md#container-id",
    ),
)
