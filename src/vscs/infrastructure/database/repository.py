"""Reusable SQLAlchemy repository primitives."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from vscs.infrastructure.database.models import Base


class Repository[ModelType: Base]:
    """Small typed repository for common ORM persistence operations."""

    def __init__(self, session: Session, model_type: type[ModelType]) -> None:
        self.session = session
        self.model_type = model_type

    def add(self, model: ModelType) -> ModelType:
        """Add a model to the current transaction."""
        self.session.add(model)
        return model

    def get(self, identity: object) -> ModelType | None:
        """Return a model by primary-key identity."""
        return self.session.get(self.model_type, identity)

    def list_all(self) -> list[ModelType]:
        """Return every model instance ordered by its primary key."""
        return list(self.session.scalars(select(self.model_type)).all())

    def delete(self, model: ModelType) -> None:
        """Delete a model in the current transaction."""
        self.session.delete(model)
