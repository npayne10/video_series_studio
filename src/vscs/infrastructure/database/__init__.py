"""Project database infrastructure."""

from vscs.infrastructure.database.manager import (
    DatabaseAlreadyOpenError,
    DatabaseError,
    DatabaseIntegrityError,
    DatabaseManager,
    DatabaseNotOpenError,
)
from vscs.infrastructure.database.models import Base, SchemaVersion
from vscs.infrastructure.database.repository import Repository

__all__ = [
    "Base",
    "DatabaseAlreadyOpenError",
    "DatabaseError",
    "DatabaseIntegrityError",
    "DatabaseManager",
    "DatabaseNotOpenError",
    "Repository",
    "SchemaVersion",
]
