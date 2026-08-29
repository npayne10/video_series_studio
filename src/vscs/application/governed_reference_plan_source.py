"""Read-only access to persisted governed ACPP reference plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from vscs.application.acpp.serialization import ACPPSerializationError, ACPPSerializer
from vscs.application.projects import ProjectNotOpenError, ProjectService


class GovernedReferencePlanSourceError(RuntimeError):
    """Raised when persisted governed reference authority cannot be read safely."""


class GovernedReferencePlanSource(Protocol):
    """Provide the authoritative persisted reference-plan payload for one Shot."""

    def reference_plan_for_shot(self, shot_id: str) -> dict[str, Any] | None: ...


class PersistedGovernedReferencePlanSource:
    """Resolve governed reference plans from current editable ACPP records."""

    DIRECTORY_NAME = "acpp"

    def __init__(
        self,
        projects: ProjectService,
        serializer: ACPPSerializer | None = None,
    ) -> None:
        self.projects = projects
        self.serializer = serializer or ACPPSerializer()

    @property
    def package_directory(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.DIRECTORY_NAME

    def reference_plan_for_shot(self, shot_id: str) -> dict[str, Any] | None:
        normalized = shot_id.strip().upper()
        directory = self.package_directory
        if not directory.is_dir():
            return None

        match = None
        for path in sorted(directory.glob("*.json")):
            try:
                package = self.serializer.loads(path.read_text(encoding="utf-8"))
            except (OSError, ACPPSerializationError) as exc:
                raise GovernedReferencePlanSourceError(
                    f"Unable to read governed reference authority from {path.name}: {exc}"
                ) from exc
            if package.identity.shot_id.strip().upper() == normalized:
                match = package
                break

        if match is None or match.reference_plan is None:
            return None
        payload = self.serializer.to_dict(match).get("reference_plan")
        if not isinstance(payload, dict):
            raise GovernedReferencePlanSourceError(
                f"Persisted governed reference plan for {normalized} is invalid"
            )
        return dict(payload)
