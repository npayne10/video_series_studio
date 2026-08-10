"""Hierarchical continuity-state contracts for renderer-neutral production."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ContinuityScope(StrEnum):
    """Production level at which continuity state applies."""

    SERIES = "series"
    EPISODE = "episode"
    SCENE = "scene"
    SHOT = "shot"


class ContinuityEntityKind(StrEnum):
    """Kinds of production entities whose visible state must persist."""

    CHARACTER = "character"
    LOCATION = "location"
    SHIP = "ship"
    VEHICLE = "vehicle"
    PROP = "prop"
    COSTUME = "costume"
    LIGHTING = "lighting"
    CAMERA = "camera"
    EFFECT = "effect"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ContinuityFrameReference:
    """Approved frame used to preserve a clip-boundary visual state."""

    reference_id: str
    relative_path: str
    frame_number: int | None = None
    checksum: str | None = None

    def __post_init__(self) -> None:
        if not self.reference_id.strip():
            raise ValueError("reference_id is required")
        normalized = self.relative_path.replace("\\", "/")
        unsafe = not normalized or normalized.startswith("/") or ".." in normalized.split("/")
        if unsafe:
            raise ValueError("relative_path must remain project-relative")
        if self.frame_number is not None and self.frame_number < 0:
            raise ValueError("frame_number may not be negative")


@dataclass(frozen=True, slots=True)
class EntityContinuityState:
    """Canonical visible and narrative state for one production entity."""

    entity_id: str
    kind: ContinuityEntityKind
    canonical_asset_id: str | None = None
    state_values: tuple[tuple[str, str], ...] = ()
    mandatory_traits: tuple[str, ...] = ()
    prohibited_changes: tuple[str, ...] = ()
    reference_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.entity_id.strip():
            raise ValueError("entity_id is required")
        keys = [key for key, _value in self.state_values]
        if any(not key.strip() for key in keys):
            raise ValueError("continuity state keys may not be empty")
        if len(keys) != len(set(keys)):
            raise ValueError("continuity state keys must be unique")

    def value(self, key: str) -> str | None:
        """Return one named state value when present."""
        return next(
            (value for name, value in self.state_values if name == key),
            None,
        )


@dataclass(frozen=True, slots=True)
class ScopedContinuityState:
    """Continuity state declared at one production hierarchy level."""

    state_id: str
    scope: ContinuityScope
    production_id: str
    container_id: str | None = None
    scene_id: str | None = None
    shot_id: str | None = None
    entities: tuple[EntityContinuityState, ...] = ()
    requirements: tuple[str, ...] = ()
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.state_id.strip() or not self.production_id.strip():
            raise ValueError("state_id and production_id are required")
        if self.scope is not ContinuityScope.SERIES and not self.container_id:
            raise ValueError("container_id is required below series scope")
        requires_scene = self.scope in {
            ContinuityScope.SCENE,
            ContinuityScope.SHOT,
        }
        if requires_scene and not self.scene_id:
            raise ValueError("scene_id is required for scene and shot scope")
        if self.scope is ContinuityScope.SHOT and not self.shot_id:
            raise ValueError("shot_id is required for shot scope")
        entity_ids = [entity.entity_id for entity in self.entities]
        if len(entity_ids) != len(set(entity_ids)):
            raise ValueError("entity continuity states must be unique by entity_id")


@dataclass(frozen=True, slots=True)
class ContinuityPackage:
    """Resolved continuity input supplied to one render request."""

    package_id: str
    production_id: str
    container_id: str
    scene_id: str
    shot_id: str
    series_state: ScopedContinuityState | None = None
    episode_state: ScopedContinuityState | None = None
    scene_state: ScopedContinuityState | None = None
    shot_state: ScopedContinuityState | None = None
    previous_frame: ContinuityFrameReference | None = None
    next_frame: ContinuityFrameReference | None = None
    screen_direction: str = ""
    continuity_notes: tuple[str, ...] = ()
    version: str = "1.0"

    def __post_init__(self) -> None:
        for name, value in (
            ("package_id", self.package_id),
            ("production_id", self.production_id),
            ("container_id", self.container_id),
            ("scene_id", self.scene_id),
            ("shot_id", self.shot_id),
            ("version", self.version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        expected = (
            (self.series_state, ContinuityScope.SERIES),
            (self.episode_state, ContinuityScope.EPISODE),
            (self.scene_state, ContinuityScope.SCENE),
            (self.shot_state, ContinuityScope.SHOT),
        )
        for state, scope in expected:
            if state is not None and state.scope is not scope:
                raise ValueError(f"{scope.value} continuity state has the wrong scope")

    @property
    def ordered_states(self) -> tuple[ScopedContinuityState, ...]:
        """Return available states from broadest to narrowest scope."""
        return tuple(
            state
            for state in (
                self.series_state,
                self.episode_state,
                self.scene_state,
                self.shot_state,
            )
            if state is not None
        )

    def resolved_entities(self) -> tuple[EntityContinuityState, ...]:
        """Resolve entities with narrower scopes overriding broader scopes."""
        resolved: dict[str, EntityContinuityState] = {}
        for state in self.ordered_states:
            resolved.update({entity.entity_id: entity for entity in state.entities})
        return tuple(resolved.values())


@dataclass(slots=True)
class ContinuityStateRegistry:
    """In-memory registry for continuity contracts before persistence is added."""

    _states: dict[str, ScopedContinuityState] = field(default_factory=dict)

    def register(self, state: ScopedContinuityState) -> None:
        """Register or replace one continuity state by stable identity."""
        self._states[state.state_id] = state

    def get(self, state_id: str) -> ScopedContinuityState | None:
        """Return one continuity state by identity."""
        return self._states.get(state_id)

    def list(
        self,
        scope: ContinuityScope | None = None,
    ) -> tuple[ScopedContinuityState, ...]:
        """List states in stable identity order with optional scope filtering."""
        values = self._states.values()
        return tuple(
            sorted(
                (state for state in values if scope is None or state.scope is scope),
                key=lambda state: state.state_id,
            )
        )
