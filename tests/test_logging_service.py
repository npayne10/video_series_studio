"""Tests for the VSCS logging service."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from vscs.infrastructure.logging import LoggingService


def _close_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers:
        handler.close()
    logger.handlers.clear()


def test_configure_creates_log_file_and_writes_message(tmp_path: Path) -> None:
    service = LoggingService(tmp_path / "logs", console_enabled=False)
    logger = service.configure()

    logger.info("Configuration test message")
    for handler in logger.handlers:
        handler.flush()

    assert service.log_file.exists()
    assert "Configuration test message" in service.log_file.read_text(encoding="utf-8")
    _close_handlers(logger)


def test_named_logger_uses_vscs_hierarchy(tmp_path: Path) -> None:
    service = LoggingService(tmp_path / "logs", console_enabled=False)
    root_logger = service.configure()
    child_logger = service.get_logger("renderer")

    assert child_logger.name == "vscs.renderer"
    assert child_logger.parent is root_logger
    _close_handlers(root_logger)


def test_configure_replaces_existing_handlers(tmp_path: Path) -> None:
    service = LoggingService(tmp_path / "logs", console_enabled=False)
    logger = service.configure()
    first_handlers = list(logger.handlers)

    logger = service.configure()

    assert len(logger.handlers) == 1
    assert logger.handlers != first_handlers
    _close_handlers(logger)


def test_invalid_log_level_is_rejected(tmp_path: Path) -> None:
    service = LoggingService(tmp_path / "logs", level="VERBOSE")

    with pytest.raises(ValueError, match="Unsupported logging level"):
        service.configure()
