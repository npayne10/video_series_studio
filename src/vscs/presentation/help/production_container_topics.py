"""VKF topics for production containers and container-aware scene identity."""

from .knowledge_topics import KnowledgeTopic


PRODUCTION_CONTAINER_TOPICS = (
    KnowledgeTopic(
        topic_id="scene.production_type",
        title="Production Type",
        purpose="Defines the kind of production container that owns the scene.",
        description=(
            "Choose Episode for normal series material, or Trailer, Teaser, Promo, "
            "Special or Test for non-episode production work."
        ),
        examples=("Episode", "Trailer", "Teaser", "Promo", "Special", "Test"),
        common_mistakes=(
            "Putting trailer scenes inside a normal episode only to obtain a Scene ID.",
        ),
        related_topics=("scene.container_id", "scene.sequence"),
        documentation_page="docs/story/scene_editor.md#production-container",
    ),
    KnowledgeTopic(
        topic_id="scene.container_id",
        title="Container ID",
        purpose="Provides the canonical identity of the production owning the scene.",
        description=(
            "Use a stable ID such as EP-001 for an episode or T01 for a trailer. "
            "VSCS combines this value with the scene sequence to generate the Scene ID."
        ),
        examples=("EP-001", "T01", "TEASER-01", "PROMO-01", "TEST-01"),
        common_mistakes=(
            "Using a display title instead of a short canonical identity.",
            "Changing the container identity after downstream production records exist.",
        ),
        related_topics=("scene.production_type", "scene.sequence"),
        documentation_page="docs/story/scene_editor.md#production-container",
    ),
)
