"""Reusable persisted Beginner Mode preference support."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal


class BeginnerModeController(QObject):
    """Manage and persist whether guided beginner assistance is enabled."""

    enabled_changed = Signal(bool)

    def __init__(
        self,
        settings: QSettings,
        key: str,
        parent: QObject | None = None,
        *,
        default_enabled: bool = True,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._key = key
        self._enabled = settings.value(key, default_enabled, type=bool)

    @property
    def enabled(self) -> bool:
        """Return whether beginner guidance is enabled."""
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        """Update and persist Beginner Mode."""
        normalized = bool(enabled)
        if normalized == self._enabled:
            return
        self._enabled = normalized
        self._settings.setValue(self._key, normalized)
        self._settings.sync()
        self.enabled_changed.emit(normalized)
