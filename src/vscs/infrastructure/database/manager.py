"""Project-scoped SQLite database lifecycle management."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.database.models import Base, SchemaVersion
from vscs.infrastructure.logging import LoggingService


class DatabaseError(RuntimeError):
    """Base exception for database lifecycle failures."""


class DatabaseNotOpenError(DatabaseError):
    """Raised when an operation requires an active project database."""


class DatabaseAlreadyOpenError(DatabaseError):
    """Raised when opening a second database without closing the first."""


class DatabaseIntegrityError(DatabaseError):
    """Raised when SQLite reports a failed integrity check."""


class DatabaseManager:
    """Manage the SQLite database belonging to the active VSCS project."""

    SCHEMA_VERSION = 1
    APPLICATION_VERSION = "0.1.0"

    def __init__(self) -> None:
        self.database_path: Path | None = None
        self.engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._logger = LoggingService.get_logger("database")

    @property
    def is_open(self) -> bool:
        """Return whether a project database is active."""
        return self.engine is not None

    def open(self, project_directory: Path, project: ProjectMetadata) -> Path:
        """Open or initialize the active project's SQLite database."""
        if self.is_open:
            raise DatabaseAlreadyOpenError("Close the current database before continuing")

        database_path = (project_directory / project.paths.database).resolve(strict=False)
        try:
            database_path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(f"sqlite:///{database_path.as_posix()}", future=True)
            self._configure_sqlite(engine)
            self.database_path = database_path
            self.engine = engine
            self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
            Base.metadata.create_all(engine)
            self._install_or_validate_schema()
            self.check_integrity()
        except (OSError, SQLAlchemyError, DatabaseError) as exc:
            self.close()
            if isinstance(exc, DatabaseError):
                raise
            raise DatabaseError(f"Unable to open database {database_path}: {exc}") from exc

        self._logger.info("Database opened: %s", database_path)
        return database_path

    def close(self) -> None:
        """Dispose the active engine and clear database state."""
        if self.engine is not None:
            self.engine.dispose()
            self._logger.info("Database closed: %s", self.database_path)
        self.database_path = None
        self.engine = None
        self._session_factory = None

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transaction that commits or rolls back automatically."""
        factory = self._require_session_factory()
        database_session = factory()
        try:
            yield database_session
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise
        finally:
            database_session.close()

    def check_integrity(self) -> bool:
        """Run SQLite's integrity check and raise when corruption is detected."""
        engine = self._require_engine()
        try:
            with engine.connect() as connection:
                result = connection.execute(text("PRAGMA integrity_check")).scalar_one()
        except SQLAlchemyError as exc:
            raise DatabaseError(f"Unable to check database integrity: {exc}") from exc
        if result != "ok":
            raise DatabaseIntegrityError(f"Database integrity check failed: {result}")
        return True

    def backup(self, destination: Path | None = None) -> Path:
        """Create a consistent file backup of the active SQLite database."""
        database_path = self._require_database_path()
        if destination is None:
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            destination = database_path.parent / "backups" / f"project-{stamp}.db"
        destination = destination.expanduser().resolve(strict=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._require_engine().begin() as connection:
                connection.execute(text("PRAGMA wal_checkpoint(FULL)"))
            shutil.copy2(database_path, destination)
        except (OSError, SQLAlchemyError) as exc:
            raise DatabaseError(f"Unable to back up database: {exc}") from exc
        self._logger.info("Database backup created: %s", destination)
        return destination

    def _install_or_validate_schema(self) -> None:
        with self.session() as database_session:
            schema = database_session.scalar(select(SchemaVersion).where(SchemaVersion.id == 1))
            if schema is None:
                database_session.add(
                    SchemaVersion(
                        id=1,
                        version=self.SCHEMA_VERSION,
                        application_version=self.APPLICATION_VERSION,
                    )
                )
                return
            if schema.version > self.SCHEMA_VERSION:
                raise DatabaseError(
                    "Project database schema is newer than this VSCS installation: "
                    f"{schema.version} > {self.SCHEMA_VERSION}"
                )
            if schema.version < self.SCHEMA_VERSION:
                self._migrate(database_session, schema)

    def _migrate(self, database_session: Session, schema: SchemaVersion) -> None:
        """Apply ordered migrations up to the current schema version."""
        migrations: dict[int, callable] = {}
        while schema.version < self.SCHEMA_VERSION:
            next_version = schema.version + 1
            migration = migrations.get(next_version)
            if migration is None:
                raise DatabaseError(f"No migration is registered for schema {next_version}")
            migration(database_session)
            schema.version = next_version
        schema.application_version = self.APPLICATION_VERSION

    @staticmethod
    def _configure_sqlite(engine: Engine) -> None:
        @event.listens_for(engine, "connect")
        def configure_connection(dbapi_connection: object, _record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    def _require_engine(self) -> Engine:
        if self.engine is None:
            raise DatabaseNotOpenError("No project database is currently open")
        return self.engine

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise DatabaseNotOpenError("No project database is currently open")
        return self._session_factory

    def _require_database_path(self) -> Path:
        if self.database_path is None:
            raise DatabaseNotOpenError("No project database is currently open")
        return self.database_path
