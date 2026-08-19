"""Application facade for the Generated Media workspace."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from vscs.domain.generated_media import GeneratedMedia, GeneratedMediaKind, GeneratedMediaState

from .persistence import GeneratedMediaPersistenceService
from .repository import GeneratedMediaRepository
from .review import GeneratedMediaReviewActor, GeneratedMediaReviewService
from .selection import (
    GeneratedMediaSelection,
    GeneratedMediaSelectionRepository,
    GeneratedMediaSelectionService,
)


class GeneratedMediaUiError(RuntimeError):
    """Raised when the Generated Media workspace cannot complete a governed command."""


@dataclass(frozen=True, slots=True)
class GeneratedMediaListItem:
    media_id: str
    production_id: str
    episode_id: str
    scene_id: str | None
    shot_id: str | None
    task_id: str
    task_label: str
    kind: GeneratedMediaKind
    state: GeneratedMediaState
    revision: int
    technical_status: str
    selected: bool
    relative_path: str


@dataclass(frozen=True, slots=True)
class GeneratedMediaDetailView:
    media: GeneratedMedia
    selection: GeneratedMediaSelection | None
    candidates: tuple[GeneratedMedia, ...]


MediaRepositoryFactory = Callable[[], GeneratedMediaRepository]
SelectionRepositoryFactory = Callable[[], GeneratedMediaSelectionRepository]


class GeneratedMediaUiService:
    """Thin governed facade for operator-facing Generated Media queries and commands."""

    def __init__(
        self,
        media_repository_factory: MediaRepositoryFactory,
        selection_repository_factory: SelectionRepositoryFactory,
    ) -> None:
        self._media_repository_factory = media_repository_factory
        self._selection_repository_factory = selection_repository_factory

    def list_all(self) -> tuple[GeneratedMediaListItem, ...]:
        """Return every authoritative Generated Media record for project browsing."""
        return self._list_items(self._persistence().list_all())

    def list_for_production(self, production_id: str) -> tuple[GeneratedMediaListItem, ...]:
        normalized = production_id.strip()
        if not normalized:
            raise GeneratedMediaUiError("production_id cannot be blank")
        return self._list_items(self._persistence().list_for_production(normalized))

    def list_filtered(
        self,
        *,
        production_id: str | None = None,
        episode_id: str | None = None,
        task_id: str | None = None,
    ) -> tuple[GeneratedMediaListItem, ...]:
        """Filter project Generated Media without exposing repository identifiers as input fields."""
        items = self.list_all()
        production = self._optional_filter(production_id)
        episode = self._optional_filter(episode_id)
        task = self._optional_filter(task_id)
        return tuple(
            item
            for item in items
            if (production is None or item.production_id == production)
            and (episode is None or item.episode_id == episode)
            and (task is None or item.task_id == task)
        )

    def detail(self, media_id: str) -> GeneratedMediaDetailView:
        persistence = self._persistence()
        media = self._require_media(persistence, media_id)
        selection_service = self._selection_service(persistence)
        return GeneratedMediaDetailView(
            media=media,
            selection=selection_service.get_for_media(media),
            candidates=selection_service.candidates_for(media),
        )

    def submit_for_review(
        self,
        media_id: str,
        *,
        actor_id: str,
        display_name: str,
        reason: str,
    ) -> GeneratedMediaDetailView:
        persistence = self._persistence()
        GeneratedMediaReviewService(persistence).submit_for_review(
            media_id,
            submitted_by=self._actor(actor_id, display_name),
            reason=reason,
        )
        return self._detail_with(persistence, media_id)

    def approve(
        self,
        media_id: str,
        *,
        actor_id: str,
        display_name: str,
        reason: str,
    ) -> GeneratedMediaDetailView:
        persistence = self._persistence()
        GeneratedMediaReviewService(persistence).approve(
            media_id,
            reviewer=self._actor(actor_id, display_name),
            reason=reason,
        )
        return self._detail_with(persistence, media_id)

    def reject(
        self,
        media_id: str,
        *,
        actor_id: str,
        display_name: str,
        reason: str,
    ) -> GeneratedMediaDetailView:
        persistence = self._persistence()
        GeneratedMediaReviewService(persistence).reject(
            media_id,
            reviewer=self._actor(actor_id, display_name),
            reason=reason,
        )
        return self._detail_with(persistence, media_id)

    def select(
        self,
        media_id: str,
        *,
        actor_id: str,
        display_name: str,
        reason: str,
    ) -> GeneratedMediaDetailView:
        persistence = self._persistence()
        self._selection_service(persistence).select(
            media_id,
            selected_by=self._actor(actor_id, display_name),
            reason=reason,
        )
        return self._detail_with(persistence, media_id)

    def supersede_and_select(
        self,
        media_id: str,
        *,
        actor_id: str,
        display_name: str,
        reason: str,
    ) -> GeneratedMediaDetailView:
        persistence = self._persistence()
        self._selection_service(persistence).supersede_and_select(
            media_id,
            selected_by=self._actor(actor_id, display_name),
            reason=reason,
        )
        return self._detail_with(persistence, media_id)

    def _list_items(self, media_records: tuple[GeneratedMedia, ...]) -> tuple[GeneratedMediaListItem, ...]:
        persistence = self._persistence()
        selection_service = self._selection_service(persistence)
        items = tuple(
            GeneratedMediaListItem(
                media_id=media.media_id,
                production_id=media.scope.production_id,
                episode_id=media.scope.episode_id,
                scene_id=media.scope.scene_id,
                shot_id=media.scope.shot_id,
                task_id=media.scope.production_task_id,
                task_label=self._task_label(media),
                kind=media.kind,
                state=media.state,
                revision=media.revision,
                technical_status=dict(media.technical_metadata).get(
                    "technical_validation.status", "not-validated"
                ),
                selected=(selection := selection_service.get_for_media(media)) is not None
                and selection.selected_media_id == media.media_id,
                relative_path=media.file.relative_path,
            )
            for media in media_records
        )
        return tuple(
            sorted(
                items,
                key=lambda item: (
                    item.production_id,
                    item.episode_id,
                    item.task_label.casefold(),
                    item.kind.value,
                    item.revision,
                    item.media_id,
                ),
            )
        )

    def _detail_with(
        self,
        persistence: GeneratedMediaPersistenceService,
        media_id: str,
    ) -> GeneratedMediaDetailView:
        media = self._require_media(persistence, media_id)
        selection_service = self._selection_service(persistence)
        return GeneratedMediaDetailView(
            media=media,
            selection=selection_service.get_for_media(media),
            candidates=selection_service.candidates_for(media),
        )

    def _persistence(self) -> GeneratedMediaPersistenceService:
        return GeneratedMediaPersistenceService(self._media_repository_factory())

    def _selection_service(
        self,
        persistence: GeneratedMediaPersistenceService,
    ) -> GeneratedMediaSelectionService:
        return GeneratedMediaSelectionService(
            persistence,
            self._selection_repository_factory(),
        )

    @staticmethod
    def _task_label(media: GeneratedMedia) -> str:
        kind = media.kind.value.replace("_", " ").title()
        location = media.scope.shot_id or media.scope.scene_id or media.scope.episode_id
        suffix = media.scope.production_task_id[-8:]
        return f"{kind} — {location} (…{suffix})"

    @staticmethod
    def _optional_filter(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _actor(actor_id: str, display_name: str) -> GeneratedMediaReviewActor:
        try:
            return GeneratedMediaReviewActor(actor_id=actor_id, display_name=display_name)
        except ValueError as exc:
            raise GeneratedMediaUiError(str(exc)) from exc

    @staticmethod
    def _require_media(
        persistence: GeneratedMediaPersistenceService,
        media_id: str,
    ) -> GeneratedMedia:
        normalized = media_id.strip()
        if not normalized:
            raise GeneratedMediaUiError("media_id cannot be blank")
        media = persistence.get(normalized)
        if media is None:
            raise GeneratedMediaUiError(f"Generated Media not found: {normalized}")
        return media
