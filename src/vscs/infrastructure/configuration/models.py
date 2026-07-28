"""Typed configuration models for Video Series Studio."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Theme(StrEnum):
    """Supported application themes."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class AIProvider(StrEnum):
    """Supported AI generation providers."""

    TEMPLATE = "template"
    OPENAI = "openai"


class AISettings(BaseModel):
    """AI provider preferences that are safe to persist in YAML."""

    provider: AIProvider = AIProvider.TEMPLATE
    openai_model: str = "gpt-5.5"

    @field_validator("openai_model")
    @classmethod
    def validate_openai_model(cls, model: str) -> str:
        normalized = model.strip()
        if not normalized:
            raise ValueError("OpenAI model is required")
        return normalized


class RendererSettings(BaseModel):
    """Configuration for an external rendering application."""

    enabled: bool = False
    executable_path: Path | None = None
    api_url: str | None = None


class EnvironmentSettings(BaseModel):
    """Application-owned workspace, XCIC, and ComfyUI runtime settings."""

    workspace_root: Path = Path(r"D:\VSCS")
    config_root: Path = Path(r"D:\VSCS\config")
    projects_root: Path = Path(r"D:\VSCS\Projects")
    logs_root: Path = Path(r"D:\VSCS\Logs")
    cache_root: Path = Path(r"D:\VSCS\Cache")
    xcic_root: Path = Path(r"D:\VSCS\XCIC")
    comfyui_url: str = "http://127.0.0.1:8188"
    xcic_text_workflow: Path = Path("Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json")
    xcic_reference_workflow: Path | None = None
    validate_on_startup: bool = True
    developer_mode: bool = False

    @field_validator("comfyui_url")
    @classmethod
    def validate_comfyui_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("ComfyUI URL must begin with http:// or https://")
        return normalized


class DatabaseSettings(BaseModel):
    """Application database and cache locations."""

    database_path: Path | None = None
    cache_directory: Path | None = None


class PluginSettings(BaseModel):
    """Persistent application plugin preferences."""

    disabled: list[str] = Field(default_factory=list)

    @field_validator("disabled")
    @classmethod
    def normalize_disabled_plugins(cls, plugin_ids: list[str]) -> list[str]:
        return list(dict.fromkeys(plugin_id.strip() for plugin_id in plugin_ids if plugin_id.strip()))


class LoggingSettings(BaseModel):
    """Application logging preferences."""

    level: str = "INFO"
    console_enabled: bool = True
    max_file_size_bytes: int = Field(default=5_000_000, ge=100_000)
    backup_count: int = Field(default=5, ge=1, le=50)

    @field_validator("level")
    @classmethod
    def validate_level(cls, level: str) -> str:
        normalized = level.upper()
        supported = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in supported:
            raise ValueError(f"Unsupported logging level: {level}")
        return normalized


class WorkspaceSettings(BaseModel):
    """Workspace behaviour and user-interface preferences."""

    default_workspace: str = "Dashboard"
    restore_last_project: bool = True
    confirm_before_exit: bool = False


class ApplicationSettings(BaseModel):
    """Root VSCS application configuration model."""

    schema_version: int = 2
    theme: Theme = Theme.SYSTEM
    recent_projects: list[Path] = Field(default_factory=list)
    maximum_recent_projects: int = Field(default=10, ge=1, le=50)
    ai: AISettings = Field(default_factory=AISettings)
    environment: EnvironmentSettings = Field(default_factory=EnvironmentSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    renderers: dict[str, RendererSettings] = Field(
        default_factory=lambda: {
            "comfyui": RendererSettings(enabled=True, api_url="http://127.0.0.1:8188"),
            "pinokio": RendererSettings(),
        }
    )

    @field_validator("recent_projects")
    @classmethod
    def remove_duplicate_recent_projects(cls, projects: list[Path]) -> list[Path]:
        unique: list[Path] = []
        seen: set[str] = set()
        for project in projects:
            key = str(project.expanduser().resolve(strict=False)).casefold()
            if key not in seen:
                seen.add(key)
                unique.append(project)
        return unique
