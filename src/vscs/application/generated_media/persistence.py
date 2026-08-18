"""Application persistence service for authoritative Generated Media."""

from __future__ import annotations

from vscs.domain.generated_media import GeneratedMedia

from .governance import GeneratedMediaGovernanceService
from .repository import GeneratedMediaRepository, GeneratedMediaRepositoryError


class GeneratedMediaPersistenceService:
    """Persist and retrieve only governance-valid Generated Media records."""

    def __init__(
        self,
        repository: GeneratedMediaRepository,
        governance: GeneratedMediaGovernanceService | None = None,
    ) -> None:
        self.repository = repository
        self.governance = governance or GeneratedMediaGovernanceService()

    def register(self, media: GeneratedMedia) -> GeneratedMedia:
        """Register a new stable media identity without replacing an existing record."""
        self.governance.require_valid(media)
        if self.repository.get(media.media_id) is not None:
            raise GeneratedMediaRepositoryError(
                f"Generated Media identity already exists: {media.media_id}"
            )
        return self.repository.save(media)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        """Persist a governance-valid update for an existing or new media identity."""
        self.governance.require_valid(media)
        return self.repository.save(media)

    def get(self, media_id: str) -> GeneratedMedia | None:
        media = self.repository.get(media_id)
        if media is not None:
            self.governance.require_valid(media)
        return media

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        return self._validated(self.repository.list_for_production(production_id))

    def list_for_episode(
        self,
        production_id: str,
        episode_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        return self._validated(self.repository.list_for_episode(production_id, episode_id))

    def list_for_scene(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        return self._validated(self.repository.list_for_scene(production_id, episode_id, scene_id))

    def list_for_shot(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
        shot_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        return self._validated(
            self.repository.list_for_shot(production_id, episode_id, scene_id, shot_id)
        )

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        return self._validated(self.repository.list_for_task(production_task_id))

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        return self._validated(self.repository.list_for_execution(execution_id))

    def _validated(self, media: tuple[GeneratedMedia, ...]) -> tuple[GeneratedMedia, ...]:
        for item in media:
            self.governance.require_valid(item)
        return media
