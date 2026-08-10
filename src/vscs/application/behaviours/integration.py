"""Composition helper for Behaviour Profile application services."""

from __future__ import annotations

from vscs.application.behaviours.repository import BehaviourProfileRepository
from vscs.application.behaviours.service import BehaviourProfileService
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.services import ApplicationServices


def ensure_behaviour_profile_service(services: ApplicationServices) -> BehaviourProfileService:
    """Return the shared Behaviour Profile service, registering it once if needed."""
    existing = services.get(BehaviourProfileService)
    if existing is not None:
        return existing
    database = services.require(DatabaseManager)
    repository = services.get(BehaviourProfileRepository)
    if repository is None:
        repository = services.register(
            BehaviourProfileRepository,
            BehaviourProfileRepository(database),
        )
    return services.register(BehaviourProfileService, BehaviourProfileService(repository))
