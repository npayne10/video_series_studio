"""Persistence contracts for authoritative Generated Media records."""

from __future__ import annotations

from typing import Protocol

from vscs.domain.generated_media import GeneratedMedia


class GeneratedMediaRepositoryError(RuntimeError):
    """Raised when Generated Media persistence cannot complete safely."""


class GeneratedMediaRepository(Protocol):
    """Persistence boundary for authoritative Generated Media records."""

    def get(self, media_id: str) -> GeneratedMedia | None:
        """Return one Generated Media record by stable identity."""
        ...

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        """Create or replace one authoritative Generated Media record."""
        ...

    def list_all(self) -> tuple[GeneratedMedia, ...]:
        """Return all Generated Media records in deterministic identity order."""
        ...

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        """Return Generated Media for one production in deterministic order."""
        ...

    def list_for_episode(
        self,
        production_id: str,
        episode_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        """Return Generated Media for one episode."""
        ...

    def list_for_scene(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        """Return Generated Media for one scene."""
        ...

    def list_for_shot(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
        shot_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        """Return Generated Media for one shot."""
        ...

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        """Return Generated Media produced for one ProductionTask."""
        ...

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        """Return Generated Media originating from one execution identity."""
        ...
