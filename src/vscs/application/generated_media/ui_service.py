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
    task_id: str
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

    def list_for_production(self, production_id: str) -> tuple[GeneratedMediaListItem, ...]:
        normalized = production_id.strip()
        if not normalized:
            raise GeneratedMediaUiError("production_id cannot be blank")
        persistence = self._persistence()
        selection_service = self._selection_service(persistence)
        items: list[GeneratedMediaListItem] = []
        for media in persistence.list_for_production(normalized):
            selection = selection_service.get_for_media(media)
            items.append(
                GeneratedMediaListItem(
                    media_id=media.media_id,
                    task_id=media.scope.production_task_id,
                    kind=media.kind,
                    state=media.state,
                    revision=media.revision,
                    technical_status=dict(media.technical_metadata).get(
                        "technical_validation.status", "not-validated"
                    ),
                    selected=selection is not None
                    and selection.selected_media_id == media.media_id,
                    relative_path=media.file.relative_path,
                )
            )
        return tuple(
            sorted(
                items,
                key=lambda item: (item.task_id, item.kind.value, item.revision, item.media_id),
            )
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
