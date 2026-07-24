"""Secure storage for AI provider credentials."""

from __future__ import annotations

import os
from contextlib import suppress
from importlib import import_module
from typing import Any


class CredentialStorageError(RuntimeError):
    """Raised when a credential cannot be read or stored securely."""


class AICredentialStore:
    """Store API credentials in the operating system credential vault."""

    SERVICE_NAME = "Video Series Studio"
    OPENAI_ACCOUNT = "openai-api-key"

    def get_openai_api_key(self) -> str:
        """Return the stored OpenAI key, falling back to the process environment."""
        environment_key = os.environ.get("OPENAI_API_KEY", "").strip()
        try:
            keyring: Any = import_module("keyring")
        except ImportError:
            return environment_key
        try:
            stored = keyring.get_password(self.SERVICE_NAME, self.OPENAI_ACCOUNT)
        except Exception as exc:
            if environment_key:
                return environment_key
            raise CredentialStorageError(
                f"Unable to read the OpenAI API key from secure storage: {exc}"
            ) from exc
        return (stored or environment_key).strip()

    def set_openai_api_key(self, api_key: str) -> None:
        """Save or remove the OpenAI key in the operating system credential vault."""
        try:
            keyring: Any = import_module("keyring")
        except ImportError as exc:
            raise CredentialStorageError(
                'Install secure credential support with: python -m pip install "keyring>=25"'
            ) from exc
        try:
            if api_key.strip():
                keyring.set_password(
                    self.SERVICE_NAME,
                    self.OPENAI_ACCOUNT,
                    api_key.strip(),
                )
            else:
                with suppress(keyring.errors.PasswordDeleteError):
                    keyring.delete_password(self.SERVICE_NAME, self.OPENAI_ACCOUNT)
        except Exception as exc:
            raise CredentialStorageError(
                f"Unable to update the OpenAI API key in secure storage: {exc}"
            ) from exc
