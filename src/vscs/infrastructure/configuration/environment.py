"""Apply validated VSCS runtime configuration at application startup."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from vscs.infrastructure.configuration.models import ApplicationSettings


@dataclass(frozen=True, slots=True)
class EnvironmentHealth:
    """Result of validating the configured external rendering environment."""

    ready: bool
    messages: tuple[str, ...]


class EnvironmentManager:
    """Create runtime folders and publish application-owned environment variables.

    Windows environment variables remain supported as external overrides, but normal
    application startup is driven by the persisted VSCS settings file.
    """

    def __init__(self, settings: ApplicationSettings) -> None:
        self.settings = settings

    def apply(self) -> dict[str, str]:
        """Apply configured values to the current process and create core folders."""
        environment = self.settings.environment
        workspace = environment.workspace_root.expanduser().resolve(strict=False)
        xcic_root = environment.xcic_root.expanduser().resolve(strict=False)
        config_root = environment.config_root.expanduser().resolve(strict=False)
        projects_root = environment.projects_root.expanduser().resolve(strict=False)
        logs_root = environment.logs_root.expanduser().resolve(strict=False)
        cache_root = environment.cache_root.expanduser().resolve(strict=False)

        for directory in (workspace, xcic_root, config_root, projects_root, logs_root, cache_root):
            directory.mkdir(parents=True, exist_ok=True)

        values = {
            "VSCS_WORKSPACE_ROOT": str(workspace),
            "VSCS_CONFIG_ROOT": str(config_root),
            "VSCS_PROJECTS_ROOT": str(projects_root),
            "VSCS_LOGS_ROOT": str(logs_root),
            "VSCS_CACHE_ROOT": str(cache_root),
            "VSCS_XCIC_ROOT": str(xcic_root),
            "VSCS_COMFYUI_URL": environment.comfyui_url.rstrip("/"),
            "VSCS_XCIC_TEXT_WORKFLOW": str(
                self._resolve(xcic_root, environment.xcic_text_workflow)
            ),
        }
        if environment.xcic_reference_workflow:
            values["VSCS_XCIC_REFERENCE_WORKFLOW"] = str(
                self._resolve(xcic_root, environment.xcic_reference_workflow)
            )

        # Application configuration is authoritative for this process. This also
        # neutralises stale user-level variables inherited by the launched process.
        os.environ.update(values)
        return values

    def healthcheck(self) -> EnvironmentHealth:
        """Validate folders and the loader-based XCIC API workflow."""
        environment = self.settings.environment
        xcic_root = environment.xcic_root.expanduser().resolve(strict=False)
        workflow = self._resolve(xcic_root, environment.xcic_text_workflow)
        messages: list[str] = []
        if not xcic_root.is_dir():
            messages.append(f"XCIC installation folder not found: {xcic_root}")
        if not workflow.is_file():
            messages.append(f"XCIC text-to-image API workflow not found: {workflow}")
        elif workflow.name.casefold() == "qwen_xcic_api_workflow.json":
            messages.append(
                "The obsolete mapping-based qwen_xcic_api_workflow.json is configured. "
                "Select the loader-based API export instead."
            )
        return EnvironmentHealth(not messages, tuple(messages))

    @staticmethod
    def _resolve(root: Path, value: Path) -> Path:
        return value.expanduser() if value.is_absolute() else root / value
