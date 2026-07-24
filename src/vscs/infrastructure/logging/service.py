"""Central logging configuration for Video Series Studio."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


class LoggingService:
    """Configure and expose the shared VSCS logging infrastructure."""

    LOGGER_NAME = "vscs"

    def __init__(
        self,
        log_directory: Path,
        *,
        level: str = "INFO",
        console_enabled: bool = True,
        max_file_size_bytes: int = 5_000_000,
        backup_count: int = 5,
    ) -> None:
        self.log_directory = log_directory
        self.level = level.upper()
        self.console_enabled = console_enabled
        self.max_file_size_bytes = max_file_size_bytes
        self.backup_count = backup_count
        self.log_file = self.log_directory / "vscs.log"

    def configure(self) -> logging.Logger:
        """Configure file and console handlers and return the root VSCS logger."""
        self.log_directory.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(self.LOGGER_NAME)
        logger.setLevel(self._resolve_level(self.level))
        logger.propagate = False
        logger.handlers.clear()

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=self.max_file_size_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(self._resolve_level(self.level))
        logger.addHandler(file_handler)

        if self.console_enabled:
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(self._resolve_level(self.level))
            logger.addHandler(console_handler)

        logger.info("Logging initialized. Log file: %s", self.log_file)
        return logger

    @classmethod
    def get_logger(cls, name: str | None = None) -> logging.Logger:
        """Return the root VSCS logger or a named child logger."""
        if not name:
            return logging.getLogger(cls.LOGGER_NAME)
        return logging.getLogger(f"{cls.LOGGER_NAME}.{name}")

    @staticmethod
    def _resolve_level(level: str) -> int:
        """Convert a configured logging level name to its numeric value."""
        resolved = logging.getLevelName(level.upper())
        if not isinstance(resolved, int):
            raise ValueError(f"Unsupported logging level: {level}")
        return resolved
