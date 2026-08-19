"""Generated Media revision, supersession, and authoritative selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol

from vscs.domain.generated_media import GeneratedMedia, GeneratedMediaKind, GeneratedMediaState

from .persistence import GeneratedMediaPersistenceService
from .review import GeneratedMediaReviewActor, ReviewAuthorityType


class GeneratedMediaSelectionError(RuntimeError):
    """Raised when Generated Media selection or supersession is invalid."""


@dataclass(frozen=True, slots=True)
class GeneratedMediaSelectionEvent:
    """One immutable authoritative selection change for a production intent slot."""

    previous_media_id: str | None
    selected_media_id: str
    selected_revision: int
    actor: str
    reason: str
    occurred_at: datetime

    def __post_init__(self) -> None:
        if self.previous_media_id is not None and not self.previous_media_id.strip():
            raise ValueError("previous_media_id cannot be blank when supplied")
        if not self.selected_media_id.strip():
            raise ValueError("selected_media_id cannot be blank")
        if self.selected_revision < 1:
            raise ValueError("selected_revision must be at least 1")
        if not self.actor.strip() or not self.reason.strip():
            raise ValueError("selection actor and reason are required")
        if self.previous_media_id == self.selected_media_id:
            raise ValueError("selection event must change selected media")


@dataclass(frozen=True, slots=True)
class GeneratedMediaSelection:
    """Durable single authoritative selection for one Generated Media production intent."""

    selection_id: str
    production_id: str
    episode_id: str
    production_task_id: str
    kind: GeneratedMediaKind
    selected_media_id: str
    selected_revision: int
    selected_by: str
    reason: str
    selected_at: datetime
    history: tuple[GeneratedMediaSelectionEvent, ...]

    def __post_init__(self) -> None:
        for field_name, value in (
            ("selection_id", self.selection_id),
            ("production_id", self.production_id),
            ("episode_id", self.episode_id),
            ("production_task_id", self.production_task_id),
            ("selected_media_id", self.selected_media_id),
            ("selected_by", self.selected_by),
            ("reason", self.reason),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.selected_revision < 1:
            raise ValueError("selected_revision must be at least 1")
        if not self.history:
            raise ValueError("Generated Media selection requires history")
        previous: str | None = None
        for index, event in enumerate(self.history):
            if event.previous_media_id != previous:
                raise ValueError("Generated Media selection history is discontinuous")
            if index > 0 and event.selected_revision <= self.history[index - 1].selected_revision:
                raise ValueError("Generated Media selection revisions must increase")
            previous = event.selected_media_id
        latest = self.history[-1]
        if (
            latest.selected_media_id != self.selected_media_id
            or latest.selected_revision != self.selected_revision
            or latest.actor != self.selected_by
            or latest.reason != self.reason
            or latest.occurred_at != self.selected_at
        ):
            raise ValueError("Generated Media selection must match latest history event")


class GeneratedMediaSelectionRepository(Protocol):
    """Persistence boundary for one selection record per production intent."""

    def get(self, selection_id: str) -> GeneratedMediaSelection | None:
        ...

    def save(self, selection: GeneratedMediaSelection) -> GeneratedMediaSelection:
        ...

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMediaSelection, ...]:
        ...


@dataclass(frozen=True, slots=True)
class GeneratedMediaSupersessionResult:
    previous_media: GeneratedMedia
    replacement_media: GeneratedMedia
    selection: GeneratedMediaSelection


class GeneratedMediaSelectionService:
    """Own human-authorised Generated Media selection and supersession."""

    def __init__(
        self,
        media: GeneratedMediaPersistenceService,
        selections: GeneratedMediaSelectionRepository,
    ) -> None:
        self.media = media
        self.selections = selections

    def select(
        self,
        media_id: str,
        *,
        selected_by: GeneratedMediaReviewActor,
        reason: str,
        now: datetime | None = None,
    ) -> GeneratedMediaSelection:
        """Select one approved candidate when no active selection exists for its intent."""
        actor = self._require_human(selected_by)
        message = self._require_reason(reason)
        candidate = self._require_media(media_id)
        self._require_approved(candidate)
        selection_id = self.selection_id_for(candidate)
        if self.selections.get(selection_id) is not None:
            raise GeneratedMediaSelectionError(
                "Generated Media production intent already has an authoritative selection"
            )
        current = now or datetime.now(UTC)
        event = GeneratedMediaSelectionEvent(
            previous_media_id=None,
            selected_media_id=candidate.media_id,
            selected_revision=candidate.revision,
            actor=actor,
            reason=message,
            occurred_at=current,
        )
        selection = GeneratedMediaSelection(
            selection_id=selection_id,
            production_id=candidate.scope.production_id,
            episode_id=candidate.scope.episode_id,
            production_task_id=candidate.scope.production_task_id,
            kind=candidate.kind,
            selected_media_id=candidate.media_id,
            selected_revision=candidate.revision,
            selected_by=actor,
            reason=message,
            selected_at=current,
            history=(event,),
        )
        return self.selections.save(selection)

    def supersede_and_select(
        self,
        replacement_media_id: str,
        *,
        selected_by: GeneratedMediaReviewActor,
        reason: str,
        now: datetime | None = None,
    ) -> GeneratedMediaSupersessionResult:
        """Replace the selected approved revision and explicitly supersede the prior media."""
        actor = self._require_human(selected_by)
        message = self._require_reason(reason)
        replacement = self._require_media(replacement_media_id)
        self._require_approved(replacement)
        selection_id = self.selection_id_for(replacement)
        existing = self.selections.get(selection_id)
        if existing is None:
            raise GeneratedMediaSelectionError(
                "Generated Media production intent has no current selection to supersede"
            )
        if existing.selected_media_id == replacement.media_id:
            return self._finish_pending_supersession(existing, replacement)

        previous = self._require_media(existing.selected_media_id)
        self._require_approved(previous)
        self._require_same_intent(previous, replacement)
        if replacement.revision <= previous.revision:
            raise GeneratedMediaSelectionError(
                "replacement media revision must be later than the selected revision"
            )

        current = now or datetime.now(UTC)
        event = GeneratedMediaSelectionEvent(
            previous_media_id=previous.media_id,
            selected_media_id=replacement.media_id,
            selected_revision=replacement.revision,
            actor=actor,
            reason=message,
            occurred_at=current,
        )
        updated_selection = GeneratedMediaSelection(
            selection_id=existing.selection_id,
            production_id=existing.production_id,
            episode_id=existing.episode_id,
            production_task_id=existing.production_task_id,
            kind=existing.kind,
            selected_media_id=replacement.media_id,
            selected_revision=replacement.revision,
            selected_by=actor,
            reason=message,
            selected_at=current,
            history=(*existing.history, event),
        )

        # Persist selection first. A retry can deterministically finish the governance write
        # from the latest immutable selection event if the second persistence step fails.
        saved_selection = self.selections.save(updated_selection)
        superseded = self.media.governance.supersede(
            previous,
            replacement_media_id=replacement.media_id,
            actor=actor,
            reason=message,
            occurred_at=current,
        )
        saved_previous = self.media.save(superseded)
        return GeneratedMediaSupersessionResult(
            previous_media=saved_previous,
            replacement_media=replacement,
            selection=saved_selection,
        )

    def _finish_pending_supersession(
        self,
        selection: GeneratedMediaSelection,
        replacement: GeneratedMedia,
    ) -> GeneratedMediaSupersessionResult:
        latest = selection.history[-1]
        previous_media_id = latest.previous_media_id
        if previous_media_id is None:
            raise GeneratedMediaSelectionError("replacement media is already selected")
        previous = self._require_media(previous_media_id)
        self._require_same_intent(previous, replacement)
        if previous.state is GeneratedMediaState.SUPERSEDED:
            event = previous.governance_history[-1]
            if event.replacement_media_id != replacement.media_id:
                raise GeneratedMediaSelectionError(
                    "superseded media points to a different replacement"
                )
            return GeneratedMediaSupersessionResult(
                previous_media=previous,
                replacement_media=replacement,
                selection=selection,
            )
        self._require_approved(previous)
        superseded = self.media.governance.supersede(
            previous,
            replacement_media_id=replacement.media_id,
            actor=latest.actor,
            reason=latest.reason,
            occurred_at=latest.occurred_at,
        )
        return GeneratedMediaSupersessionResult(
            previous_media=self.media.save(superseded),
            replacement_media=replacement,
            selection=selection,
        )

    def get_for_media(self, media: GeneratedMedia) -> GeneratedMediaSelection | None:
        return self.selections.get(self.selection_id_for(media))

    def candidates_for(self, media: GeneratedMedia) -> tuple[GeneratedMedia, ...]:
        """Return immutable candidates for the same production intent in revision order."""
        candidates = tuple(
            item
            for item in self.media.list_for_task(media.scope.production_task_id)
            if self._same_intent(item, media)
        )
        return tuple(sorted(candidates, key=lambda item: (item.revision, item.media_id)))

    @staticmethod
    def selection_id_for(media: GeneratedMedia) -> str:
        raw = "|".join(
            (
                media.scope.production_id,
                media.scope.episode_id,
                media.scope.production_task_id,
                media.kind.value,
            )
        )
        digest = sha256(raw.encode("utf-8")).hexdigest()[:24].upper()
        return f"GMS-{digest}"

    def _require_media(self, media_id: str) -> GeneratedMedia:
        normalized = media_id.strip()
        if not normalized:
            raise GeneratedMediaSelectionError("media_id cannot be blank")
        media = self.media.get(normalized)
        if media is None:
            raise GeneratedMediaSelectionError(f"Generated Media not found: {normalized}")
        return media

    @staticmethod
    def _require_approved(media: GeneratedMedia) -> None:
        if media.state is not GeneratedMediaState.APPROVED:
            raise GeneratedMediaSelectionError(
                "Only APPROVED Generated Media can become authoritative selection"
            )

    @staticmethod
    def _require_human(actor: GeneratedMediaReviewActor) -> str:
        if actor.authority_type is not ReviewAuthorityType.HUMAN:
            raise GeneratedMediaSelectionError("Generated Media selection requires human authority")
        return actor.audit_identity

    @staticmethod
    def _require_reason(reason: str) -> str:
        normalized = reason.strip()
        if not normalized:
            raise GeneratedMediaSelectionError("selection reason/comment cannot be blank")
        return normalized

    @classmethod
    def _require_same_intent(cls, left: GeneratedMedia, right: GeneratedMedia) -> None:
        if not cls._same_intent(left, right):
            raise GeneratedMediaSelectionError(
                "Generated Media supersession requires the same production intent"
            )

    @staticmethod
    def _same_intent(left: GeneratedMedia, right: GeneratedMedia) -> bool:
        return (
            left.scope.production_id == right.scope.production_id
            and left.scope.episode_id == right.scope.episode_id
            and left.scope.production_task_id == right.scope.production_task_id
            and left.kind is right.kind
        )
