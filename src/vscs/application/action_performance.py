"""Action & Performance authoring and compilation for Phase 19.4.2."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectNotOpenError, ProjectService


class ActionPerformanceError(RuntimeError):
    """Raised when Action & Performance intent cannot be processed safely."""


class ActionPerformanceStatus(StrEnum):
    """Governance state for human-reviewed temporal production intent."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ActionPerformanceDraft:
    """Provider-neutral temporal story and performance authority for one Shot."""

    shot_id: str
    source_package_id: str
    source_fingerprint: str
    temporal_narrative: str
    spoken_content: str = ""
    performance_direction: str = ""
    opening_state: str = ""
    closing_state: str = ""
    timing_notes: str = ""
    status: ActionPerformanceStatus = ActionPerformanceStatus.DRAFT


class ActionPerformanceCompilerService:
    """Turn reviewed temporal Shot intent into canonical Production Package content."""

    FILE_NAME = "action_performance.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
    ) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[ActionPerformanceDraft, ...]:
        path = self.draft_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            drafts = tuple(self._from_dict(item) for item in raw.get("action_performance", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ActionPerformanceError(
                f"Unable to load Action & Performance drafts: {exc}"
            ) from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> ActionPerformanceDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> ActionPerformanceDraft:
        """Seed only from governed Shot intent; never invent additional action."""
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise ActionPerformanceError(f"Action & Performance already exists for {normalized}")
        package = self.packages.current_package(normalized)
        if package is None:
            package = self.packages.materialize(normalized)
        shot = package.shot
        draft = ActionPerformanceDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            temporal_narrative=str(shot.get("required_action", "")).strip(),
            spoken_content=str(shot.get("dialogue_requirement", "")).strip(),
            opening_state=str(shot.get("continuity_in", "")).strip(),
            closing_state=str(shot.get("continuity_out", "")).strip(),
            timing_notes=f"Target runtime: {shot.get('target_runtime_seconds', '')} seconds".strip(),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> ActionPerformanceDraft:
        """Rebase a stale Draft without replacing human-authored production intent."""
        current = self._require_draft(shot_id)
        if current.status is ActionPerformanceStatus.READY:
            raise ActionPerformanceError(
                "Ready Action & Performance must return to Draft before refreshing its source"
            )
        package = self.packages.require_current_package(current.shot_id)
        if (
            current.source_package_id == package.package_id
            and current.source_fingerprint == package.source_fingerprint
        ):
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
        )
        self._replace(updated)
        return updated

    def save(
        self,
        shot_id: str,
        *,
        temporal_narrative: str,
        spoken_content: str,
        performance_direction: str,
        opening_state: str,
        closing_state: str,
        timing_notes: str,
    ) -> ActionPerformanceDraft:
        current = self._require_draft(shot_id)
        if current.status is ActionPerformanceStatus.READY:
            raise ActionPerformanceError(
                "Ready Action & Performance must return to Draft before editing"
            )
        package = self.packages.require_current_package(current.shot_id)
        updated = replace(
            current,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            temporal_narrative=temporal_narrative.strip(),
            spoken_content=spoken_content.strip(),
            performance_direction=performance_direction.strip(),
            opening_state=opening_state.strip(),
            closing_state=closing_state.strip(),
            timing_notes=timing_notes.strip(),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> ActionPerformanceDraft:
        current = self._require_draft(shot_id)
        if not current.temporal_narrative.strip():
            raise ActionPerformanceError(
                "Temporal narrative is required before Action & Performance can be Ready"
            )
        if not self.is_current(current):
            raise ActionPerformanceError(
                "Action & Performance is stale against the current Production Package"
            )
        ready = replace(current, status=ActionPerformanceStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> ActionPerformanceDraft:
        current = self._require_draft(shot_id)
        draft = replace(current, status=ActionPerformanceStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: ActionPerformanceDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        return package is not None and package.source_fingerprint == draft.source_fingerprint

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not ActionPerformanceStatus.READY:
            raise ActionPerformanceError("Only Ready Action & Performance may be compiled")
        if not self.is_current(draft):
            raise ActionPerformanceError("Action & Performance is stale and cannot be compiled")
        compiled: dict[str, Any] = {
            "temporal_narrative": draft.temporal_narrative,
            "spoken_content": draft.spoken_content,
            "performance_direction": draft.performance_direction,
            "opening_state": draft.opening_state,
            "closing_state": draft.closing_state,
            "timing_notes": draft.timing_notes,
            "source": "human-reviewed-action-performance",
            "provider_neutral": True,
        }
        return self.packages.derive_action_performance(draft.shot_id, compiled)

    def _require_draft(self, shot_id: str) -> ActionPerformanceDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise ActionPerformanceError(
                f"No Action & Performance exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: ActionPerformanceDraft) -> None:
        drafts = tuple(
            updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
        )
        self._write(drafts)

    def _write(self, drafts: tuple[ActionPerformanceDraft, ...]) -> None:
        path = self.draft_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "action_performance": [self._to_dict(item) for item in drafts],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _to_dict(draft: ActionPerformanceDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> ActionPerformanceDraft:
        return ActionPerformanceDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            source_fingerprint=str(data["source_fingerprint"]),
            temporal_narrative=str(data.get("temporal_narrative", "")),
            spoken_content=str(data.get("spoken_content", "")),
            performance_direction=str(data.get("performance_direction", "")),
            opening_state=str(data.get("opening_state", "")),
            closing_state=str(data.get("closing_state", "")),
            timing_notes=str(data.get("timing_notes", "")),
            status=ActionPerformanceStatus(str(data.get("status", "draft"))),
        )
