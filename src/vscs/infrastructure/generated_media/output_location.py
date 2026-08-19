"""Resolve the VSCS-managed Generated Media output location inside a project."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


class ProjectMediaOutputError(ValueError):
    """Raised when configured Generated Media storage escapes project authority."""


class ProjectMediaOutputResolver:
    """Resolve one safe project-relative folder for authoritative media bytes."""

    DEFAULT_DIRECTORY = "Media Output"

    @classmethod
    def resolve(cls, project_directory: Path, configured_directory: str | None = None) -> Path:
        project = Path(project_directory).expanduser().resolve(strict=False)
        configured = (configured_directory or cls.DEFAULT_DIRECTORY).strip().replace("\\", "/")
        if not configured:
            configured = cls.DEFAULT_DIRECTORY
        relative = PurePosixPath(configured)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or (relative.parts and ":" in relative.parts[0])
        ):
            raise ProjectMediaOutputError(
                "Media output directory must remain inside the current VSCS project"
            )
        if configured in {".", ".."}:
            raise ProjectMediaOutputError("Media output directory must name a project subdirectory")
        output = project.joinpath(*relative.parts).resolve(strict=False)
        try:
            output.relative_to(project)
        except ValueError as exc:
            raise ProjectMediaOutputError(
                "Media output directory resolves outside the current VSCS project"
            ) from exc
        return output

    @classmethod
    def relative_path(cls, project_directory: Path, configured_directory: str | None = None) -> str:
        project = Path(project_directory).expanduser().resolve(strict=False)
        return cls.resolve(project, configured_directory).relative_to(project).as_posix()
