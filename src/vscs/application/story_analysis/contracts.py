"""Core contracts for the VSCS story-analysis framework.

Phase 18.2.1 deliberately defines orchestration boundaries only. Concrete
narrative models and extractors are introduced by later Phase 18.2 increments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable


class AnalysisStatus(StrEnum):
    """Lifecycle state of an analysis pipeline execution."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class StoryAnalysisRequest:
    """Immutable input supplied to the story-analysis pipeline."""

    story_id: str
    source_text: str
    source_revision: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.story_id.strip():
            raise ValueError("story_id must not be blank")
        if not self.source_text.strip():
            raise ValueError("source_text must not be blank")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Read-only execution context visible to every analysis stage."""

    request: StoryAnalysisRequest
    artifacts: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))

    def with_artifacts(self, values: Mapping[str, Any]) -> AnalysisContext:
        merged = dict(self.artifacts)
        merged.update(values)
        return AnalysisContext(request=self.request, artifacts=merged)


@dataclass(frozen=True, slots=True)
class StageResult:
    """Output returned by a single analysis stage."""

    stage_id: str
    artifacts: Mapping[str, Any] = field(default_factory=dict)
    diagnostics: tuple[str, ...] = ()
    status: AnalysisStatus = AnalysisStatus.COMPLETED

    def __post_init__(self) -> None:
        if not self.stage_id.strip():
            raise ValueError("stage_id must not be blank")
        object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True, slots=True)
class StoryAnalysisReport:
    """Stable framework-level result for an analysis pipeline run."""

    story_id: str
    status: AnalysisStatus
    stage_results: tuple[StageResult, ...]
    artifacts: Mapping[str, Any]
    diagnostics: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_results", tuple(self.stage_results))
        object.__setattr__(self, "artifacts", MappingProxyType(dict(self.artifacts)))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@runtime_checkable
class StoryAnalysisStage(Protocol):
    """Plugin contract implemented by every story-analysis stage."""

    @property
    def stage_id(self) -> str:
        """Return the globally unique stage identifier."""

    @property
    def order(self) -> int:
        """Return the deterministic execution order."""

    @property
    def enabled(self) -> bool:
        """Return whether the stage participates in pipeline execution."""

    def analyze(self, context: AnalysisContext) -> StageResult:
        """Analyze the current context and return new framework artifacts."""


@runtime_checkable
class StoryAnalysisEngine(Protocol):
    """Application-facing contract for the complete analysis pipeline."""

    def analyze(self, request: StoryAnalysisRequest) -> StoryAnalysisReport:
        """Run all registered stages for the supplied story request."""
